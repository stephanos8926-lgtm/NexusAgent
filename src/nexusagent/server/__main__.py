# src/nexusagent/server/__main__.py
"""Entry point for `python3 -m nexusagent.server`."""

from nexusagent.server.lifespan import create_server_app
from nexusagent.server.server import run

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NexusAgent Server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )
    args = parser.parse_args()

    # Wire create_server_app() as the active FastAPI app
    app = create_server_app()

    # Keep CLI flags identical, and run using the lifespan app
    run(reload=args.reload, use_lifespan_app=True)
