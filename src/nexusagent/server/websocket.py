# src/nexusagent/server/websocket.py
"""WebSocket session handler for real-time interactive agent sessions."""

import asyncio
import logging

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from nexusagent.core.agent import Agent
from nexusagent.core.session import session_manager
from nexusagent.infrastructure.api_auth import verify_api_key
from nexusagent.infrastructure.db import get_session_repo
from nexusagent.tools.fs import set_workspace_root

logger = logging.getLogger(__name__)


async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    api_key: str | None = None,
):
    """Real-time interactive session via WebSocket.

    Requires API key via X-API-Key header (preferred) or ?api_key= query param.
    Query param is supported for browser compatibility (browsers cannot set
    custom headers on WebSocket connections).
    """
    # Verify API key before accepting the connection
    # Prefer header auth; fall back to query param for browser clients
    header_key = websocket.headers.get("x-api-key")
    effective_key = header_key or api_key
    if not effective_key:
        await websocket.close(code=4001, reason="Missing API key")
        return
    try:
        await verify_api_key(effective_key)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return

    await websocket.accept()

    session_repo = get_session_repo()

    # Create a real agent for this interactive session
    agent = Agent(role="full", policy="permissive")

    session = await session_manager.get_or_create(
        session_id,
        working_dir=".",
        agent=agent,
        memory=None,
        db_repo=session_repo,
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
                msg_type = msg.get("type")

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
        logger.error("WebSocket error in session %s: %s", session_id, e, exc_info=True)
        await websocket.close(code=1011)
