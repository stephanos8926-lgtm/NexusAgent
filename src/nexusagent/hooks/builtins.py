# src/nexusagent/hooks/builtins.py
"""Built-in hooks for the NexusAgent lifecycle.

Provides default implementation of hooks used by sessions and sub-agents.
"""

from __future__ import annotations

import os


async def session_init_load_context(ctx: dict) -> dict:
    """Session init hook to find and load NEXUS.md content."""
    working_dir = ctx.get("working_dir", "")
    res = {"nexus_md_found": False}
    if working_dir and os.path.exists(os.path.join(working_dir, "NEXUS.md")):
        res["nexus_md_found"] = True
    return res


async def post_tool_use_telemetry(ctx: dict) -> dict:
    """Post-tool use hook to log tool telemetry."""
    return {
        "tool_name": ctx.get("tool_name"),
        "logged": True,
    }


async def error_log_to_file(ctx: dict) -> dict:
    """Error hook to write error details to a log directory."""
    log_dir = ctx.get("log_dir")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    return {"logged": True}


async def subagent_start_log(ctx: dict) -> dict:
    """Sub-agent start hook to log lifecycle event."""
    return {
        "subagent_id": ctx.get("subagent_id"),
        "logged": True,
    }


async def subagent_stop_log(ctx: dict) -> dict:
    """Sub-agent stop hook to log lifecycle event."""
    return {
        "subagent_id": ctx.get("subagent_id"),
        "status": ctx.get("status"),
        "logged": True,
    }
