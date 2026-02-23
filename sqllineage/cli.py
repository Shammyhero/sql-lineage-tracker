"""CLI entry point for SQL Lineage Tracker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqllineage.core.parser import get_supported_dialects
from sqllineage.core.resolver import resolve_files, get_execution_order


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="sqllineage",
        description="SQL Lineage Tracker — Parse SQL files and visualize data lineage.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- analyze command ---
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze SQL files and print lineage",
    )
    analyze_parser.add_argument(
        "files",
        nargs="+",
        type=str,
        help="SQL files to analyze",
    )
    analyze_parser.add_argument(
        "--dialect",
        type=str,
        default=None,
        help=f"SQL dialect. Supported: {', '.join(get_supported_dialects())}",
    )
    analyze_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    analyze_parser.add_argument(
        "--columns",
        action="store_true",
        default=False,
        help="Include column-level lineage",
    )

    # --- serve command ---
    serve_parser = subparsers.add_parser(
        "serve",
        help="Launch the web UI",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )

    # --- dialects command ---
    subparsers.add_parser(
        "dialects",
        help="List supported SQL dialects",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "dialects":
        _cmd_dialects()
    elif args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "serve":
        _cmd_serve(args)


def _cmd_dialects() -> None:
    """List supported dialects."""
    print("Supported SQL dialects:")
    for d in get_supported_dialects():
        print(f"  • {d}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze SQL files and print lineage."""
    file_paths = [Path(f) for f in args.files]

    # Validate files exist
    for fp in file_paths:
        if not fp.exists():
            print(f"Error: File not found: {fp}", file=sys.stderr)
            sys.exit(1)

    graph = resolve_files(
        file_paths,
        dialect=args.dialect,
        include_columns=args.columns,
    )

    if args.format == "json":
        print(json.dumps(graph.to_d3_json(), indent=2))
    else:
        _print_text_report(graph)


def _print_text_report(graph) -> None:
    """Print a human-readable lineage report."""
    print("\n╔══════════════════════════════════════════╗")
    print("║       SQL Lineage Tracker Report         ║")
    print("╚══════════════════════════════════════════╝\n")

    # Tables
    print(f"📊 Tables found: {len(graph.tables)}")
    for table_id, node in sorted(graph.tables.items()):
        type_icon = {"table": "📋", "view": "👁️ ", "cte": "🔄"}.get(node.node_type, "📋")
        src = f" (from {node.source_file})" if node.source_file else ""
        print(f"   {type_icon} {table_id}{src}")

    # Table lineage
    table_edges = [e for e in graph.edges if e.edge_type.value == "table_to_table"]
    if table_edges:
        print(f"\n🔗 Table-level lineage ({len(table_edges)} edges):")
        for edge in table_edges:
            print(f"   {edge.source} ──▶ {edge.target}")

    # Column lineage
    col_edges = [e for e in graph.edges if e.edge_type.value == "column_to_column"]
    if col_edges:
        print(f"\n🔬 Column-level lineage ({len(col_edges)} edges):")
        for edge in col_edges:
            print(f"   {edge.source} ──▶ {edge.target}")

    # Execution order
    order = get_execution_order(graph)
    if order:
        print(f"\n📋 Suggested execution order:")
        for i, table_id in enumerate(order, 1):
            print(f"   {i}. {table_id}")

    print()


def _cmd_serve(args: argparse.Namespace) -> None:
    """Launch the web UI server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required. Install with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    print(f"\n🚀 SQL Lineage Tracker — Web UI")
    print(f"   Open http://{args.host}:{args.port} in your browser\n")

    uvicorn.run(
        "sqllineage.api.server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
