# src/nexusagent/server.py
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nexusagent.infrastructure.api_auth import verify_api_key
from nexusagent.version import VERSION, MIN_CLIENT_VERSION

# Track server start time for uptime reporting
_SERVER_START_TIME = time.monotonic()
from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.config import settings
from nexusagent.server.sdk import sdk
from nexusagent.core.worker import worker

# Setup logging
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan: Handles startup and shutdown.
    """
    logger.info(f"NexusAgent Server v{VERSION} starting on port {settings.server.api_port}...")
    try:
        # 1. Initialize DB
        from nexusagent.infrastructure.db import db_manager

        await db_manager.init_db()
        logger.info("Database initialized.")

        # 2. Connect to NATS
        _bus = get_bus()
        await _bus.connect()

        # 3. Start the Worker as a background task within the same process
        # This co-locates the API and the Worker for simplicity in deployment.
        worker_task = asyncio.create_task(worker.start())
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


class SubmitTaskRequest(BaseModel):
    description: str
    priority: int = 1
    metadata: dict = {}


@app.post("/tasks", response_model=dict, dependencies=[Depends(verify_api_key)])
async def create_task(request: SubmitTaskRequest):
    """
    Submit a new task to the orchestrator.
    """
    try:
        # In a production system, we would save the task to DB here before publishing to NATS
        # but for simplicity, we let the worker handle the first 'create' or
        # we can add a call to task_repo.create_task here.

        # Let's ensure the task is in the DB before it hits NATS
        import uuid

        from nexusagent.infrastructure.db import task_repo

        task_id = str(uuid.uuid4())

        await task_repo.create_task(
            task_id=task_id,
            description=request.description,
            priority=request.priority,
            metadata=request.metadata,
        )

        task_id = await sdk.submit_task(
            {
                "id": task_id,
                "description": request.description,
                "priority": request.priority,
                "metadata": request.metadata,
            }
        )

        return {"task_id": task_id, "status": "submitted"}
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/tasks/{task_id}/status", dependencies=[Depends(verify_api_key)])
async def get_task_status(task_id: str):
    """
    Check the status of a task.
    """
    status = await sdk.get_task_status(task_id)
    return {"task_id": task_id, "status": status}


@app.get("/tasks/{task_id}/result", dependencies=[Depends(verify_api_key)])
async def get_task_result(task_id: str):
    """
    Retrieve the result of a task.
    Returns 404 if result is not yet available.
    """
    result = await sdk.get_result(task_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="Result not found or timed out.")


@app.get("/health")
async def health_check():
    _bus = get_bus()
    return {
        "status": "ok",
        "version": VERSION,
        "nats": "connected" if _bus.nc else "disconnected",
    }


@app.get("/version")
async def version_endpoint():
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
    from nexusagent.infrastructure.db import task_repo

    tasks = await task_repo.list_tasks(status=status, limit=limit, offset=offset)
    return {"tasks": tasks, "count": len(tasks)}


# ─── Task Cancellation ─────────────────────────────────────────────────


@app.post("/tasks/{task_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_task(task_id: str):
    """Cancel a pending or processing task."""
    from nexusagent.infrastructure.db import task_repo

    cancelled = await task_repo.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task not found or already completed/failed")
    return {"task_id": task_id, "status": "cancelled"}


# ─── Task Retry ────────────────────────────────────────────────────────


@app.post("/tasks/{task_id}/retry", dependencies=[Depends(verify_api_key)])
async def retry_task(task_id: str):
    """Retry a failed task."""
    from nexusagent.infrastructure.db import task_repo

    new_id = await task_repo.retry_task(task_id)
    if not new_id:
        raise HTTPException(status_code=400, detail="Task not found or not in failed state")

    # Re-publish to NATS
    task_data = {"id": new_id, "description": "retried", "priority": 1}
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

    Requires API key via query parameter: ?api_key=xxx
    """
    # Verify API key before accepting the connection
    from nexusagent.infrastructure.api_auth import verify_api_key
    try:
        verify_api_key(api_key)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return

    await websocket.accept()

    from nexusagent.core.agent import Agent
    from nexusagent.infrastructure.db import session_repo
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
                msg = await websocket.receive_json()
                msg_type = msg.get("type")

                if msg_type == "user_input":
                    content = msg.get("content", "")
                    images = msg.get("images", [])
                    if images:
                        await session.send(content, images=images)
                    else:
                        await session.send(content)
                elif msg_type == "approval":
                    await session.approve(msg["call_id"], msg.get("approved", False))
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
