"""FastAPI backend for the SQL Lineage Tracker web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from sqllineage.core.parser import get_supported_dialects
from sqllineage.core.resolver import resolve_sql_strings, get_execution_order

# Path to the bundled web UI files
WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(
    title="SQL Lineage Tracker",
    description="Parse SQL files and visualize data lineage",
    version="0.1.0",
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main web UI."""
    index_path = WEB_DIR / "index.html"
    return FileResponse(index_path, media_type="text/html")


@app.get("/styles.css")
async def serve_css():
    """Serve the CSS file."""
    css_path = WEB_DIR / "styles.css"
    return FileResponse(css_path, media_type="text/css")


@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_path = WEB_DIR / "app.js"
    return FileResponse(js_path, media_type="application/javascript")


@app.get("/api/dialects")
async def list_dialects():
    """Return the list of supported SQL dialects."""
    return {"dialects": get_supported_dialects()}


@app.post("/api/analyze")
async def analyze(
    files: list[UploadFile] = File(...),
    dialect: Optional[str] = Form(""),
    include_columns: str = Form("true"),
):
    """Analyze uploaded SQL files and return lineage data.

    Accepts multiple SQL file uploads and returns a unified lineage graph
    in D3.js-compatible JSON format.
    """
    # Parse form data
    resolved_dialect = dialect.strip() if dialect else None
    if not resolved_dialect:
        resolved_dialect = None
    columns_flag = include_columns.lower() in ("true", "1", "yes", "on")

    sql_strings: list[tuple[str, str]] = []

    for upload_file in files:
        content = await upload_file.read()
        sql_content = content.decode("utf-8")
        file_name = upload_file.filename or "unknown.sql"
        sql_strings.append((file_name, sql_content))

    # Resolve cross-file lineage
    graph = resolve_sql_strings(
        sql_strings,
        dialect=resolved_dialect,
        include_columns=columns_flag,
    )

    # Get execution order
    exec_order = get_execution_order(graph)

    # Build response
    d3_data = graph.to_d3_json()
    d3_data["execution_order"] = exec_order
    d3_data["files"] = [name for name, _ in sql_strings]
    d3_data["stats"] = {
        "total_tables": len(graph.tables),
        "total_columns": len(graph.columns),
        "total_edges": len(graph.edges),
        "table_edges": len([e for e in graph.edges if e.edge_type.value == "table_to_table"]),
        "column_edges": len([e for e in graph.edges if e.edge_type.value == "column_to_column"]),
    }

    return d3_data
