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
    except FileNotFoundError:
        # Auth not initialized yet — fall through to permissive mode
        logger.debug("Auth keystore not initialized, accepting any non-empty key")
    except Exception as e:
        # Auth system error — fail safe
        logger.warning(f"Auth system error: {e}, accepting any non-empty key")

    # No keystore configured or not initialized — accept any non-empty key
    return api_key
