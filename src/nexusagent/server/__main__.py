# src/nexusagent/server/__main__.py
"""Entry point for `python3 -m nexusagent.server`."""

import argparse

import uvicorn

from nexusagent.infrastructure.config import settings
from nexusagent.server.lifespan import create_server_app
from nexusagent.server.server import _acquire_singleton_lock

# Import create_server_app from nexusagent.server.lifespan instead of create_app from nexusagent.server.server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NexusAgent Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.server.api_port,
        help=f"Bind port (default: {settings.server.api_port})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )
    args = parser.parse_args()

    lock_fd = _acquire_singleton_lock()
    if lock_fd is not None:
        # Replace the create_app() call with create_server_app()
        app = create_server_app()

        if args.reload:
            uvicorn.run(
                "nexusagent.server.lifespan:create_server_app",
                host=args.host,
                port=args.port,
                reload=True,
                factory=True,
                ssl_certfile=settings.server.tls_certfile if settings.server.tls_enabled else None,
                ssl_keyfile=settings.server.tls_keyfile if settings.server.tls_enabled else None,
                ws="websockets",
            )
        else:
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                ssl_certfile=settings.server.tls_certfile if settings.server.tls_enabled else None,
                ssl_keyfile=settings.server.tls_keyfile if settings.server.tls_enabled else None,
                ws="websockets",
            )
