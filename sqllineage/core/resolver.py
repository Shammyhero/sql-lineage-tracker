"""Multi-file dependency resolver — handles cross-file SQL lineage."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqllineage.core.extractor import extract_lineage
from sqllineage.core.models import LineageGraph
from sqllineage.core.parser import parse_file, parse_sql


def resolve_files(
    file_paths: list[str | Path],
    dialect: Optional[str] = None,
    include_columns: bool = True,
) -> LineageGraph:
    """Parse multiple SQL files and resolve cross-file lineage.

    This function:
    1. Parses each file individually
    2. Extracts lineage from each file
    3. Merges all lineage graphs into one unified graph
    4. Cross-file references are automatically resolved by matching
       qualified table names across files.

    Args:
        file_paths: List of paths to SQL files.
        dialect: SQL dialect (e.g., 'postgres', 'bigquery'). None = auto-detect.
        include_columns: Whether to extract column-level lineage.

    Returns:
        A unified LineageGraph with cross-file lineage resolved.
    """
    unified_graph = LineageGraph()

    for file_path in file_paths:
        path = Path(file_path)
        file_name = path.name

        try:
            statements = parse_file(path, dialect=dialect)
            file_graph = extract_lineage(
                statements,
                source_file=file_name,
                include_columns=include_columns,
            )
            unified_graph.merge(file_graph)
        except Exception as e:
            # Log but don't fail — continue processing other files
            print(f"Warning: Error processing {file_name}: {e}")

    return unified_graph


def resolve_sql_strings(
    sql_strings: list[tuple[str, str]],
    dialect: Optional[str] = None,
    include_columns: bool = True,
) -> LineageGraph:
    """Parse multiple SQL strings and resolve cross-file lineage.

    Args:
        sql_strings: List of (filename, sql_content) tuples.
        dialect: SQL dialect.
        include_columns: Whether to extract column-level lineage.

    Returns:
        A unified LineageGraph.
    """
    unified_graph = LineageGraph()

    for file_name, sql_content in sql_strings:
        try:
            statements = parse_sql(sql_content, dialect=dialect)
            file_graph = extract_lineage(
                statements,
                source_file=file_name,
                include_columns=include_columns,
            )
            unified_graph.merge(file_graph)
        except Exception as e:
            print(f"Warning: Error processing {file_name}: {e}")

    return unified_graph


def get_execution_order(graph: LineageGraph) -> list[str]:
    """Compute topological order of tables based on dependencies.

    Returns a list of table qualified names in dependency order
    (tables with no dependencies first).
    """
    # Build adjacency: source -> [targets]
    adj: dict[str, set[str]] = {}
    in_degree: dict[str, int] = {}

    for table_id in graph.tables:
        adj.setdefault(table_id, set())
        in_degree.setdefault(table_id, 0)

    for edge in graph.edges:
        if edge.edge_type.value == "table_to_table":
            src = edge.source.lower()
            tgt = edge.target.lower()
            if src in adj and tgt in in_degree:
                adj[src].add(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

    # Kahn's algorithm for topological sort
    queue: list[str] = [node for node, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Include any remaining nodes (cycles or disconnected)
    remaining = [t for t in graph.tables if t not in order]
    order.extend(remaining)

    return order
