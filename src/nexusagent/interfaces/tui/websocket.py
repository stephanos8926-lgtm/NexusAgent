"""WebSocket connection and event loop for the TUI.

Handles:
- Pre-connect version check
- WebSocket connection with retry logic
- Sending/receiving events
- Approval relay
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request

import websockets

from nexusagent.infrastructure.config import settings
from nexusagent.interfaces.cli import is_compatible
from nexusagent.version import VERSION as CLIENT_VERSION

logger = logging.getLogger(__name__)


async def fetch_server_version(app) -> dict | None:
    """Fetch server version data from /version endpoint.

    Args:
        app: The NexusApp instance.

    Returns:
        Parsed JSON dict on success, None on failure.
    """
    url = f"http://127.0.0.1:{settings.server.api_port}/version"
    try:
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(url, timeout=5).read(),
        )
        return json.loads(raw)
    except Exception:
        return None


async def check_server_version(app) -> bool:
    """Fetch server version via HTTP before WebSocket connect.

    Args:
        app: The NexusApp instance.

    Returns:
        True if server is reachable (version mismatch is non-blocking).
        False if server is unreachable.
    """
    data = await app._fetch_server_version()
    if data is None:
        from nexusagent.widgets.messages import AppMessage
        msg = AppMessage("⚠ Server unreachable. Retrying…")
        app.messages_container.mount(msg)
        logger.warning("Version check failed: server unreachable")
        return False

    server_ver = data.get("version", "unknown")
    if not is_compatible(server_ver, CLIENT_VERSION):
        from nexusagent.widgets.messages import AppMessage
        msg = AppMessage(
            f"⚠ Version mismatch: server={server_ver} "
            f"client={CLIENT_VERSION}. Consider upgrading."
        )
        app.messages_container.mount(msg)
        logger.warning(
            "Version mismatch: server=%s client=%s",
            server_ver, CLIENT_VERSION,
        )
    return True


async def send_approval(app, call_id: str, approved: bool) -> None:
    """Send an approval decision to the server.

    Args:
        app: The NexusApp instance.
        call_id: The tool call identifier.
        approved: Whether the call was approved.
    """
    if app._ws:
        await app._ws.send(json.dumps({
            "type": "approval",
            "call_id": call_id,
            "approved": approved,
        }))


async def ws_loop(app) -> None:
    """Main WebSocket connection loop.

    Handles connection, retry with exponential backoff, and event dispatch.
    Delegates event handling to handle_event() in streaming.py.

    Args:
        app: The NexusApp instance.
    """
    api_key = settings.client.api_key
    ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{app.session_id}/ws"
    # Pass working_dir as query param for workspace-scoped memory
    working_dir = getattr(app, "working_dir", None) or "."
    if working_dir != ".":
        from urllib.parse import quote as _quote
        ws_url += f"?working_dir={_quote(working_dir, safe='')}"
    extra_headers: dict[str, str] = {}
    if api_key:
        extra_headers["Authorization"] = f"Bearer {api_key}"

    # Pre-connect version check (non-blocking on mismatch)
    await app._check_server_version()

    max_retries = 6
    base_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                additional_headers=extra_headers,
            ) as ws:
                app._ws = ws
                app.status_bar.set_status("Connected")
                app.status_bar.set_spinner(False)

                async def send_messages():
                    while True:
                        msg = await app._input_queue.get()
                        if msg is None:
                            break
                        try:
                            await ws.send(json.dumps({"type": "user_input", "content": msg}))
                        except Exception:
                            break

                async def receive_events():
                    from nexusagent.interfaces.tui.streaming import handle_event
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        try:
                            await handle_event(app, event)
                        except Exception as exc:
                            logger.warning("handle_event failed for %s: %s", event.get("type"), exc)

                await asyncio.gather(send_messages(), receive_events())
                # Clean close — no retry needed
                return

        except ConnectionRefusedError:
            delay = base_delay * (2 ** attempt)
            remaining = max_retries - attempt - 1
            if remaining == 0:
                app.status_bar.set_status("Connection refused")
                _mount_error(app, f"Cannot connect to server at port {settings.server.api_port} "
                                  f"after {max_retries} attempts.")
                return
            app.status_bar.set_status(f"Reconnecting ({remaining} left)…")
            await asyncio.sleep(delay)
            continue

        except websockets.exceptions.ConnectionClosedOK:
            app.status_bar.set_status("Disconnected")
            app._busy = False
            return

        except websockets.exceptions.ConnectionClosedError as e:
            delay = base_delay * (2 ** attempt)
            remaining = max_retries - attempt - 1
            if remaining == 0:
                app.status_bar.set_status("Connection lost")
                _mount_error(app, f"Connection lost: {e}")
                app._busy = False
                return
            app.status_bar.set_status(f"Reconnecting ({remaining} left)…")
            await asyncio.sleep(delay)
            continue

        except Exception as e:
            app.status_bar.set_status("Error")
            _mount_error(app, f"Error: {e}")
            return

        finally:
            app._ws = None


def _mount_error(app, message: str) -> None:
    """Mount an error message in the TUI.

    Args:
        app: The NexusApp instance.
        message: The error message to display.
    """
    from nexusagent.widgets.messages import ErrorMessage
    err = ErrorMessage(message=message)
    app.messages_container.mount(err)
