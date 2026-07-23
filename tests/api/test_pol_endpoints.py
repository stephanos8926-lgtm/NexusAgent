# tests/api/test_pol_endpoints.py
"""API and WebSocket integration tests for Phase 7: POL Control Plane."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from nexusagent.core.pol import get_pol_control_plane
from nexusagent.infrastructure.db import get_db_manager
from nexusagent.server.server import app

_TEST_API_KEY = "test-pol-api-key-2026"
_TEST_OPERATOR_KEY = "operator-key-pol-123"
API_HEADERS = {"X-API-Key": _TEST_API_KEY}


@pytest.fixture(autouse=True)
async def _setup_test_db():
    """Initialize test database before each test."""
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
    import secrets
    from pathlib import Path

    from nexusagent.infrastructure.auth import AuthManager, set_auth_manager

    _test_dir = tempfile.mkdtemp()
    _master = Path(_test_dir) / ".master.secret"
    _salt = Path(_test_dir) / ".master.salt"
    _keystore = Path(_test_dir) / "keystore.json"

    _master.write_bytes(b"test-master-secret-for-tests-pol")
    _salt.write_bytes(secrets.token_bytes(16))

    _auth = AuthManager()
    _auth.master_secret_path = _master
    _auth.salt_path = _salt
    _auth.keystore_path = _keystore
    _auth.initialize_wizard(force=True)
    _auth.save_key("api", _TEST_API_KEY)
    set_auth_manager(_auth)

    # Set operator keys env var
    os.environ["NEXUS_AUTH_OPERATOR_KEYS"] = _TEST_OPERATOR_KEY

    yield

    # Cleanup
    import shutil
    shutil.rmtree(_test_dir, ignore_errors=True)
    if "NEXUS_AUTH_OPERATOR_KEYS" in os.environ:
        del os.environ["NEXUS_AUTH_OPERATOR_KEYS"]


@pytest.mark.asyncio
async def test_get_interventions_requires_auth():
    """GET /pol/interventions without API key should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/pol/interventions")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_interventions_operator_allowed():
    """GET /pol/interventions with Operator key should return 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/pol/interventions",
            headers={"X-API-Key": _TEST_OPERATOR_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert "interventions" in data
        assert "count" in data


@pytest.mark.asyncio
async def test_create_intervention_admin_only():
    """POST /pol/interventions should be forbidden for Operators, allowed for Admins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Operator attempt (Should return 403)
        response = await client.post(
            "/pol/interventions",
            json={
                "task_id": "task-test-123",
                "reason": "resource_exhaustion",
                "guidance": "Restart components",
                "priority": "high",
            },
            headers={"X-API-Key": _TEST_OPERATOR_KEY}
        )
        assert response.status_code == 403

        # 2. Admin attempt (Should succeed 201)
        response = await client.post(
            "/pol/interventions",
            json={
                "task_id": "task-test-123",
                "reason": "resource_exhaustion",
                "guidance": "Restart components",
                "priority": "high",
            },
            headers=API_HEADERS
        )
        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "task-test-123"
        assert data["reason"] == "resource_exhaustion"
        assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_resolve_intervention_admin_only():
    """POST /pol/interventions/{id}/resolve should be forbidden for Operators, allowed for Admins."""
    # Create an intervention directly in the control plane
    pol = get_pol_control_plane()
    intv = await pol.create_intervention(
        task_id="task-xyz",
        reason="repeated_tool_failure",
        guidance="Debug MCP connectivity",
        priority="high"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Operator attempt to resolve (Should return 403)
        response = await client.post(
            f"/pol/interventions/{intv['id']}/resolve",
            json={"action": "retry"},
            headers={"X-API-Key": _TEST_OPERATOR_KEY}
        )
        assert response.status_code == 403

        # 2. Admin attempt to resolve (Should succeed 200)
        response = await client.post(
            f"/pol/interventions/{intv['id']}/resolve",
            json={"action": "retry"},
            headers=API_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["action"] == "retry"


def test_pol_websocket_connection():
    """Test WebSocket auth and streaming for POL interventions."""
    client = TestClient(app)

    # 1. Connecting without token/key should fail
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/pol"):
            pass

    # 2. Connecting with valid token should succeed
    with client.websocket_connect(f"/ws/pol?token={_TEST_API_KEY}") as ws:
        # Create an intervention to trigger a broadcast event
        import asyncio
        pol = get_pol_control_plane()
        asyncio.run(pol.create_intervention(
            task_id="task-ws",
            reason="policy_violation",
            guidance="Warn agent",
            priority="low"
        ))

        # Receive WebSocket broadcast
        msg = ws.receive_json()
        assert msg["task_id"] == "task-ws"
        assert msg["reason"] == "policy_violation"
        assert msg["status"] == "pending"
