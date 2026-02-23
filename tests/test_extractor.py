"""Tests for the lineage extractor module."""

import pytest
from sqllineage.core.parser import parse_sql
from sqllineage.core.extractor import extract_lineage
from sqllineage.core.models import EdgeType


class TestTableLineage:
    """Test table-level lineage extraction."""

    def test_create_table_as_select(self):
        sql = "CREATE TABLE target AS SELECT id, name FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "target" in graph.tables
        assert "source" in graph.tables
        assert len([e for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE]) == 1
        assert graph.edges[0].source == "source"
        assert graph.edges[0].target == "target"

    def test_insert_into_select(self):
        sql = "INSERT INTO target SELECT id FROM source_a JOIN source_b ON source_a.id = source_b.id"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "target" in graph.tables
        assert "source_a" in graph.tables
        assert "source_b" in graph.tables
        table_edges = [e for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE]
        assert len(table_edges) == 2

    def test_create_view(self):
        sql = "CREATE VIEW my_view AS SELECT id FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "my_view" in graph.tables
        assert graph.tables["my_view"].node_type == "view"
        assert "source" in graph.tables

    def test_cte_lineage(self):
        sql = """
        WITH cte AS (SELECT id FROM source)
        CREATE TABLE target AS SELECT * FROM cte
        """
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "target" in graph.tables
        # CTE and/or source should be discovered
        assert len(graph.tables) >= 2

    def test_multiple_joins(self):
        sql = """
        CREATE TABLE result AS
        SELECT a.id, b.name, c.value
        FROM table_a a
        JOIN table_b b ON a.id = b.a_id
        LEFT JOIN table_c c ON a.id = c.a_id
        """
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "result" in graph.tables
        sources = {e.source for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE}
        assert "table_a" in sources
        assert "table_b" in sources
        assert "table_c" in sources

    def test_qualified_table_names(self):
        sql = "CREATE TABLE schema_a.target AS SELECT id FROM schema_b.source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        assert "schema_a.target" in graph.tables
        assert "schema_b.source" in graph.tables

    def test_no_target_select(self):
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        # Standalone SELECT — no target, but sources should be tracked
        assert "users" in graph.tables
        assert "orders" in graph.tables
        table_edges = [e for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE]
        assert len(table_edges) == 0

    def test_source_file_tracking(self):
        sql = "CREATE TABLE target AS SELECT id FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, source_file="my_file.sql", include_columns=False)

        assert graph.tables["target"].source_file == "my_file.sql"


class TestColumnLineage:
    """Test column-level lineage extraction."""

    def test_simple_column_mapping(self):
        sql = "CREATE TABLE target AS SELECT id, name FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=True)

        col_edges = [e for e in graph.edges if e.edge_type == EdgeType.COLUMN_TO_COLUMN]
        assert len(col_edges) >= 2

        targets = {e.target for e in col_edges}
        assert any("id" in t for t in targets)
        assert any("name" in t for t in targets)

    def test_column_alias(self):
        sql = "CREATE TABLE target AS SELECT id AS user_id FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=True)

        col_edges = [e for e in graph.edges if e.edge_type == EdgeType.COLUMN_TO_COLUMN]
        targets = {e.target for e in col_edges}
        assert any("user_id" in t for t in targets)

    def test_column_with_table_reference(self):
        sql = """
        CREATE TABLE target AS
        SELECT a.id, b.name
        FROM table_a a
        JOIN table_b b ON a.id = b.a_id
        """
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=True)

        col_edges = [e for e in graph.edges if e.edge_type == EdgeType.COLUMN_TO_COLUMN]
        # Should have edges from table_a.id -> target.id and table_b.name -> target.name
        assert len(col_edges) >= 2


class TestGraphOperations:
    """Test LineageGraph methods."""

    def test_d3_json_output(self):
        sql = "CREATE TABLE target AS SELECT id FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        d3 = graph.to_d3_json()
        assert "nodes" in d3
        assert "links" in d3
        assert len(d3["nodes"]) >= 2
        assert len(d3["links"]) >= 1

    def test_get_upstream_downstream(self):
        sql = "CREATE TABLE target AS SELECT id FROM source"
        stmts = parse_sql(sql)
        graph = extract_lineage(stmts, include_columns=False)

        upstream = graph.get_upstream("target")
        assert "source" in upstream

        downstream = graph.get_downstream("source")
        assert "target" in downstream

    def test_merge_graphs(self):
        sql1 = "CREATE TABLE mid AS SELECT id FROM source"
        sql2 = "CREATE TABLE target AS SELECT id FROM mid"

        stmts1 = parse_sql(sql1)
        stmts2 = parse_sql(sql2)

        graph1 = extract_lineage(stmts1, include_columns=False)
        graph2 = extract_lineage(stmts2, include_columns=False)

        graph1.merge(graph2)

        assert "source" in graph1.tables
        assert "mid" in graph1.tables
        assert "target" in graph1.tables
        assert len(graph1.edges) == 2
