# src/nexusagent/server/routes.py
"""REST API routes for the NexusAgent platform."""

import logging
import time

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from nexusagent.infrastructure.api_auth import require_admin, verify_api_key
from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.db import get_task_repo
from nexusagent.infrastructure.rate_limit import check_rate_limit
from nexusagent.llm.models import TaskStatus
from nexusagent.server.sdk import sdk
from nexusagent.tools.registry import list_all_tools
from nexusagent.version import MIN_CLIENT_VERSION, VERSION

logger = logging.getLogger(__name__)

# Module-level start time for uptime calculation (independent of server.py to avoid circular imports)
_VERSION_START_TIME = time.monotonic()


class SubmitTaskRequest(BaseModel):
    """Request body for submitting a new task to the orchestrator."""

    description: str = Field(..., max_length=10000, description="Task description (max 10K chars)")
    priority: int = Field(default=1, ge=1, le=10)
    metadata: dict = Field(default_factory=dict)


def register_routes(app: FastAPI) -> None:
    """Register all REST API routes on the given FastAPI app."""

    # ─── Rate Limiting Middleware ────────────────────────────────────────

    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        """Apply rate limiting to all API endpoints."""
        # Skip rate limiting for health/version endpoints
        if request.url.path in ("/health", "/version") or request.url.path.startswith("/sessions/"):
            return await call_next(request)

        # Identify client by API key header or fallback to client IP
        # Use X-Forwarded-For when behind a reverse proxy (nginx, Cloudflare, k8s ingress)
        xff = request.headers.get("x-forwarded-for", "")
        client_ip = xff.split(",")[0].strip() if xff else request.client.host
        client_id = request.headers.get("x-api-key") or client_ip

        allowed, headers = await check_rate_limit(client_id)
        if not allowed:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    # ─── Task Submission ────────────────────────────────────────────────

    @app.post("/tasks", response_model=dict, dependencies=[Depends(require_admin)])
    async def create_task(request: SubmitTaskRequest):
        """Submit a new task to the orchestrator."""
        try:
            import uuid

            task_repo = get_task_repo()
            task_id = str(uuid.uuid4())

            # Create task in DB first
            await task_repo.create_task(
                task_id=task_id,
                description=request.description,
                priority=request.priority,
                metadata=request.metadata,
            )

            # Publish to NATS — with retry on failure
            nats_error = None
            for attempt in range(3):
                try:
                    await sdk.submit_task(
                        {
                            "id": task_id,
                            "description": request.description,
                            "priority": request.priority,
                            "metadata": request.metadata,
                        }
                    )
                    nats_error = None
                    break
                except Exception as nats_exc:
                    nats_error = nats_exc
                    logger.warning("NATS publish attempt %d failed: %s", attempt + 1, nats_exc)
                    if attempt < 2:
                        import asyncio

                        await asyncio.sleep(0.5 * (attempt + 1))

            if nats_error:
                await task_repo.update_task_status(task_id, TaskStatus.FAILED)
                logger.error("Task %s: NATS publish failed after 3 attempts", task_id)
                raise HTTPException(
                    status_code=503,
                    detail="Task queue unavailable. Please try again later.",
                ) from nats_error

            await task_repo.update_task_status(task_id, TaskStatus.PENDING)
            return {"task_id": task_id, "status": "submitted"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error submitting task: %s", type(e).__name__)
            raise HTTPException(status_code=500, detail="Internal server error") from e

    # ─── Task Status ────────────────────────────────────────────────────

    @app.get("/tasks/{task_id}/status", dependencies=[Depends(verify_api_key)])
    async def get_task_status(task_id: str):
        """Check the status of a task."""
        status = await sdk.get_task_status(task_id)
        return {"task_id": task_id, "status": status}

    # ─── Task Result ────────────────────────────────────────────────────

    @app.get("/tasks/{task_id}/result", dependencies=[Depends(verify_api_key)])
    async def get_task_result(task_id: str):
        """Retrieve the result of a task."""
        result = await sdk.get_result(task_id)
        if result:
            return result
        raise HTTPException(status_code=404, detail="Result not found or timed out.")

    # ─── Health Check ───────────────────────────────────────────────────

    @app.get("/health")
    async def health_check():
        """Return server health status including NATS and JetStream connectivity."""
        _bus = get_bus()
        nats_connected = _bus.nc is not None and not _bus.nc.is_closed
        js_available = False
        if nats_connected:
            try:
                _bus.nc.jetstream()
                js_available = True
            except Exception:
                pass
        return {
            "status": "ok",
            "version": VERSION,
            "nats": "connected" if nats_connected else "disconnected",
            "jetstream": js_available,
        }

    # ─── Version ────────────────────────────────────────────────────────

    @app.get("/version")
    def version_endpoint():
        """Return server version and minimum supported client version."""
        _bus = get_bus()
        return {
            "version": VERSION,
            "minClient": MIN_CLIENT_VERSION,
            "server": "nexus-server",
            "uptime": round(time.monotonic() - _VERSION_START_TIME, 2),
            "nats": "connected" if _bus.nc else "disconnected",
        }

    # ─── Task Listing ───────────────────────────────────────────────────

    @app.get("/tasks", dependencies=[Depends(verify_api_key)])
    async def list_tasks(status: str | None = None, limit: int = 50, offset: int = 0):
        """List tasks with optional status filter and pagination."""
        task_repo = get_task_repo()
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        tasks = await task_repo.list_tasks(status=status, limit=limit, offset=offset)
        return {"tasks": tasks, "count": len(tasks), "limit": limit, "offset": offset}

    # ─── Task Cancellation ──────────────────────────────────────────────

    @app.post("/tasks/{task_id}/cancel", dependencies=[Depends(require_admin)])
    async def cancel_task(task_id: str):
        """Cancel a pending or processing task."""
        task_repo = get_task_repo()
        cancelled = await task_repo.cancel_task(task_id)
        if not cancelled:
            raise HTTPException(
                status_code=400, detail="Task not found or already completed/failed"
            )

        try:
            bus = get_bus()
            await bus.publish("tasks.cancel", {"task_id": task_id})
        except Exception:
            pass

        return {"task_id": task_id, "status": "cancelled"}

    # ─── Task Retry ─────────────────────────────────────────────────────

    @app.post("/tasks/{task_id}/retry", dependencies=[Depends(require_admin)])
    async def retry_task(task_id: str):
        """Retry a failed task."""
        task_repo = get_task_repo()
        original = await task_repo.get_task(task_id)
        if not original:
            raise HTTPException(status_code=404, detail="Task not found")

        new_id = await task_repo.retry_task(task_id)
        if not new_id:
            raise HTTPException(status_code=400, detail="Task not found or not in failed state")

        task_data = {
            "id": new_id,
            "description": original.get("description", "retried"),
            "priority": original.get("priority", 1),
        }
        await sdk.submit_task(task_data)
        return {"task_id": new_id, "status": "re-queued"}

    # ─── Worker & Tool Status ───────────────────────────────────────────

    @app.get("/workers", dependencies=[Depends(verify_api_key)])
    async def list_workers():
        """List worker status including circuit breaker state."""
        from nexusagent.core.worker import _agent_breaker, _nats_breaker

        return {
            "workers": [
                {
                    "name": "default",
                    "status": "running",
                    "circuit_breakers": {
                        "agent": {
                            "state": _agent_breaker.state,
                            "failure_count": _agent_breaker.failure_count,
                        },
                        "nats": {
                            "state": _nats_breaker.state,
                            "failure_count": _nats_breaker.failure_count,
                        },
                    },
                }
            ]
        }

    @app.get("/tools", dependencies=[Depends(verify_api_key)])
    async def list_tools():
        """List all registered tools grouped by category."""
        tools = list_all_tools()
        by_cat: dict[str, list[dict]] = {}
        for t in tools:
            by_cat.setdefault(t.category, []).append(
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            )
        return {"tools": by_cat, "total": len(tools)}

    # ─── Auth Token Exchange (for browser WebSocket clients) ─────────────

    class TokenExchangeRequest(BaseModel):
        """Request body for token exchange."""

        api_key: str = Field(..., description="API key to exchange for a connection token")

    class TokenExchangeResponse(BaseModel):
        """Response with short-lived connection token."""

        token: str = Field(..., description="Short-lived connection token for WebSocket")
        expires_in: int = Field(default=300, description="Token expiry in seconds")

    @app.post("/auth/token", response_model=TokenExchangeResponse)
    async def exchange_token(request: TokenExchangeRequest):
        """Exchange an API key for a short-lived WebSocket connection token.

        Browser clients that cannot set custom headers on WebSocket connections
        should call this endpoint first, then pass the returned token via
        the ?token= query parameter when connecting to /sessions/{id}/ws.
        """

        try:
            await verify_api_key(request.api_key)
        except HTTPException:
            raise HTTPException(status_code=401, detail="Invalid API key") from None

        # Generate a short-lived token (the API key itself, marked as a token)
        # In production, this would be a JWT or similar with expiry
        # For now, we use the API key as the token — it's already verified
        return TokenExchangeResponse(
            token=request.api_key,
            expires_in=300,
        )
