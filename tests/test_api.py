"""Tests for the FastAPI backend."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqllineage.api.server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_dialects():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dialects")
        assert res.status_code == 200
        data = res.json()
        assert "dialects" in data
        assert "postgres" in data["dialects"]


@pytest.mark.anyio
async def test_analyze_single_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sql_content = b"CREATE TABLE target AS SELECT id, name FROM source;"
        files = [("files", ("test.sql", sql_content, "text/plain"))]
        res = await client.post("/api/analyze", files=files, data={"include_columns": "true"})
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "links" in data
        assert "stats" in data
        assert data["stats"]["total_tables"] >= 2


@pytest.mark.anyio
async def test_analyze_multi_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        file1 = b"CREATE TABLE mid AS SELECT id FROM source;"
        file2 = b"CREATE TABLE target AS SELECT id FROM mid;"
        files = [
            ("files", ("file1.sql", file1, "text/plain")),
            ("files", ("file2.sql", file2, "text/plain")),
        ]
        res = await client.post("/api/analyze", files=files, data={"include_columns": "false"})
        assert res.status_code == 200
        data = res.json()
        assert data["stats"]["total_tables"] >= 3
        assert len(data["files"]) == 2


@pytest.mark.anyio
async def test_serve_ui():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "SQL Lineage Tracker" in res.text
