"""Tests for NexusAgent API endpoints."""

import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from nexusagent.infrastructure.db import get_db_manager
from nexusagent.server.server import app

# Use a unique test key per test to avoid auth state leakage
_TEST_API_KEY = "test-server-key-2026"


@pytest.fixture(autouse=True)
async def _setup_test_db():
    """Initialize test database before each test."""
    import tempfile

    # Use a temporary database for tests
    test_db = tempfile.mktemp(suffix=".db")
    db_manager = get_db_manager()
    db_manager.reinit(test_db)
    await db_manager.init_db()

    yield

    # Cleanup
    import os
    for suffix in ["", "-shm", "-wal"]:
        p = test_db + suffix
        if os.path.exists(p):
            os.remove(p)


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
async def test_operator_key_rejected_from_admin_endpoints():
    """Operator keys (NEXUS_AUTH_OPERATOR_KEYS) should be rejected from admin-only endpoints."""
    import os
    os.environ["NEXUS_AUTH_OPERATOR_KEYS"] = "operator-key-123"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # POST /tasks should require admin — operator key must be rejected
            response = await client.post(
                "/tasks",
                json={"description": "test", "priority": 1},
                headers={"X-API-Key": "operator-key-123"},
            )
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"

            # POST /tasks/{id}/cancel should require admin
            response = await client.post(
                "/tasks/some-id/cancel",
                headers={"X-API-Key": "operator-key-123"},
            )
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"

            # POST /tasks/{id}/retry should require admin
            response = await client.post(
                "/tasks/some-id/retry",
                headers={"X-API-Key": "operator-key-123"},
            )
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    finally:
        del os.environ["NEXUS_AUTH_OPERATOR_KEYS"]


@pytest.mark.asyncio
async def test_operator_key_allowed_on_read_endpoints():
    """Operator keys should be allowed on read-only endpoints (status, result, list)."""
    import os
    os.environ["NEXUS_AUTH_OPERATOR_KEYS"] = "operator-key-456"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /tasks/{id}/status — operator allowed
            response = await client.get(
                "/tasks/some-id/status",
                headers={"X-API-Key": "operator-key-456"},
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            # GET /tasks/{id}/result — operator allowed
            from unittest.mock import AsyncMock, patch
            with patch("nexusagent.server.routes.sdk.get_result", new_callable=AsyncMock) as mock_get_result:
                mock_get_result.return_value = None
                response = await client.get(
                    "/tasks/some-id/result",
                    headers={"X-API-Key": "operator-key-456"},
                )
            # 404 is fine — we're testing auth, not task existence
            assert response.status_code in (200, 404), f"Expected 200/404, got {response.status_code}"

            # GET /tasks — operator allowed
            response = await client.get(
                "/tasks",
                headers={"X-API-Key": "operator-key-456"},
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            # GET /workers — operator allowed
            response = await client.get(
                "/workers",
                headers={"X-API-Key": "operator-key-456"},
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    finally:
        del os.environ["NEXUS_AUTH_OPERATOR_KEYS"]


@pytest.mark.asyncio
async def test_admin_key_allowed_on_all_endpoints():
    """Admin key (keystore key) should be allowed on both admin and read endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /tasks — admin allowed
        response = await client.post(
            "/tasks",
            json={"description": "test admin", "priority": 1},
            headers=API_HEADERS,
        )
        # 200 or 503 (NATS unavailable) — both mean auth passed
        assert response.status_code in (200, 503), f"Expected 200/503, got {response.status_code}"

        # GET /tasks — admin allowed
        response = await client.get("/tasks", headers=API_HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # POST /tasks/{id}/cancel — admin allowed
        response = await client.post("/tasks/some-id/cancel", headers=API_HEADERS)
        # 400 is fine (task not found), means auth passed
        assert response.status_code in (200, 400), f"Expected 200/400, got {response.status_code}"
