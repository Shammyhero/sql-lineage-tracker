"""Tests for the SQL parser module."""

import pytest
from sqllineage.core.parser import parse_sql, parse_file, get_supported_dialects
from sqlglot import exp


class TestParseSQL:
    """Test parse_sql function."""

    def test_simple_select(self):
        stmts = parse_sql("SELECT id, name FROM users")
        assert len(stmts) == 1
        assert isinstance(stmts[0], exp.Select)

    def test_multiple_statements(self):
        sql = """
        SELECT * FROM users;
        SELECT * FROM orders;
        """
        stmts = parse_sql(sql)
        assert len(stmts) == 2

    def test_create_table_as(self):
        sql = "CREATE TABLE new_table AS SELECT id FROM old_table"
        stmts = parse_sql(sql)
        assert len(stmts) == 1
        assert isinstance(stmts[0], exp.Create)

    def test_insert_into_select(self):
        sql = "INSERT INTO target SELECT id, name FROM source"
        stmts = parse_sql(sql)
        assert len(stmts) == 1
        assert isinstance(stmts[0], exp.Insert)

    def test_create_view(self):
        sql = "CREATE VIEW my_view AS SELECT id FROM users"
        stmts = parse_sql(sql)
        assert len(stmts) == 1

    def test_cte_query(self):
        sql = """
        WITH active_users AS (
            SELECT id, name FROM users WHERE is_active = true
        )
        SELECT * FROM active_users
        """
        stmts = parse_sql(sql)
        assert len(stmts) == 1

    def test_complex_joins(self):
        sql = """
        SELECT o.id, c.name, p.product_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN products p ON o.product_id = p.id
        WHERE o.status = 'ACTIVE'
        """
        stmts = parse_sql(sql)
        assert len(stmts) == 1

    def test_subquery(self):
        sql = """
        SELECT *
        FROM (SELECT id, name FROM users WHERE is_active = true) sub
        JOIN orders ON sub.id = orders.user_id
        """
        stmts = parse_sql(sql)
        assert len(stmts) == 1

    def test_dialect_postgres(self):
        sql = "SELECT id::TEXT FROM users"
        stmts = parse_sql(sql, dialect="postgres")
        assert len(stmts) == 1

    def test_dialect_bigquery(self):
        sql = "SELECT * FROM `project.dataset.table`"
        stmts = parse_sql(sql, dialect="bigquery")
        assert len(stmts) == 1

    def test_empty_sql(self):
        stmts = parse_sql("")
        assert len(stmts) == 0

    def test_union(self):
        sql = """
        SELECT id, name FROM users
        UNION ALL
        SELECT id, name FROM admins
        """
        stmts = parse_sql(sql)
        assert len(stmts) == 1


class TestSupportedDialects:
    """Test dialect listing."""

    def test_dialects_not_empty(self):
        dialects = get_supported_dialects()
        assert len(dialects) > 0

    def test_common_dialects_present(self):
        dialects = get_supported_dialects()
        for d in ["postgres", "mysql", "bigquery", "snowflake"]:
            assert d in dialects
