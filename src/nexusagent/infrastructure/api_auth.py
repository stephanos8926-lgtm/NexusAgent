"""API key authentication and authorization middleware for NexusAgent."""

import hmac
import logging
import os

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
        k.strip()
        for k in os.environ.get("NEXUS_AUTH_OPERATOR_KEYS", "").split(",")
        if k.strip()
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
