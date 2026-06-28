"""Session helper functions — environment context, git info, prompt building."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


def _extract_agent_response(result) -> str:
    """Extract the last assistant message content from an agent result."""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        text_parts = []
        for block in result:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "thinking":
                    pass
                else:
                    text_parts.append(str(block))
            else:
                text_parts.append(str(block))
        return "\n".join(text_parts) if text_parts else str(result)
    if isinstance(result, dict):
        if "messages" in result:
            from langchain_core.messages import BaseMessage

            messages = result["messages"]
            for msg in reversed(messages):
                if isinstance(msg, BaseMessage) and not isinstance(msg, SystemMessage):
                    content = msg.content
                    if isinstance(content, list):
                        return _extract_agent_response(content)
                    return content or str(msg)
            if messages:
                last = messages[-1]
                content = last.content if isinstance(last, BaseMessage) else str(last)
                if isinstance(content, list):
                    return _extract_agent_response(content)
                return str(content)
            return "No messages in response"
        if "response" in result:
            return str(result["response"])
        if "result" in result:
            return str(result["result"])
        if "content" in result:
            return str(result["content"])
        return str(result)
    return str(result)


def _get_git_info(working_dir: str) -> str:
    """Get git status summary for the working directory."""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=working_dir,
        ).stdout.strip()
        if not branch:
            return ""
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=working_dir,
        ).stdout.strip()
        info = f"Branch: {branch}"
        if status:
            changed = len(status.splitlines())
            info += f" | {changed} changed file{'s' if changed != 1 else ''}"
        else:
            info += " | clean"
        return info
    except Exception:
        return ""


def _build_environment_context(working_dir: str) -> str:
    """Build the environment context block injected into every session."""
    now = datetime.now(UTC)
    user = os.getenv("USER", os.getenv("USERNAME", "unknown"))
    hostname = platform.node()
    os_info = ""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_info = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        os_info = platform.system()

    cwd = str(Path(working_dir).resolve())
    git_info = _get_git_info(working_dir)

    lines = [
        "## Environment",
        f"- **Working Directory**: `{cwd}`",
        f"- **User**: {user}@{hostname}",
        f"- **OS**: {os_info}",
        f"- **Time**: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    if git_info:
        lines.append(f"- **Git**: {git_info}")

    # List available tools
    try:
        from nexusagent.tools.registry import list_all_tools

        tools = list_all_tools()
        if tools:
            by_cat: dict[str, list[str]] = {}
            for t in tools:
                by_cat.setdefault(t.category, []).append(t.name)
            lines.append("\n## Available Tools")
            for cat in sorted(by_cat):
                names = ", ".join(sorted(by_cat[cat]))
                lines.append(f"- **{cat}**: {names}")
    except Exception:
        logger.debug("Failed to list tools for greeting")

    return "\n".join(lines)


def _build_session_history_context(working_dir: str) -> str:
    """Build context from recent sessions for continuity.

    Uses the hybrid memory system to find and summarize recent
    conversation sessions, giving the agent awareness of what
    the user has been working on.
    """
    try:
        # This is a simplified version — in production you'd query
        # the session DB for recent sessions in this working dir
        # and extract summaries. For now, return empty.
        return ""
    except Exception:
        return ""
