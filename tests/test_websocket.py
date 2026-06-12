"""Tests for the WebSocket session endpoint."""

from starlette.routing import WebSocketRoute

from nexusagent.server.server import app


def test_websocket_route_exists():
    """Verify the WebSocket route is registered in app.routes."""
    ws_routes = [r for r in app.routes if isinstance(r, WebSocketRoute)]
    assert len(ws_routes) > 0, "No WebSocket routes found in app"

    paths = [r.path for r in ws_routes]
    assert any("session" in p and "ws" in p for p in paths), (
        f"No route matching /sessions/{{session_id}}/ws found. Routes: {paths}"
    )
