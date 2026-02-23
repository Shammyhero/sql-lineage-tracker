# 🔗 SQL Lineage Tracker

**Parse SQL files. Extract data lineage. Visualize the flow.**

A beautiful, open-source Python tool that parses SQL files, extracts table & column-level lineage across multiple files, and renders an interactive graph in your browser.

---

## ✨ Features

- **20+ SQL Dialects** — PostgreSQL, MySQL, BigQuery, Snowflake, Spark, and more (powered by [sqlglot](https://github.com/tobymao/sqlglot))
- **Complex SQL Support** — CTEs, subqueries, JOINs, UNIONs, MERGE, window functions
- **Multi-File Resolution** — Upload interdependent SQL files and see cross-file lineage
- **Table & Column Lineage** — Track dependencies at both table and column level
- **Column Transformations** — See exactly how each column is derived (e.g., `SUM(amount)`, `LOWER(TRIM(email))`)
- **Interactive Graph** — Hierarchical DAG layout with zoom, pan, search, and click-to-highlight
- **Upstream/Downstream Tracing** — Click any node to trace its full lineage path
- **Export** — Download lineage as PNG image or JSON data
- **CLI & Web UI** — Use from the terminal or launch a gorgeous dark-mode web interface
- **Execution Order** — Automatic topological sort of table dependencies

## 🚀 Quick Start

### Install from PyPI

```bash
pip install sqllineage-tracker
```

### Install from Source

```bash
git clone https://github.com/Shammyhero/sql-lineage-tracker.git
cd sql-lineage-tracker
pip install -e .
```

### Launch the Web UI

```bash
sqllineage serve
```

Then open [http://localhost:8000](http://localhost:8000) in your browser, upload your SQL files, and click **Analyze Lineage**.

### CLI Usage

```bash
# Analyze SQL files
sqllineage analyze examples/ecommerce/*.sql

# JSON output
sqllineage analyze examples/ecommerce/*.sql --format json

# With column-level lineage
sqllineage analyze examples/ecommerce/*.sql --columns

# Specify dialect
sqllineage analyze my_query.sql --dialect bigquery

# List supported dialects
sqllineage dialects
```

### Use as a Library

```python
from sqllineage import resolve_files

graph = resolve_files(["file1.sql", "file2.sql"], dialect="postgres")

# Get D3.js-compatible JSON
data = graph.to_d3_json()

# Explore lineage
print(graph.get_upstream("mart.user_summary"))
print(graph.get_downstream("raw.users"))
```

## 🏗️ Project Structure

```
sql-lineage-tracker/
├── sqllineage/
│   ├── core/
│   │   ├── models.py        # Table, Column, LineageEdge, LineageGraph
│   │   ├── parser.py        # sqlglot wrapper (20+ dialects)
│   │   ├── extractor.py     # AST → lineage edges
│   │   └── resolver.py      # Multi-file resolution + topo sort
│   ├── api/
│   │   └── server.py        # FastAPI backend
│   ├── web/
│   │   ├── index.html        # Web UI
│   │   ├── styles.css        # Dark mode + glassmorphism
│   │   └── app.js            # D3.js hierarchical DAG
│   └── cli.py                # CLI entry point
├── tests/                     # pytest test suite
├── examples/                  # Sample SQL pipelines
├── pyproject.toml
└── LICENSE                    # MIT
```

## 🧪 Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Build the package
python -m build

# Check the package
twine check dist/*
```

## 📜 License

MIT — see [LICENSE](LICENSE).
