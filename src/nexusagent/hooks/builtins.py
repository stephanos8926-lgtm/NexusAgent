"""Built-in hook implementations.

These are the standard hooks fired at key points in the agent lifecycle.
Each hook accepts a context dict and returns a dict with metadata about
what it did. Hooks are lightweight — they log to the standard logger or
to a designated log directory.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def session_init_load_context(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Load NEXUS.md from the working directory into the session context.

    Args:
        ctx: Must contain ``working_dir`` key.

    Returns:
        A dict with ``nexus_md_found`` flag, ``nexus_md_path``, and
        ``nexus_md_content``. Returns ``None`` if working_dir is missing.
    """
    working_dir = ctx.get("working_dir")
    if not working_dir:
        return None

    nexus_md_path = Path(working_dir) / "NEXUS.md"
    if nexus_md_path.is_file():
        content = nexus_md_path.read_text(encoding="utf-8")
        return {
            "nexus_md_found": True,
            "nexus_md_path": str(nexus_md_path),
            "nexus_md_content": content,
        }
    return {
        "nexus_md_found": False,
        "nexus_md_path": str(nexus_md_path),
        "nexus_md_content": "",
    }


async def post_tool_use_telemetry(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Log tool usage telemetry.

    Args:
        ctx: Must contain ``tool_name``, ``tool_args``, ``tool_result``, ``session_id``.

    Returns:
        A dict with ``tool_name`` and ``logged`` flag, or ``None`` on
        malformed contexts.
    """
    tool_name = ctx.get("tool_name")
    session_id = ctx.get("session_id")
    if tool_name is None or session_id is None:
        return None

    record = {
        "tool_name": tool_name,
        "tool_args": ctx.get("tool_args", {}),
        "tool_result_preview": str(ctx.get("tool_result", ""))[:200],
        "session_id": session_id,
        "ts": datetime.now(UTC).isoformat(),
    }
    logger.info("tool_telemetry: %s", json.dumps(record, sort_keys=True))
    return {"tool_name": tool_name, "logged": True, "session_id": session_id}


async def error_log_to_file(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Write error details to a log file in ``ctx['log_dir']``.

    Args:
        ctx: Must contain ``error_message``, ``session_id``; ``log_dir``
            optional (defaults to ``/tmp/nexusagent_hook_errors``).

    Returns:
        A dict with ``logged`` flag and the path written, or ``None`` on
        malformed input.
    """
    log_dir = ctx.get("log_dir") or "/tmp/nexusagent_hook_errors"
    error_message = ctx.get("error_message")
    if error_message is None:
        return None

    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        session_id = ctx.get("session_id", "unknown")
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        path = os.path.join(log_dir, f"{session_id}-{ts}.json")
        payload = {
            "error_message": str(error_message),
            "session_id": session_id,
            "tool_name": ctx.get("tool_name"),
            "ts": datetime.now(UTC).isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return {"logged": True, "path": path}
    except Exception as exc:
        logger.warning("error_log_to_file failed: %s", exc)
        return {"logged": False, "error": str(exc)}


async def subagent_start_log(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Log sub-agent start lifecycle event.

    Args:
        ctx: Must contain ``subagent_id``; may contain ``subagent_type``,
            ``parent_session_id``, ``task_description``.

    Returns:
        A dict with ``subagent_id``, ``logged`` flag — or ``None`` if
        ``subagent_id`` missing.
    """
    subagent_id = ctx.get("subagent_id")
    if subagent_id is None:
        return None
    record = {
        "event": "subagent_start",
        "subagent_id": subagent_id,
        "subagent_type": ctx.get("subagent_type"),
        "parent_session_id": ctx.get("parent_session_id"),
        "task_description": ctx.get("task_description"),
        "ts": datetime.now(UTC).isoformat(),
    }
    logger.info("subagent_start: %s", json.dumps(record, sort_keys=True))
    return {"subagent_id": subagent_id, "logged": True}


async def subagent_stop_log(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Log sub-agent stop lifecycle event.

    Args:
        ctx: Must contain ``subagent_id``; may contain ``status``,
            ``result_summary``.

    Returns:
        A dict with ``subagent_id``, ``logged`` flag — or ``None`` if
        ``subagent_id`` missing.
    """
    subagent_id = ctx.get("subagent_id")
    if subagent_id is None:
        return None
    record = {
        "event": "subagent_stop",
        "subagent_id": subagent_id,
        "status": ctx.get("status"),
        "result_summary": ctx.get("result_summary"),
        "ts": datetime.now(UTC).isoformat(),
    }
    logger.info("subagent_stop: %s", json.dumps(record, sort_keys=True))
    return {
        "subagent_id": subagent_id,
        "logged": True,
        "status": ctx.get("status"),
    }


__all__ = [
    "error_log_to_file",
    "post_tool_use_telemetry",
    "session_init_load_context",
    "subagent_start_log",
    "subagent_stop_log",
]
