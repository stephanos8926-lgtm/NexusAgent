"""API key authentication middleware for NexusAgent."""

import logging

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from header against the auth keystore."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Try to validate against the keystore if auth is initialized
    try:
        from nexusagent.auth import auth_manager

        stored_key = auth_manager.get_key("api")
        if stored_key is not None:
            if api_key != stored_key:
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
        )
    except HTTPException:
        raise  # Re-raise our own 401s
    except Exception as e:
        # Any other auth system error — fail closed
        logger.error(f"Auth system error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication system error",
        )
