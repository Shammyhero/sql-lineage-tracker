"""SQL parser module — wraps sqlglot for multi-dialect SQL parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import sqlglot
from sqlglot import exp


# Map user-friendly dialect names to sqlglot dialect identifiers
SUPPORTED_DIALECTS: dict[str, str] = {
    "ansi": "ansi",
    "bigquery": "bigquery",
    "clickhouse": "clickhouse",
    "databricks": "databricks",
    "duckdb": "duckdb",
    "hive": "hive",
    "mysql": "mysql",
    "oracle": "oracle",
    "postgres": "postgres",
    "presto": "presto",
    "redshift": "redshift",
    "snowflake": "snowflake",
    "spark": "spark",
    "sqlite": "sqlite",
    "starrocks": "starrocks",
    "tableau": "tableau",
    "teradata": "teradata",
    "trino": "trino",
    "tsql": "tsql",
}


def get_supported_dialects() -> list[str]:
    """Return a sorted list of supported SQL dialect names."""
    return sorted(SUPPORTED_DIALECTS.keys())


def parse_sql(
    sql: str,
    dialect: Optional[str] = None,
) -> list[exp.Expression]:
    """Parse a SQL string into a list of sqlglot AST expressions.

    Args:
        sql: The SQL string to parse.
        dialect: SQL dialect (e.g., 'postgres', 'bigquery'). None = auto-detect.

    Returns:
        A list of parsed sqlglot Expression objects.

    Raises:
        sqlglot.errors.ParseError: If the SQL cannot be parsed.
    """
    resolved_dialect = None
    if dialect:
        dialect_lower = dialect.lower()
        resolved_dialect = SUPPORTED_DIALECTS.get(dialect_lower, dialect_lower)

    try:
        statements = sqlglot.parse(sql, dialect=resolved_dialect, error_level=sqlglot.ErrorLevel.WARN)
    except Exception:
        # Fallback: try without dialect
        statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.WARN)

    # Filter out None results (can happen with empty statements)
    return [stmt for stmt in statements if stmt is not None]


def parse_file(
    file_path: str | Path,
    dialect: Optional[str] = None,
) -> list[exp.Expression]:
    """Parse a SQL file into a list of sqlglot AST expressions.

    Args:
        file_path: Path to the SQL file.
        dialect: SQL dialect (e.g., 'postgres', 'bigquery'). None = auto-detect.

    Returns:
        A list of parsed sqlglot Expression objects.
    """
    path = Path(file_path)
    sql_content = path.read_text(encoding="utf-8")
    return parse_sql(sql_content, dialect=dialect)
