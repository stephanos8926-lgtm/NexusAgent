# src/nexusagent/server.py
"""FastAPI WebSocket server for the NexusAgent platform.

Provides REST endpoints for task submission, status tracking, and
cancellation, plus a WebSocket interface for real-time interactive
sessions. Includes rate limiting, API key authentication, and
version handshake middleware.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nexusagent.infrastructure.api_auth import verify_api_key
from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.config import settings
from nexusagent.server.sdk import sdk
from nexusagent.version import MIN_CLIENT_VERSION, VERSION

# Track server start time for uptime reporting
_SERVER_START_TIME = time.monotonic()

# Setup logging
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan: Handles startup and shutdown.
    """
    logger.info(f"NexusAgent Server v{VERSION} starting on port {settings.server.api_port}...")
    try:
        # 1. Initialize DB
        from nexusagent.infrastructure.db import get_db_manager
        db_manager = get_db_manager()
        await db_manager.init_db()
        logger.info("Database initialized.")

        # 2. Connect to NATS
        _bus = get_bus()
        await _bus.connect()

        # 3. Start the Worker as a background task within the same process
        # This co-locates the API and the Worker for simplicity in deployment.
        from nexusagent.core.worker import NexusWorker
        worker = NexusWorker()
        worker_task = asyncio.create_task(worker.start())  # noqa: RUF006
        logger.info("Worker background task started.")

        yield

        # Shutdown
        logger.info("Shutting down NexusAgent Backend...")
        worker_task.cancel()
        await _bus.close()

    except Exception as e:
        logger.error(f"Critical error during startup: {e}", exc_info=True)
        raise


app = FastAPI(
    title="NexusAgent API",
    description="Production-grade API for the NexusAgent Orchestrator",
    lifespan=lifespan,
)

# SECURITY: restrict CORS to localhost only.
# allow_credentials=True is incompatible with allow_origins=["*"] in browsers
# and exposes cookies/auth headers to any origin. Localhost-only origins are
# safe for the local TUI/web-UI use-case.
_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Rate Limiting Middleware ──────────────────────────────────────────

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Apply rate limiting to all API endpoints."""
    from nexusagent.infrastructure.rate_limit import check_rate_limit

    # Skip rate limiting for health/version endpoints
    if request.url.path in ("/health", "/version"):
        return await call_next(request)

    # Identify client by API key header or fallback to IP
    client_id = request.headers.get("x-api-key") or request.client.host

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


class SubmitTaskRequest(BaseModel):
    """Request body for submitting a new task to the orchestrator."""

    description: str = Field(..., max_length=10000, description="Task description (max 10K chars)")
    priority: int = Field(default=1, ge=1, le=10)
    metadata: dict = Field(default_factory=dict)


@app.post("/tasks", response_model=dict, dependencies=[Depends(verify_api_key)])
async def create_task(request: SubmitTaskRequest):
    """Submit a new task to the orchestrator.
    """
    try:
        import uuid

        from nexusagent.infrastructure.db import get_task_repo
        from nexusagent.llm.models import TaskStatus

        task_repo = get_task_repo()

        task_id = str(uuid.uuid4())

        # Create task in DB first (status=pending_nats indicates not yet on bus)
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
                logger.warning(f"NATS publish attempt {attempt + 1} failed: {nats_exc}")
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(0.5 * (attempt + 1))

        if nats_error:
            # NATS publish failed after retries — mark task as failed, not orphaned
            await task_repo.update_task_status(task_id, TaskStatus.FAILED)
            logger.error(f"Task {task_id}: NATS publish failed after 3 attempts")
            raise HTTPException(
                status_code=503,
                detail="Task queue unavailable. Please try again later.",
            ) from nats_error

        # NATS publish succeeded — update status to pending
        await task_repo.update_task_status(task_id, TaskStatus.PENDING)

        return {"task_id": task_id, "status": "submitted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/tasks/{task_id}/status", dependencies=[Depends(verify_api_key)])
async def get_task_status(task_id: str):
    """Check the status of a task.
    """
    status = await sdk.get_task_status(task_id)
    return {"task_id": task_id, "status": status}


@app.get("/tasks/{task_id}/result", dependencies=[Depends(verify_api_key)])
async def get_task_result(task_id: str):
    """Retrieve the result of a task.
    Returns 404 if result is not yet available.
    """
    result = await sdk.get_result(task_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="Result not found or timed out.")


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


@app.get("/version")
async def version_endpoint():
    """Return server version and minimum supported client version."""
    _bus = get_bus()
    return {
        "version": VERSION,
        "minClient": MIN_CLIENT_VERSION,
        "server": "nexus-server",
        "uptime": round(time.monotonic() - _SERVER_START_TIME, 1),
        "nats": "connected" if _bus.nc else "disconnected",
    }


# ─── Task Listing ──────────────────────────────────────────────────────


@app.get("/tasks", dependencies=[Depends(verify_api_key)])
async def list_tasks(status: str | None = None, limit: int = 50, offset: int = 0):
    """List tasks with optional status filter and pagination."""
    from nexusagent.infrastructure.db import get_task_repo
    task_repo = get_task_repo()

    # Clamp limit to prevent resource exhaustion
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    tasks = await task_repo.list_tasks(status=status, limit=limit, offset=offset)
    return {"tasks": tasks, "count": len(tasks), "limit": limit, "offset": offset}


# ─── Task Cancellation ─────────────────────────────────────────────────


@app.post("/tasks/{task_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_task(task_id: str):
    """Cancel a pending or processing task."""
    from nexusagent.infrastructure.db import get_task_repo
    task_repo = get_task_repo()

    cancelled = await task_repo.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task not found or already completed/failed")

    # Signal worker to stop processing (best-effort via NATS)
    try:
        bus = get_bus()
        await bus.publish("tasks.cancel", {"task_id": task_id})
    except Exception:
        pass  # Worker may not be running; DB cancel is sufficient

    return {"task_id": task_id, "status": "cancelled"}


# ─── Task Retry ────────────────────────────────────────────────────────


@app.post("/tasks/{task_id}/retry", dependencies=[Depends(verify_api_key)])
async def retry_task(task_id: str):
    """Retry a failed task."""
    from nexusagent.infrastructure.db import get_task_repo
    task_repo = get_task_repo()

    # Fetch original task to preserve description
    original = await task_repo.get_task(task_id)
    if not original:
        raise HTTPException(status_code=404, detail="Task not found")

    new_id = await task_repo.retry_task(task_id)
    if not new_id:
        raise HTTPException(status_code=400, detail="Task not found or not in failed state")

    # Re-publish to NATS with original description preserved
    task_data = {
        "id": new_id,
        "description": original.get("description", "retried"),
        "priority": original.get("priority", 1),
    }
    await sdk.submit_task(task_data)

    return {"task_id": new_id, "status": "re-queued"}


# ─── Worker & Tool Status ──────────────────────────────────────────────


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
    from nexusagent.tools.registry import list_all_tools

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


# ─── WebSocket Interactive Sessions ────────────────────────────────────


@app.websocket("/sessions/{session_id}/ws")
async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    api_key: str | None = None,
):
    """Real-time interactive session via WebSocket.

    Requires API key via X-API-Key header (preferred) or ?api_key= query param.
    Query param is supported for browser compatibility (browsers cannot set
    custom headers on WebSocket connections).
    """
    # Verify API key before accepting the connection
    # Prefer header auth; fall back to query param for browser clients
    header_key = websocket.headers.get("x-api-key")
    effective_key = header_key or api_key
    if not effective_key:
        await websocket.close(code=4001, reason="Missing API key")
        return
    try:
        await verify_api_key(effective_key)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return

    await websocket.accept()

    from nexusagent.core.agent import Agent
    from nexusagent.infrastructure.db import get_session_repo
    session_repo = get_session_repo()
    from nexusagent.core.session import session_manager

    # Create a real agent for this interactive session
    agent = Agent(role="full", policy="permissive")

    session = await session_manager.get_or_create(
        session_id,
        working_dir=".",
        agent=agent,
        memory=None,
        db_repo=session_repo,
    )

    # Set workspace root for file operation path jail
    from nexusagent.tools.fs import set_workspace_root
    set_workspace_root(session.working_dir)

    try:
        await websocket.send_json({"type": "session_status", "status": session.status})

        async def send_events():
            async for event in session.event_stream():
                await websocket.send_json(event)

        async def receive_messages():
            while True:
                try:
                    msg = await websocket.receive_json()
                except Exception:
                    break
                msg_type = msg.get("type")

                if msg_type == "user_input":
                    content = msg.get("content", "")
                    images = msg.get("images", []) or []
                    if images:
                        await session.send(content, images=images)
                    else:
                        await session.send(content)
                elif msg_type == "approval":
                    call_id = msg.get("call_id", "")
                    approved = msg.get("approved", False)
                    await session.approve(call_id, approved)
                elif msg_type == "interrupt":
                    await session.interrupt()
                elif msg_type == "list_sessions":
                    # Return session list to the TUI
                    try:
                        sessions = await session_repo.list_sessions(limit=20)
                        await websocket.send_json({
                            "type": "session_list",
                            "sessions": sessions,
                        })
                    except Exception as e:
                        logger.warning("Failed to list sessions: %s", e)
                        await websocket.send_json({
                            "type": "session_list",
                            "sessions": [],
                            "error": str(e),
                        })
                elif msg_type == "compact":
                    # Trigger context compaction for this session
                    try:
                        ctx = await session.pre_compaction_flush()
                        await websocket.send_json({
                            "type": "compact_result",
                            "status": "ok",
                            "summary": ctx[:200] if ctx else "",
                        })
                    except Exception as e:
                        logger.warning("Compaction failed: %s", e)
                        await websocket.send_json({
                            "type": "compact_result",
                            "status": "error",
                            "error": str(e),
                        })
                elif msg_type == "close":
                    await session.close()
                    break

        await asyncio.gather(send_events(), receive_messages())

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected")
        await session_manager.mark_idle(session_id)
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}", exc_info=True)
        await websocket.close(code=1011)


def run(reload: bool = False) -> None:
    """Entry point for the nexus-server command."""
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.server.api_port,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NexusAgent Server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )
    args = parser.parse_args()
    run(reload=args.reload)
