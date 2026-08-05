# SPDX-License-Identifier: MIT

# src/nexusagent/server/websocket.py
"""WebSocket session handler for real-time interactive agent sessions."""

import asyncio
import contextlib
import json
import logging

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from nexusagent.core.agent import Agent
from nexusagent.core.session import session_manager
from nexusagent.infrastructure.api_auth import verify_api_key
from nexusagent.infrastructure.bus import get_bus
from nexusagent.infrastructure.db import get_session_repo
from nexusagent.tools.fs_base import set_workspace_root

# Allowed origins for WebSocket CSRF protection (shared with CORS)
_WS_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

# Maximum WebSocket message size in bytes (64 KB)
_WS_MAX_MESSAGE_SIZE = 65536

logger = logging.getLogger(__name__)

_WRAPPED_TIMEOUT = 300.0


async def _recv_with_timeout(websocket: WebSocket, timeout: float = _WRAPPED_TIMEOUT):
    try:
        return await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except TimeoutError:
        return None
    except WebSocketDisconnect:
        return "__DISCONNECT__"
    except Exception as e:
        logger.error("WebSocket receive error: %s", e)
        return "__DISCONNECT__"


async def _authenticate_websocket(websocket: WebSocket, session_id: str) -> str | None:
    header_key = websocket.headers.get("x-api-key")
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        header_key = header_key or auth_header[7:]
    token_param = websocket.query_params.get("token")
    if token_param and not header_key:
        try:
            from nexusagent.infrastructure.api_auth import resolve_short_lived_token

            resolved = resolve_short_lived_token(token_param)
            if resolved is not None:
                header_key = resolved
        except Exception:
            pass
        if not header_key:
            header_key = token_param
    if not header_key:
        await websocket.close(code=4001, reason="Missing API key — use Authorization: Bearer <key>")
        return None

    try:
        await verify_api_key(header_key)
    except HTTPException as e:
        logger.warning("WS auth failed for session=%s: %s", session_id, e)
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return None

    origin = websocket.headers.get("origin", "")
    if origin and origin not in _WS_ALLOWED_ORIGINS:
        logger.warning("Rejected WebSocket from unauthorized origin: %s", origin)
        await websocket.close(code=4003, reason="Forbidden origin")
        return None

    return header_key


async def session_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """Real-time interactive session via WebSocket.

    Accepts API key via:
      - X-API-Key header (primary)
      - Authorization: Bearer <key> header (TUI clients)

    For browser clients (which cannot set custom WebSocket headers),
    call POST /auth/token first to obtain a short-lived token, then
    pass it via the ?token= query parameter. Note: query-param tokens
    are less secure — they may appear in server logs, proxy logs, and
    Referer headers.
    """
    logger.info("session_websocket CALLED: session_id=%s", session_id)
    header_key = await _authenticate_websocket(websocket, session_id)
    if header_key is None:
        return

    await websocket.accept()

    # Log origin for accepted connections (diagnostic)
    origin = websocket.headers.get("origin", "")
    logger.info("WebSocket accepted from origin: %s", origin or "none")

    session_repo = get_session_repo()

    # Create a real agent for this interactive session
    agent = await Agent.create(role="full", policy="permissive")

    # Resolve workspace-scoped memory directory from query param or config
    _memory_dir: str | None = None
    _working_dir = websocket.query_params.get("working_dir", ".")
    try:
        from nexusagent.infrastructure.config import settings as _settings

        if _settings.agent.memory_workspace:
            # Config-level override: use the configured workspace memory directory
            import os as _os

            _memory_dir = _os.path.expanduser(_settings.agent.memory_workspace)
        elif _working_dir and _working_dir != ".":
            # Per-session workspace: use <working_dir>/.nexusagent/memory
            from pathlib import Path as _Path

            _ws_memory = _Path(_working_dir) / ".nexusagent" / "memory"
            _memory_dir = str(_ws_memory)
    except Exception:
        _memory_dir = None

    session = await session_manager.get_or_create(
        session_id,
        working_dir=_working_dir,
        agent=agent,
        db_repo=session_repo,
        memory_dir=_memory_dir,
    )

    # Set workspace root for file operation path jail
    set_workspace_root(session.working_dir)

    try:
        await websocket.send_json({"type": "session_status", "status": session.status})

        async def send_events():
            async for event in session.event_stream():
                await websocket.send_json(event)

        async def receive_messages():
            while True:
                try:
                    raw_text = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error("WebSocket receive error in receive_messages: %s", e)
                    break
                # Validate message size BEFORE parsing JSON (prevents OOM from crafted payloads)
                if len(raw_text) > _WS_MAX_MESSAGE_SIZE:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "error": f"Message too large ({len(raw_text)} bytes, max {_WS_MAX_MESSAGE_SIZE})",
                        }
                    )
                    continue
                try:
                    import json

                    msg = json.loads(raw_text)
                except Exception:
                    continue
                # Validate message has required fields
                msg_type = msg.get("type")
                if not msg_type:
                    continue

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
                    # Return session list to the TUI — admin only
                    try:
                        from nexusagent.infrastructure.api_auth import _classify_key

                        _role = _classify_key(header_key)
                        if _role != "admin":
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "error": "Admin access required to list sessions",
                                }
                            )
                            continue
                        sessions = await session_repo.list_sessions(limit=20)
                        await websocket.send_json(
                            {
                                "type": "session_list",
                                "sessions": sessions,
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to list sessions: %s", e)
                        await websocket.send_json(
                            {
                                "type": "session_list",
                                "sessions": [],
                                "error": str(e),
                            }
                        )
                elif msg_type == "change_model":
                    model = msg.get("model", "")
                    provider = msg.get("provider", "")
                    if model:
                        from nexusagent.infrastructure.config import settings as _settings

                        _settings.agent.default_model = model
                        if provider:
                            _settings.agent.primary_provider = provider
                        await websocket.send_json(
                            {
                                "type": "model_changed",
                                "model": model,
                                "provider": provider,
                            }
                        )
                elif msg_type == "compact":
                    # Trigger context compaction for this session
                    try:
                        ctx = await session.pre_compaction_flush()
                        await websocket.send_json(
                            {
                                "type": "compact_result",
                                "status": "ok",
                                "summary": ctx[:200] if ctx else "",
                            }
                        )
                    except Exception as e:
                        logger.warning("Compaction failed: %s", e)
                        await websocket.send_json(
                            {
                                "type": "compact_result",
                                "status": "error",
                                "error": str(e),
                            }
                        )
                elif msg_type == "close":
                    await session.close()
                    break

        await asyncio.gather(send_events(), receive_messages())

    except WebSocketDisconnect:
        logger.info("Session %s disconnected", session_id)
        # Cancel heartbeat immediately on disconnect (prevents "Still thinking..." after client gone)
        if session._heartbeat_task is not None and not session._heartbeat_task.done():
            session._heartbeat_task.cancel()
        await session_manager.mark_idle(session_id)
    except Exception as e:
        logger.error("WebSocket error in session %s: %s", session_id, type(e).__name__)
        # Cancel heartbeat on any error
        if session._heartbeat_task is not None and not session._heartbeat_task.done():
            session._heartbeat_task.cancel()
        await websocket.close(code=1011)


async def events_websocket(websocket: WebSocket) -> None:
    """Real-time system events streaming via WebSocket.

    Accepts API key via headers, Authorization header, or token query parameter.
    """
    logger.info("events_websocket CALLED")

    header_key = await _authenticate_websocket(websocket, session_id="events")
    if header_key is None:
        return

    bus = get_bus()
    queue: asyncio.Queue = asyncio.Queue()

    async def callback(msg) -> None:
        try:
            data = json.loads(msg.data.decode())
            await queue.put(data)
        except Exception as e:
            logger.error("Events websocket callback error: %s", e)

    # Subscribe to all nexus events
    sub = await bus.nc.subscribe("nexus.>", cb=callback)

    try:
        while True:
            # Get event from queue and send over WebSocket
            event_data = await asyncio.wait_for(queue.get(), timeout=_WRAPPED_TIMEOUT)
            await websocket.send_json(event_data)
    except TimeoutError:
        logger.info("Events WebSocket idle timeout")
    except WebSocketDisconnect:
        logger.info("Events WebSocket disconnected")
    except Exception as e:
        logger.error("Error in events_websocket: %s", e)
    finally:
        with contextlib.suppress(Exception):
            await sub.unsubscribe()


async def pol_websocket(websocket: WebSocket) -> None:
    """Real-time POL system interventions streaming via WebSocket.

    Accepts API key via headers, Authorization header, or token query parameter.
    """
    logger.info("pol_websocket CALLED")
    header_key = await _authenticate_websocket(websocket, session_id="pol")
    if header_key is None:
        return

    await websocket.accept()

    from typing import Any

    from nexusagent.core.pol import get_pol_control_plane

    pol = get_pol_control_plane()
    queue: asyncio.Queue = asyncio.Queue()

    async def callback(intervention: dict[str, Any]) -> None:
        try:
            await queue.put(intervention)
        except Exception as e:
            logger.error("POL websocket callback error: %s", e)

    # Register the callback in POLControlPlane
    pol.register_websocket_callback(callback)

    try:
        while True:
            # Get intervention update from queue and send over WebSocket
            intervention_data = await asyncio.wait_for(queue.get(), timeout=_WRAPPED_TIMEOUT)
            await websocket.send_json(intervention_data)
    except TimeoutError:
        logger.info("POL WebSocket idle timeout")
    except WebSocketDisconnect:
        logger.info("POL WebSocket disconnected")
    except Exception as e:
        logger.error("Error in pol_websocket: %s", e)
    finally:
        pol.unregister_websocket_callback(callback)
