"""Data models for representing SQL lineage information."""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field


class EdgeType(str, enum.Enum):
    """Type of lineage relationship."""

    TABLE_TO_TABLE = "table_to_table"
    COLUMN_TO_COLUMN = "column_to_column"


class Table(BaseModel):
    """Represents a SQL table or view."""

    name: str
    schema_name: Optional[str] = None
    database: Optional[str] = None
    source_file: Optional[str] = None
    is_cte: bool = False

    @property
    def qualified_name(self) -> str:
        """Full qualified name: database.schema.table."""
        parts = []
        if self.database:
            parts.append(self.database)
        if self.schema_name:
            parts.append(self.schema_name)
        parts.append(self.name)
        return ".".join(parts)

    def __hash__(self) -> int:
        return hash(self.qualified_name.lower())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Table):
            return False
        return self.qualified_name.lower() == other.qualified_name.lower()

    def __str__(self) -> str:
        return self.qualified_name


class Column(BaseModel):
    """Represents a column in a table."""

    name: str
    table: Optional[Table] = None

    @property
    def qualified_name(self) -> str:
        if self.table:
            return f"{self.table.qualified_name}.{self.name}"
        return self.name

    def __hash__(self) -> int:
        return hash(self.qualified_name.lower())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Column):
            return False
        return self.qualified_name.lower() == other.qualified_name.lower()

    def __str__(self) -> str:
        return self.qualified_name


class LineageEdge(BaseModel):
    """A directed lineage relationship between two nodes."""

    source: str  # qualified name of source (table or column)
    target: str  # qualified name of target (table or column)
    edge_type: EdgeType = EdgeType.TABLE_TO_TABLE
    expression: Optional[str] = None  # the SQL expression that created this edge
    source_file: Optional[str] = None

    def __hash__(self) -> int:
        return hash((self.source.lower(), self.target.lower(), self.edge_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LineageEdge):
            return False
        return (
            self.source.lower() == other.source.lower()
            and self.target.lower() == other.target.lower()
            and self.edge_type == other.edge_type
        )


class TableNode(BaseModel):
    """A table node for the graph visualization."""

    id: str
    name: str
    schema_name: Optional[str] = None
    database: Optional[str] = None
    source_file: Optional[str] = None
    is_cte: bool = False
    node_type: str = "table"  # table, view, cte


class ColumnNode(BaseModel):
    """A column node for the graph visualization."""

    id: str
    name: str
    table_id: str


class LineageGraph(BaseModel):
    """Complete lineage graph with nodes and edges."""

    tables: dict[str, TableNode] = Field(default_factory=dict)
    columns: dict[str, ColumnNode] = Field(default_factory=dict)
    edges: list[LineageEdge] = Field(default_factory=list)

    def add_table(self, table: Table, node_type: str = "table") -> str:
        """Add a table node. Returns the node ID."""
        node_id = table.qualified_name.lower()
        if node_id not in self.tables:
            self.tables[node_id] = TableNode(
                id=node_id,
                name=table.name,
                schema_name=table.schema_name,
                database=table.database,
                source_file=table.source_file,
                is_cte=table.is_cte,
                node_type=node_type,
            )
        return node_id

    def add_column(self, column: Column) -> str:
        """Add a column node. Returns the node ID."""
        node_id = column.qualified_name.lower()
        table_id = column.table.qualified_name.lower() if column.table else ""
        if node_id not in self.columns:
            self.columns[node_id] = ColumnNode(
                id=node_id,
                name=column.name,
                table_id=table_id,
            )
        return node_id

    def add_edge(self, edge: LineageEdge) -> None:
        """Add a lineage edge (deduplicated)."""
        if edge not in self.edges:
            self.edges.append(edge)

    def merge(self, other: LineageGraph) -> None:
        """Merge another lineage graph into this one."""
        for table_id, table_node in other.tables.items():
            if table_id not in self.tables:
                self.tables[table_id] = table_node
        for col_id, col_node in other.columns.items():
            if col_id not in self.columns:
                self.columns[col_id] = col_node
        for edge in other.edges:
            self.add_edge(edge)

    def get_upstream(self, node_id: str) -> list[str]:
        """Get all nodes that feed into the given node."""
        return [e.source for e in self.edges if e.target.lower() == node_id.lower()]

    def get_downstream(self, node_id: str) -> list[str]:
        """Get all nodes that the given node feeds into."""
        return [e.target for e in self.edges if e.source.lower() == node_id.lower()]

    def to_d3_json(self) -> dict:
        """Export to D3.js-compatible JSON format."""
        nodes = []
        for table_node in self.tables.values():
            nodes.append(
                {
                    "id": table_node.id,
                    "name": table_node.name,
                    "type": table_node.node_type,
                    "schema": table_node.schema_name,
                    "database": table_node.database,
                    "source_file": table_node.source_file,
                    "is_cte": table_node.is_cte,
                    "level": "table",
                }
            )

        for col_node in self.columns.values():
            nodes.append(
                {
                    "id": col_node.id,
                    "name": col_node.name,
                    "type": "column",
                    "table_id": col_node.table_id,
                    "table": col_node.table_id,  # alias for frontend
                    "level": "column",
                }
            )

        links = []
        for edge in self.edges:
            link_data = {
                "source": edge.source,
                "target": edge.target,
                "type": edge.edge_type.value,
                "expression": edge.expression,
                "source_file": edge.source_file,
            }

            # For column-to-column edges, extract table and column parts
            if edge.edge_type == EdgeType.COLUMN_TO_COLUMN:
                src_parts = edge.source.rsplit(".", 1)
                tgt_parts = edge.target.rsplit(".", 1)
                if len(src_parts) == 2:
                    link_data["source_table"] = src_parts[0]
                    link_data["source_column"] = src_parts[1]
                if len(tgt_parts) == 2:
                    link_data["target_table"] = tgt_parts[0]
                    link_data["target_column"] = tgt_parts[1]

            links.append(link_data)

        return {"nodes": nodes, "links": links}
