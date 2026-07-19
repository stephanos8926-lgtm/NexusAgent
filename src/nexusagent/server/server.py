# src/nexusagent/server/server.py
"""FastAPI WebSocket server for the NexusAgent platform."""

import asyncio
import fcntl
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.config import settings
from nexusagent.server.routes import register_routes
from nexusagent.server.websocket import session_websocket
from nexusagent.version import VERSION

# Singleton lock — prevents multiple server instances on the same host
_PID_FILE = os.path.join(
    os.path.expanduser("~"), ".nexusagent", "server.pid"
)

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
    worker_task = None
    _bus = None
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

    except Exception as e:
        logger.error("Critical error during startup: %s", e, exc_info=True)
        raise
    finally:
        # Guaranteed shutdown — runs even if an exception occurs during app runtime
        logger.info("Shutting down NexusAgent Backend...")
        if worker_task is not None:
            worker_task.cancel()
        if _bus is not None:
            await _bus.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NexusAgent API",
        description="Production-grade API for the NexusAgent Orchestrator",
        lifespan=lifespan,
    )

    # Register REST routes (includes rate limiting middleware)
    register_routes(app)

    # Register WebSocket endpoint
    @app.websocket("/sessions/{session_id}/ws")
    async def ws_endpoint(websocket: WebSocket, session_id: str):
        await session_websocket(websocket, session_id)

    return app


# Default app instance (for uvicorn import string)
app = create_app()


def _acquire_singleton_lock() -> int | None:
    """Acquire a file-based singleton lock. Returns the file descriptor or None if another instance is running."""
    os.makedirs(os.path.dirname(_PID_FILE), exist_ok=True)
    fd = None
    try:
        fd = os.open(_PID_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Another instance holds the lock
        existing_pid = "unknown"
        if fd is not None:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                existing_pid = os.read(fd, 32).decode().strip()
            except Exception:
                pass
            os.close(fd)
        print(f"❌ NexusAgent server already running (PID {existing_pid}). Refusing to start.")
        print(f"   If this is stale, remove: {_PID_FILE}")
        return None

    # Write our PID and keep the fd open (lock released on process exit)
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, str(os.getpid()).encode())
    os.fsync(fd)
    return fd


def run(reload: bool = False, use_lifespan_app: bool = False) -> None:
    """Entry point for the nexus-server command."""
    import uvicorn

    lock_fd = _acquire_singleton_lock()
    if lock_fd is None:
        return  # Another instance is already running

    app_import_string = "nexusagent.server.lifespan:app" if use_lifespan_app else "nexusagent.server.server:app"

    uvicorn.run(
        app_import_string,
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
