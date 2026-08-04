"""API key authentication and authorization middleware for NexusAgent."""

import hmac
import json
import logging
import os
import time

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Admin API key — the primary key from the keystore has full access
# Additional operator keys can be set via NEXUS_AUTH_OPERATOR_KEYS (comma-separated)
# NOTE: Read dynamically at call time to support test environment overrides
def _get_operator_keys() -> set[str]:
    """Get current operator keys from environment."""
    return {
        k.strip() for k in os.environ.get("NEXUS_AUTH_OPERATOR_KEYS", "").split(",") if k.strip()
    }


def _classify_key(api_key: str) -> str:
    """Classify an API key as 'admin' or 'operator'.

    The admin key is the one stored in the Fernet keystore.
    Operator keys are configured via NEXUS_AUTH_OPERATOR_KEYS env var.
    """
    if api_key in _get_operator_keys():
        return "operator"
    return "admin"  # keystore key is always admin


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from header against the auth keystore or operator keys.

    Uses constant-time comparison to prevent timing attacks.
    Returns the API key if valid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Check operator keys first (constant-time via set membership)
    if api_key in _get_operator_keys():
        return api_key

    # Try to validate against the keystore
    try:
        from nexusagent.infrastructure.auth import get_auth_manager

        stored_key = get_auth_manager().get_key("api")
        if stored_key is not None:
            if not hmac.compare_digest(api_key, stored_key):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                )
            return api_key
        # Keystore initialized but no API key configured — fail closed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key not configured",
        )
    except FileNotFoundError:
        # Auth not initialized — fail closed
        logger.warning("Auth keystore not found — rejecting all requests")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication not configured",
        ) from None
    except HTTPException:
        raise  # Re-raise our own 401s
    except Exception as e:
        # Any other auth system error — fail closed
        logger.error(f"Auth system error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication system error",
        ) from e


async def require_admin(api_key: str = Security(api_key_header)) -> str:
    """Dependency: require admin role.

    Use on endpoints that modify state (task submission, worker management, etc.).
    Operator keys are rejected with 403.
    """
    # First verify the key is valid
    verified_key = await verify_api_key(api_key)
    # Then check role
    role = _classify_key(verified_key)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return verified_key


# ── Short-lived WebSocket tokens ──────────────────────────────────────────────

# Default TTL for exchange tokens issued to browser WebSocket clients.
_SHORT_TOKEN_TTL_SECONDS = 300


def _get_fernet() -> "Fernet":
    """Get the Fernet instance derived from the master secret.

    Imported lazily so auth.py (which imports api_auth indirectly via
    settings) does not create a circular import at module load time.
    """
    from nexusagent.infrastructure.auth import get_auth_manager

    return get_auth_manager()._get_fernet()


def create_short_lived_token(api_key: str, ttl_seconds: int = _SHORT_TOKEN_TTL_SECONDS) -> str:
    """Create a short-lived, signed token for a verified API key.

    The token is a Fernet-encrypted JSON payload containing the API key and
    an absolute expiry timestamp. It is NOT the API key itself — the key is
    only recoverable server-side (Fernet uses the master secret), so a leaked
    token cannot be used to authenticate after it expires.
    """
    payload = json.dumps(
        {"key": api_key, "exp": int(time.time()) + ttl_seconds}
    ).encode()
    return _get_fernet().encrypt(payload).decode()


def resolve_short_lived_token(token: str) -> str | None:
    """Resolve a short-lived token back to its API key.

    Returns the embedded API key if the token is valid and unexpired,
    otherwise None. Decryption failure (tampered/forged token) and expiry
    both yield None — callers must treat None as authentication failure.
    """
    try:
        raw = _get_fernet().decrypt(token.encode())
        payload = json.loads(raw.decode())
        if int(payload["exp"]) < int(time.time()):
            return None  # expired
        key = payload.get("key")
        return key if isinstance(key, str) and key else None
    except Exception:
        return None
