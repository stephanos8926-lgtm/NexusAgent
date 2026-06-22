"""Tests for NexusAgent API endpoints."""

import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from nexusagent.server.server import app

# Use a unique test key per test to avoid auth state leakage
_TEST_API_KEY = "test-server-key-2026"


@pytest.fixture(autouse=True)
def _setup_test_auth():
    """Ensure auth manager is initialized with the test key before each test."""
    import secrets as _secrets
    from pathlib import Path as _Path
    from nexusagent.infrastructure.auth import AuthManager, set_auth_manager

    _test_dir = tempfile.mkdtemp()
    _master = _Path(_test_dir) / ".master.secret"
    _salt = _Path(_test_dir) / ".master.salt"
    _keystore = _Path(_test_dir) / "keystore.json"

    _master.write_bytes(b"test-master-secret-for-tests")
    _salt.write_bytes(_secrets.token_bytes(16))

    _auth = AuthManager()
    _auth.master_secret_path = _master
    _auth.salt_path = _salt
    _auth.keystore_path = _keystore
    _auth.initialize_wizard(force=True)
    _auth.save_key("api", _TEST_API_KEY)
    set_auth_manager(_auth)

    yield

    # Cleanup
    import shutil
    shutil.rmtree(_test_dir, ignore_errors=True)


API_HEADERS = {"X-API-Key": _TEST_API_KEY}


@pytest.mark.asyncio
async def test_health_check():
    """Health endpoint should work without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_tasks_requires_auth():
    """GET /tasks without API key should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tasks")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_tasks_with_auth():
    """GET /tasks with API key should return 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tasks", headers=API_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "count" in data


@pytest.mark.asyncio
async def test_list_tasks_with_status_filter():
    """GET /tasks?status=pending should filter by status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tasks", params={"status": "pending"}, headers=API_HEADERS)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancel_task_not_found():
    """POST /tasks/{id}/cancel for nonexistent task should return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks/nonexistent/cancel", headers=API_HEADERS)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_retry_task_not_found():
    """POST /tasks/{id}/retry for nonexistent task should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks/nonexistent/retry", headers=API_HEADERS)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_requires_auth():
    """POST /tasks/{id}/cancel without API key should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks/some-id/cancel")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_workers_endpoint():
    """GET /workers should return circuit breaker state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/workers", headers=API_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "workers" in data
        assert len(data["workers"]) > 0
        worker = data["workers"][0]
        assert "circuit_breakers" in worker
        assert "agent" in worker["circuit_breakers"]
        assert "nats" in worker["circuit_breakers"]


@pytest.mark.asyncio
async def test_tools_endpoint():
    """GET /tools should return registered tools grouped by category."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tools", headers=API_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert data["total"] >= 0
