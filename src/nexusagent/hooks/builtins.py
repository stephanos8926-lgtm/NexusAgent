# src/nexusagent/hooks/builtins.py
"""Built-in hooks for NexusAgent.

These hooks provide default functionality:
- session_init_load_context: Loads project context (NEXUS.md, .nexusagent/)
- post_tool_use_telemetry: Logs tool usage to telemetry
- error_log_to_file: Logs errors to file with context
- subagent_start_log: Logs sub-agent start lifecycle
- subagent_stop_log: Logs sub-agent stop lifecycle
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def session_init_load_context(context: dict[str, Any]) -> dict[str, Any]:
    """Load project context at session start.

    Reads NEXUS.md from the working directory and .nexusagent/ directory,
    injecting project-specific context into the session.

    Context keys expected:
        - working_dir: Path to the working directory
        - config: ConfigSchema instance

    Returns:
        Dict with keys: nexus_md_found (bool), nexus_md_content (str),
        nexusagent_dir_found (bool), nexusagent_files (list[str])
    """
    working_dir = context.get("working_dir", ".")
    result: dict[str, Any] = {
        "nexus_md_found": False,
        "nexus_md_content": "",
        "nexusagent_dir_found": False,
        "nexusagent_files": [],
    }

    # Load NEXUS.md from working directory
    nexus_path = Path(working_dir) / "NEXUS.md"
    if nexus_path.exists():
        try:
            content = nexus_path.read_text(encoding="utf-8")
            result["nexus_md_found"] = True
            result["nexus_md_content"] = content
            logger.debug("Loaded NEXUS.md from %s (%d chars)", working_dir, len(content))
        except Exception as exc:
            logger.warning("Failed to read NEXUS.md: %s", exc)

    # Check .nexusagent/ directory
    nexusagent_dir = Path(working_dir) / ".nexusagent"
    if nexusagent_dir.is_dir():
        result["nexusagent_dir_found"] = True
        try:
            result["nexusagent_files"] = [
                str(p.relative_to(nexusagent_dir))
                for p in nexusagent_dir.rglob("*")
                if p.is_file()
            ]
            logger.debug("Found %d files in .nexusagent/", len(result["nexusagent_files"]))
        except Exception as exc:
            logger.warning("Failed to list .nexusagent/: %s", exc)

    return result


async def post_tool_use_telemetry(context: dict[str, Any]) -> dict[str, Any]:
    """Log tool usage to telemetry after each tool execution.

    Context keys expected:
        - tool_name: Name of the tool that was called
        - tool_args: Arguments passed to the tool
        - tool_result: Result returned by the tool (optional)
        - session_id: Current session ID
        - duration: Tool execution duration in seconds (optional)

    Returns:
        Dict with logged tool call info.
    """
    tool_name = context.get("tool_name", "unknown")
    session_id = context.get("session_id", "unknown")
    duration = context.get("duration")

    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "tool_name": tool_name,
        "session_id": session_id,
        "logged": True,
    }
    if duration is not None:
        entry["duration"] = duration

    logger.info(
        "Tool '%s' used in session '%s'%s",
        tool_name,
        session_id,
        f" ({duration:.2f}s)" if duration else "",
    )

    return entry


async def error_log_to_file(context: dict[str, Any]) -> dict[str, Any]:
    """Log errors to a dedicated error log file with full context.

    Context keys expected:
        - error_message: The error message
        - session_id: Current session ID
        - tool_name: Tool that caused the error (optional)
        - working_dir: Working directory (optional)
        - log_dir: Directory for error logs (optional, defaults to ~/.nexusagent/errors)

    Returns:
        Dict with logged error info.
    """
    error_message = context.get("error_message", "Unknown error")
    session_id = context.get("session_id", "unknown")
    tool_name = context.get("tool_name")
    working_dir = context.get("working_dir", ".")
    log_dir = context.get("log_dir", os.path.expanduser("~/.nexusagent/errors"))

    os.makedirs(log_dir, exist_ok=True)

    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "error_message": error_message,
        "session_id": session_id,
        "working_dir": working_dir,
        "logged": True,
    }
    if tool_name:
        entry["tool_name"] = tool_name

    # Write to error log file
    log_file = Path(log_dir) / "errors.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("Failed to write error log: %s", exc)
        entry["logged"] = False

    logger.error("Error in session '%s': %s", session_id, error_message)
    return entry


async def subagent_start_log(context: dict[str, Any]) -> dict[str, Any]:
    """Log sub-agent start lifecycle event.

    Context keys expected:
        - subagent_id: ID of the sub-agent
        - subagent_type: Type of sub-agent (e.g., "explore", "code")
        - parent_session_id: ID of the parent session
        - task_description: Description of the task

    Returns:
        Dict with logged sub-agent start info.
    """
    subagent_id = context.get("subagent_id", "unknown")
    subagent_type = context.get("subagent_type", "unknown")
    parent_session_id = context.get("parent_session_id", "unknown")
    task_description = context.get("task_description", "")

    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "event": "subagent_start",
        "subagent_id": subagent_id,
        "subagent_type": subagent_type,
        "parent_session_id": parent_session_id,
        "task_description": task_description,
        "logged": True,
    }

    logger.info(
        "Sub-agent '%s' (type=%s) started in session '%s': %s",
        subagent_id, subagent_type, parent_session_id, task_description[:80],
    )
    return entry


async def subagent_stop_log(context: dict[str, Any]) -> dict[str, Any]:
    """Log sub-agent stop lifecycle event.

    Context keys expected:
        - subagent_id: ID of the sub-agent
        - subagent_type: Type of sub-agent
        - parent_session_id: ID of the parent session
        - status: Completion status (e.g., "completed", "failed", "cancelled")
        - duration: Wall time in seconds (optional)

    Returns:
        Dict with logged sub-agent stop info.
    """
    subagent_id = context.get("subagent_id", "unknown")
    subagent_type = context.get("subagent_type", "unknown")
    parent_session_id = context.get("parent_session_id", "unknown")
    status = context.get("status", "unknown")
    duration = context.get("duration")

    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "event": "subagent_stop",
        "subagent_id": subagent_id,
        "subagent_type": subagent_type,
        "parent_session_id": parent_session_id,
        "status": status,
        "logged": True,
    }
    if duration is not None:
        entry["duration"] = duration

    logger.info(
        "Sub-agent '%s' (type=%s) stopped in session '%s': status=%s%s",
        subagent_id, subagent_type, parent_session_id, status,
        f" ({duration:.2f}s)" if duration else "",
    )
    return entry
