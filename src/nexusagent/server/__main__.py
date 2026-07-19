# src/nexusagent/server/__main__.py
"""Entry point for `python3 -m nexusagent.server`."""

import sys

import uvicorn

from nexusagent.infrastructure.config import settings
from nexusagent.server.lifespan import create_server_app
from nexusagent.server.server import _acquire_singleton_lock

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NexusAgent Server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )
    args = parser.parse_args()

    lock_fd = _acquire_singleton_lock()
    if lock_fd is None:
        sys.exit(1)

    app = create_server_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.server.api_port,
        reload=args.reload,
        ssl_certfile=settings.server.tls_certfile if settings.server.tls_enabled else None,
        ssl_keyfile=settings.server.tls_keyfile if settings.server.tls_enabled else None,
        ws="websockets",
    )
