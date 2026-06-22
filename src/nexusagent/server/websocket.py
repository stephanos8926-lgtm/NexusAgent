# src/nexusagent/server/websocket.py
"""WebSocket session handler for real-time interactive agent sessions."""

import asyncio
import logging

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from nexusagent.core.agent import Agent
from nexusagent.core.session import session_manager
from nexusagent.infrastructure.api_auth import verify_api_key
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


async def session_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """Real-time interactive session via WebSocket.

    Requires API key via X-API-Key header.
    For browser clients, first call POST /auth/token to exchange an API key
    for a short-lived connection token, then pass that token via the
    ?token= query parameter.
    """
    logger.info(f"session_websocket CALLED: session_id={session_id}")
    # Debug: log all headers
    print(f"DEBUG headers: {dict(websocket.headers)}", flush=True)
    # Verify API key — accept X-API-Key header or Authorization: Bearer ***
    header_key = websocket.headers.get("x-api-key")
    # Also accept Bearer <REDACTED> (sent by TUI and browser clients)
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        header_key = header_key or auth_header[7:]
    # Also accept short-lived connection token from query param
    token = websocket.query_params.get("token")
    effective_key = header_key or token
    print(f"DEBUG effective_key: '{effective_key}'", flush=True)

    # In local/dev mode, if no key is provided and auth keystore doesn't exist,
    # allow connections without auth (the TUI connects locally without a key)
    if not effective_key:
        try:
            from nexusagent.infrastructure.auth import get_auth_manager
            get_auth_manager()
            # Auth is initialized but no key provided — reject
            await websocket.close(code=4001, reason="Missing API key")
            return
        except FileNotFoundError:
            # Auth not initialized — allow local dev connections without key
            logger.info("Auth keystore not found — allowing local connection without API key")
            effective_key = "local-dev"  # Skip auth verification
    if effective_key != "local-dev":
        try:
            await verify_api_key(effective_key)
        except HTTPException as e:
            logger.warning(f"WS auth failed for key={effective_key}: {e}")
            await websocket.close(code=4001, reason="Invalid or missing API key")
            return

    # Validate Origin header to prevent CSRF
    origin = websocket.headers.get("origin", "")
    print(f"DEBUG WS origin: '{origin}', allowed={_WS_ALLOWED_ORIGINS}")
    logger.info(f"WS origin: '{origin}', allowed={_WS_ALLOWED_ORIGINS}")
    if origin and origin not in _WS_ALLOWED_ORIGINS:
        logger.warning(f"Rejected WebSocket from unauthorized origin: {origin}")
        await websocket.close(code=4003, reason="Forbidden origin")
        return

    await websocket.accept()

    session_repo = get_session_repo()

    # Create a real agent for this interactive session
    agent = Agent(role="full", policy="permissive")

    # Resolve workspace-scoped memory directory from query param or config
    from nexusagent.infrastructure.config import settings as _settings
    from pathlib import Path as _Path
    import os as _os

    _memory_dir: str | None = None
    _working_dir = websocket.query_params.get("working_dir", ".")
    if _settings.agent.memory_workspace:
        # Config-level override: use the configured workspace memory directory
        _memory_dir = _os.path.expanduser(_settings.agent.memory_workspace)
    elif _working_dir and _working_dir != ".":
        # Per-session workspace: use <working_dir>/.nexusagent/memory
        _ws_memory = _Path(_working_dir) / ".nexusagent" / "memory"
        _memory_dir = str(_ws_memory)

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
                    msg = await websocket.receive_json()
                except Exception:
                    break
                # Validate message size (prevent DoS via large payloads)
                msg_size = len(str(msg))
                if msg_size > _WS_MAX_MESSAGE_SIZE:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Message too large ({msg_size} bytes, max {_WS_MAX_MESSAGE_SIZE})",
                    })
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
        logger.info("Session %s disconnected", session_id)
        await session_manager.mark_idle(session_id)
    except Exception as e:
        logger.error("WebSocket error in session %s: %s", session_id, type(e).__name__)
        await websocket.close(code=1011)
