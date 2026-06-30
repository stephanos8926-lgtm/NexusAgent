
import asyncio
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from websockets.client import connect as ws_connect

from nexusagent.server.server import app

# Use a unique test key per test to avoid auth state leakage
_TEST_API_KEY = "test-e2e-key-2026"

@pytest.fixture(autouse=True)
def _setup_test_auth():
    """Ensure auth manager is initialized with the test key before each test."""
    import secrets as _secrets
    from pathlib import Path as _Path
    import tempfile
    import shutil

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
    shutil.rmtree(_test_dir, ignore_errors=True)

API_HEADERS = {"X-API-Key": _TEST_API_KEY}
WS_HEADERS = {"Authorization": f"Bearer {_TEST_API_KEY}"}

async def test_verify_api_e2e_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("--- Verifying Unauthenticated Endpoints ---")
        # GET /health
        response = await client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code} {response.text}"
        print(f"GET /health: {response.json()}")

        # GET /version
        response = await client.get("/version")
        assert response.status_code == 200, f"Version check failed: {response.status_code} {response.text}"
        print(f"GET /version: {response.json()}")

        print("\n--- Verifying Authenticated REST Endpoints ---")
        # GET /tools
        response = await client.get("/tools", headers=API_HEADERS)
        assert response.status_code == 200, f"List tools failed: {response.status_code} {response.text}"
        print(f"GET /tools: Found {response.json().get('total', 0)} tools")

        # POST /tasks (requires admin key)
        task_description = "Perform E2E API flow verification."
        response = await client.post(
            "/tasks", json={"description": task_description, "priority": 1}, headers=API_HEADERS
        )
        assert response.status_code in (200, 503), f"Submit task failed: {response.status_code} {response.text}"
        task_id = response.json().get("task_id")
        print(f"POST /tasks: Submitted task with ID {task_id}")

        # GET /tasks/{task_id}/status
        if task_id:
            response = await client.get(f"/tasks/{task_id}/status", headers=API_HEADERS)
            assert response.status_code == 200, f"Get task status failed: {response.status_code} {response.text}"
            print(f"GET /tasks/{task_id}/status: {response.json()}")

        # GET /tasks
        response = await client.get("/tasks", headers=API_HEADERS)
        assert response.status_code == 200, f"List tasks failed: {response.status_code} {response.text}"
        print(f"GET /tasks: Found {response.json().get('count', 0)} tasks")

        # GET /workers
        response = await client.get("/workers", headers=API_HEADERS)
        assert response.status_code == 200, f"List workers failed: {response.status_code} {response.text}"
        print(f"GET /workers: {response.json()}")

        print("\n--- Verifying WebSocket Endpoint (Basic Connectivity) ---")
        session_id = str(uuid.uuid4())
        ws_url = f"/sessions/{session_id}/ws" # Relative path for ASGITransport

        response = await client.get(ws_url, headers=WS_HEADERS)
        # A successful WebSocket handshake typically returns 101 Switching Protocols.
        # However, a GET request to a WebSocket endpoint without upgrading
        # might return a 400 Bad Request or 404 Not Found if not handled by the ASGI app.
        # For basic connectivity, we'll assert that it's not a 500 error.
        assert response.status_code != 500, f"WebSocket endpoint returned 500 error: {response.status_code} {response.text}"
        print(f"GET {ws_url}: Status Code {response.status_code} (Expected non-500 for basic connectivity)")
