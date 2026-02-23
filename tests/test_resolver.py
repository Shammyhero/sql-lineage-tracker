"""Tests for the multi-file resolver module."""

import pytest
import tempfile
from pathlib import Path
from sqllineage.core.resolver import resolve_files, resolve_sql_strings, get_execution_order
from sqllineage.core.models import EdgeType


class TestResolveFiles:
    """Test multi-file resolution."""

    def test_cross_file_lineage(self, tmp_path):
        """Two files where file2 reads from a table created in file1."""
        file1 = tmp_path / "01_create.sql"
        file1.write_text("CREATE TABLE staging.users AS SELECT id, name FROM raw.users;")

        file2 = tmp_path / "02_transform.sql"
        file2.write_text("CREATE TABLE mart.user_summary AS SELECT id FROM staging.users;")

        graph = resolve_files([file1, file2], include_columns=False)

        assert "raw.users" in graph.tables
        assert "staging.users" in graph.tables
        assert "mart.user_summary" in graph.tables

        # Check cross-file edge: staging.users -> mart.user_summary
        edges = [e for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE]
        targets = {(e.source, e.target) for e in edges}
        assert ("staging.users", "mart.user_summary") in targets

    def test_multiple_files_merge(self, tmp_path):
        """Three files forming a pipeline."""
        (tmp_path / "01.sql").write_text("CREATE TABLE a AS SELECT * FROM raw;")
        (tmp_path / "02.sql").write_text("CREATE TABLE b AS SELECT * FROM a;")
        (tmp_path / "03.sql").write_text("CREATE TABLE c AS SELECT * FROM b JOIN a ON b.id = a.id;")

        files = sorted(tmp_path.glob("*.sql"))
        graph = resolve_files(files, include_columns=False)

        assert len(graph.tables) == 4  # raw, a, b, c
        table_edges = [e for e in graph.edges if e.edge_type == EdgeType.TABLE_TO_TABLE]
        assert len(table_edges) == 4  # raw->a, a->b, b->c, a->c

    def test_source_file_names(self, tmp_path):
        """Check source file names are tracked correctly."""
        file1 = tmp_path / "pipeline.sql"
        file1.write_text("CREATE TABLE target AS SELECT id FROM source;")

        graph = resolve_files([file1], include_columns=False)

        assert graph.tables["target"].source_file == "pipeline.sql"

    def test_error_handling(self, tmp_path):
        """Files with invalid SQL should not crash the resolver."""
        file1 = tmp_path / "good.sql"
        file1.write_text("CREATE TABLE good AS SELECT id FROM source;")

        file2 = tmp_path / "bad.sql"
        file2.write_text("THIS IS NOT VALID SQL AT ALL !!!")

        # Should not raise
        graph = resolve_files([file1, file2], include_columns=False)
        assert "good" in graph.tables


class TestResolveSQLStrings:
    """Test resolve_sql_strings function."""

    def test_string_input(self):
        sql_strings = [
            ("file1.sql", "CREATE TABLE mid AS SELECT id FROM source;"),
            ("file2.sql", "CREATE TABLE target AS SELECT id FROM mid;"),
        ]
        graph = resolve_sql_strings(sql_strings, include_columns=False)

        assert "source" in graph.tables
        assert "mid" in graph.tables
        assert "target" in graph.tables


class TestExecutionOrder:
    """Test topological sort of table dependencies."""

    def test_simple_chain(self):
        sql_strings = [
            ("f1.sql", "CREATE TABLE b AS SELECT * FROM a;"),
            ("f2.sql", "CREATE TABLE c AS SELECT * FROM b;"),
        ]
        graph = resolve_sql_strings(sql_strings, include_columns=False)
        order = get_execution_order(graph)

        # 'a' should come before 'b', 'b' before 'c'
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_diamond_dependency(self):
        sql_strings = [
            ("f1.sql", "CREATE TABLE b AS SELECT * FROM a;"),
            ("f2.sql", "CREATE TABLE c AS SELECT * FROM a;"),
            ("f3.sql", "CREATE TABLE d AS SELECT * FROM b JOIN c ON b.id = c.id;"),
        ]
        graph = resolve_sql_strings(sql_strings, include_columns=False)
        order = get_execution_order(graph)

        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")
