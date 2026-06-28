# src/nexusagent/server.py
"""FastAPI WebSocket server for the NexusAgent platform."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.config import settings
from nexusagent.server.routes import register_routes
from nexusagent.server.websocket import session_websocket
from nexusagent.version import VERSION

# Track server start time for uptime reporting
_SERVER_START_TIME = time.monotonic()

# Setup logging
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan: Handles startup and shutdown."""
    logger.info("NexusAgent Server v%s starting on port %d...", VERSION, settings.server.api_port)
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
        from nexusagent.core.worker import NexusWorker

        worker = NexusWorker()
        worker_task = asyncio.create_task(worker.start())
        logger.info("Worker background task started.")

        yield

        # Shutdown
        logger.info("Shutting down NexusAgent Backend...")
        worker_task.cancel()
        await _bus.close()

    except Exception as e:
        logger.error("Critical error during startup: %s", e, exc_info=True)
        raise


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NexusAgent API",
        description="Production-grade API for the NexusAgent Orchestrator",
        lifespan=lifespan,
    )

    # NO CORS MIDDLEWARE FOR TESTING

    # Register REST routes (includes rate limiting middleware)
    register_routes(app)

    # Register WebSocket endpoint
    @app.websocket("/sessions/{session_id}/ws")
    async def ws_endpoint(websocket: WebSocket, session_id: str):
        await session_websocket(websocket, session_id)

    return app


# Default app instance (for uvicorn import string)
app = create_app()


def run(reload: bool = False) -> None:
    """Entry point for the nexus-server command."""
    import uvicorn

    uvicorn.run(
        "nexusagent.server.server:app",
        host="0.0.0.0",
        port=settings.server.api_port,
        reload=settings.server.reload,
        ssl_certfile=settings.server.tls_certfile if settings.server.tls_enabled else None,
        ssl_keyfile=settings.server.tls_keyfile if settings.server.tls_enabled else None,
        ws="websockets",
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
