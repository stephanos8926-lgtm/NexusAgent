from pathlib import Path

# Load .env from project root so API keys are available for all tests
# Use override=False so test-specific env vars take precedence
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    _env = Path(__file__).parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=False)
except ImportError:
    pass

# Initialize auth keystore for tests
# The fail-closed auth requires a valid keystore. Create one for tests.
import os
import tempfile
from pathlib import Path as _Path
from nexusagent.auth import AuthManager

_test_auth_dir = tempfile.mkdtemp()
_test_master = _Path(_test_auth_dir) / ".master.secret"
_test_salt = _Path(_test_auth_dir) / ".master.salt"
_test_keystore = _Path(_test_auth_dir) / "keystore.json"

# Generate test secrets
_test_master.write_bytes(b"test-master-secret-for-tests-only")
import secrets as _secrets
_test_salt.write_bytes(_secrets.token_bytes(16))

# Create auth manager with test paths and save test API keys
_test_auth = AuthManager()
# Override paths before initialization
_test_auth.master_secret_path = _test_master
_test_auth.salt_path = _test_salt
_test_auth.keystore_path = _test_keystore
_test_auth.initialize_wizard(force=True)
_test_auth.save_key("api", "test-key")

# Patch the global auth_manager to use test keystore
import nexusagent.auth as _auth_module
_auth_module.auth_manager = _test_auth

# Initialize test database for server/session tests that need it
import asyncio as _asyncio
from nexusagent.db import DatabaseManager as _DBM

async def _init_test_db():
    _db = _DBM("data/nexus.db")
    await _db.init_db()

_asyncio.run(_init_test_db())
