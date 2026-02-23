"""Lineage extractor — walks sqlglot ASTs to extract table and column lineage."""

from __future__ import annotations

from typing import Optional

from sqlglot import exp

from sqllineage.core.models import (
    Column,
    EdgeType,
    LineageEdge,
    LineageGraph,
    Table,
)


def _parse_table_ref(table_expr: exp.Table) -> Table:
    """Convert a sqlglot Table expression into our Table model."""
    name = table_expr.name
    schema_name = table_expr.db if table_expr.db else None
    database = table_expr.catalog if table_expr.catalog else None
    return Table(name=name, schema_name=schema_name, database=database)


def _get_source_tables(expression: exp.Expression) -> list[Table]:
    """Extract all source tables from a SQL expression (FROM, JOIN, subqueries)."""
    sources: list[Table] = []
    seen: set[str] = set()

    for table_expr in expression.find_all(exp.Table):
        # Skip if this table is the target of an INSERT/CREATE/MERGE
        parent = table_expr.parent
        if isinstance(parent, (exp.Insert, exp.Create, exp.Merge)):
            continue
        # Skip if this is a CTE name reference in WITH clause definition
        if isinstance(parent, exp.CTE):
            continue

        table = _parse_table_ref(table_expr)
        key = table.qualified_name.lower()
        if key not in seen:
            seen.add(key)
            sources.append(table)

    return sources


def _get_target_table(statement: exp.Expression) -> Optional[Table]:
    """Extract the target table from a DML/DDL statement."""

    # INSERT INTO ... SELECT
    if isinstance(statement, exp.Insert):
        table_expr = statement.this
        if isinstance(table_expr, exp.Table):
            return _parse_table_ref(table_expr)

    # CREATE TABLE ... AS SELECT / CREATE VIEW ... AS SELECT
    if isinstance(statement, exp.Create):
        table_expr = statement.this
        if isinstance(table_expr, exp.Table):
            return _parse_table_ref(table_expr)
        # CREATE TABLE might wrap a Schema node
        if isinstance(table_expr, exp.Schema):
            inner = table_expr.this
            if isinstance(inner, exp.Table):
                return _parse_table_ref(inner)

    # MERGE INTO
    if isinstance(statement, exp.Merge):
        table_expr = statement.this
        if isinstance(table_expr, exp.Table):
            return _parse_table_ref(table_expr)

    return None


def _get_cte_names(statement: exp.Expression) -> dict[str, exp.Expression]:
    """Extract CTE names and their definitions from a WITH clause."""
    ctes: dict[str, exp.Expression] = {}
    with_clause = statement.find(exp.With)
    if with_clause:
        for cte in with_clause.find_all(exp.CTE):
            alias = cte.alias
            if alias:
                ctes[alias.lower()] = cte.this
    return ctes


def _extract_column_lineage(
    statement: exp.Expression,
    target_table: Optional[Table],
    source_tables: list[Table],
    source_file: Optional[str],
) -> list[LineageEdge]:
    """Extract column-level lineage from SELECT expressions."""
    edges: list[LineageEdge] = []

    if target_table is None:
        return edges

    # Find the main SELECT
    select = None
    if isinstance(statement, exp.Select):
        select = statement
    else:
        select = statement.find(exp.Select)

    if select is None:
        return edges

    # Build table alias map
    alias_map: dict[str, Table] = {}
    for table in source_tables:
        alias_map[table.name.lower()] = table

    for from_expr in select.find_all(exp.From):
        for table_expr in from_expr.find_all(exp.Table):
            tbl = _parse_table_ref(table_expr)
            alias = table_expr.alias
            if alias:
                alias_map[alias.lower()] = tbl
            alias_map[tbl.name.lower()] = tbl

    for join_expr in select.find_all(exp.Join):
        for table_expr in join_expr.find_all(exp.Table):
            tbl = _parse_table_ref(table_expr)
            alias = table_expr.alias
            if alias:
                alias_map[alias.lower()] = tbl
            alias_map[tbl.name.lower()] = tbl

    # Process SELECT expressions
    for select_expr in select.expressions:
        target_col_name = None

        if isinstance(select_expr, exp.Alias):
            target_col_name = select_expr.alias
            inner = select_expr.this
        else:
            inner = select_expr
            if isinstance(inner, exp.Column):
                target_col_name = inner.name

        if target_col_name is None:
            continue
        if target_col_name == "*":
            continue

        target_col = Column(name=target_col_name, table=target_table)

        # Find source columns referenced in this expression
        for col_ref in (
            [inner] if isinstance(inner, exp.Column) else inner.find_all(exp.Column)
        ):
            source_col_name = col_ref.name
            source_table_ref = col_ref.table
            if source_col_name == "*":
                continue

            source_table = None
            if source_table_ref:
                source_table = alias_map.get(source_table_ref.lower())
            elif len(source_tables) == 1:
                source_table = source_tables[0]

            source_col = Column(name=source_col_name, table=source_table)

            edges.append(
                LineageEdge(
                    source=source_col.qualified_name,
                    target=target_col.qualified_name,
                    edge_type=EdgeType.COLUMN_TO_COLUMN,
                    expression=select_expr.sql() if hasattr(select_expr, "sql") else str(select_expr),
                    source_file=source_file,
                )
            )

    return edges


def extract_lineage(
    statements: list[exp.Expression],
    source_file: Optional[str] = None,
    include_columns: bool = True,
) -> LineageGraph:
    """Extract lineage from a list of parsed SQL statements.

    Args:
        statements: List of sqlglot AST expressions.
        source_file: Optional filename for provenance tracking.
        include_columns: Whether to extract column-level lineage.

    Returns:
        A LineageGraph with all discovered nodes and edges.
    """
    graph = LineageGraph()

    for statement in statements:
        _process_statement(statement, graph, source_file, include_columns)

    return graph


def _process_statement(
    statement: exp.Expression,
    graph: LineageGraph,
    source_file: Optional[str],
    include_columns: bool,
) -> None:
    """Process a single SQL statement and add lineage to the graph."""

    # Extract CTEs first
    ctes = _get_cte_names(statement)

    # Determine the target table (if any)
    target_table = _get_target_table(statement)

    # Determine the node type for the target
    target_node_type = "table"
    if isinstance(statement, exp.Create):
        kind = statement.args.get("kind")
        if kind and str(kind).upper() == "VIEW":
            target_node_type = "view"

    # Get source tables
    source_tables = _get_source_tables(statement)

    # For plain SELECT with no target, create a virtual target
    if target_table is None and isinstance(statement, exp.Select):
        # Standalone SELECT — track sources only
        for src in source_tables:
            src.source_file = source_file
            is_cte = src.name.lower() in ctes
            src.is_cte = is_cte
            graph.add_table(src, node_type="cte" if is_cte else "table")
        return

    if target_table is None:
        # DDL without lineage interest (e.g., CREATE TABLE without AS SELECT)
        # Still register tables referenced
        for src in source_tables:
            src.source_file = source_file
            graph.add_table(src)
        return

    # Register target
    target_table.source_file = source_file
    graph.add_table(target_table, node_type=target_node_type)

    # Register sources and create table-level edges
    for src in source_tables:
        src.source_file = source_file
        is_cte = src.name.lower() in ctes
        src.is_cte = is_cte
        graph.add_table(src, node_type="cte" if is_cte else "table")

        graph.add_edge(
            LineageEdge(
                source=src.qualified_name,
                target=target_table.qualified_name,
                edge_type=EdgeType.TABLE_TO_TABLE,
                source_file=source_file,
            )
        )

    # Column-level lineage
    if include_columns:
        col_edges = _extract_column_lineage(
            statement, target_table, source_tables, source_file
        )
        for col_edge in col_edges:
            # Register column nodes
            parts = col_edge.source.rsplit(".", 1)
            if len(parts) == 2:
                graph.add_column(Column(name=parts[1], table=Table(name=parts[0].split(".")[-1])))
            parts = col_edge.target.rsplit(".", 1)
            if len(parts) == 2:
                graph.add_column(Column(name=parts[1], table=Table(name=parts[0].split(".")[-1])))
            graph.add_edge(col_edge)
