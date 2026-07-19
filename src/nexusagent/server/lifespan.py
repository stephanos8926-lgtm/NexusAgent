"""Server lifespan adapter — wires Runtime into FastAPI lifecycle.

Provides create_server_app() which wraps the existing create_app() with
Runtime initialize/shutdown integrated into the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import fastapi

from nexusagent.infrastructure.config import settings
from nexusagent.runtime.runtime import Runtime
from nexusagent.version import VERSION

logger = logging.getLogger("nexusagent.server")


@asynccontextmanager
async def runtime_lifespan(app: fastapi.FastAPI) -> AsyncGenerator[None]:
    """FastAPI Lifespan with Runtime lifecycle management.

    Creates a Runtime at startup, initializes it, and shuts it down
    on exit. The Runtime handles DB, NATS, and ToolManager initialization.
    The Worker background task is started separately to preserve the
    existing pattern.
    """
    logger.info(
        "NexusAgent Server v%s starting on port %d...",
        VERSION,
        settings.server.api_port,
    )

    runtime = Runtime(config=settings)
    worker_task = None

    try:
        await runtime.initialize()

        # Store in app.state for route access
        app.state.runtime = runtime
        app.state.context = runtime.context

        # Start the Worker as a background task (existing pattern)
        from nexusagent.core.worker import NexusWorker

        worker = NexusWorker()
        worker_task = asyncio.create_task(worker.start())
        logger.info("Worker background task started.")

        yield

    except Exception as e:
        logger.error("Critical error during startup: %s", e, exc_info=True)
        raise
    finally:
        logger.info("Shutting down NexusAgent Backend...")
        if worker_task is not None:
            worker_task.cancel()
        await runtime.shutdown()


def create_server_app() -> fastapi.FastAPI:
    """Create the FastAPI application with Runtime-based lifespan.

    Replaces the original create_app() lifespan with runtime_lifespan.
    All routes, middleware, and config remain identical.
    """
    from nexusagent.server.routes import register_routes
    from nexusagent.server.websocket import session_websocket

    app = fastapi.FastAPI(
        title="NexusAgent API",
        description="Production-grade API for the NexusAgent Orchestrator",
        lifespan=runtime_lifespan,
    )

    register_routes(app)
    # Wire health endpoint to Runtime
    _wire_runtime_health(app)

    # WebSocket endpoint
    @app.websocket("/ws/{session_id}")
    async def ws_endpoint(websocket: Any, session_id: str) -> None:
        await session_websocket(websocket, session_id)

    return app


def _wire_runtime_health(app: fastapi.FastAPI) -> None:
    """Add a runtime-aware health endpoint to an existing route."""

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Return server health, including Runtime subsystem status."""
        import time

        from nexusagent.server.server import _SERVER_START_TIME

        uptime = time.monotonic() - _SERVER_START_TIME

        runtime_health = None
        runtime = getattr(app.state, "runtime", None)
        if runtime is not None:
            runtime_health = runtime.health()
            runtime_health.details["uptime_seconds"] = round(uptime, 1)

        return {
            "status": "ok",
            "version": VERSION,
            "uptime_seconds": round(uptime, 1),
            "runtime": runtime_health,
        }


# Default app instance (for uvicorn import string)
app = create_server_app()
