"""Event handling and slash commands for the TUI.

Handles:
- WebSocket event dispatch (tool_call, response_chunk, response, error, etc.)
- Slash command parsing and execution
- Theme cycling and help display
"""

from __future__ import annotations

import json
import logging

from nexusagent.infrastructure.config import settings
from nexusagent.version import VERSION as CLIENT_VERSION

# Message widgets imported here (not top) to avoid circular import with widgets.messages
# These are used in slash command handlers defined later in this file.
from nexusagent.widgets.messages import (
    AppMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
)
from nexusagent.widgets.theme.colors import ALL_THEMES

# Maximum message widgets mounted in the TUI (sliding window)
_STREAMING_MAX_WIDGETS = 50


def _mount_with_limit(app, widget) -> None:
    """Mount a message widget with a sliding window limit.

    Always delegates to app._mount_with_limit() to enforce the global limit.
    Fallback to direct mount if the method doesn't exist yet.
    """
    if hasattr(app, "_mount_with_limit"):
        app._mount_with_limit(widget)
    else:
        # Fallback: direct mount with manual sliding window cleanup
        app.messages_container.mount(widget)
        children = list(app.messages_container.children)
        while len(children) > _STREAMING_MAX_WIDGETS:
            oldest = children.pop(0)
            oldest.remove()


logger = logging.getLogger(__name__)


async def handle_event(app, event: dict) -> None:
    """Dispatch a WebSocket event to the appropriate handler.

    Args:
        app: The NexusApp instance.
        event: The event dict from the WebSocket.
    """
    etype = event.get("type")

    if etype == "session_status":
        pass

    elif etype == "thinking":
        content = event.get("content", "")
        # Show thinking as a visible message widget in the chat
        thinking_msg = AppMessage(message=f"💭 {content}")
        _mount_with_limit(app, thinking_msg)
        app.status_bar.set_status("Thinking...")
        app._thinking_visible = True

    elif etype == "tool_call":
        _handle_tool_call_event(app, event)

    elif etype == "tool_result":
        _handle_tool_result_event(app, event)

    elif etype == "tool_error":
        tool = event.get("tool", "?")
        error = event.get("error", "Unknown error")
        err_msg = ErrorMessage(message=f"{tool}: {error}")
        _mount_with_limit(app, err_msg)
        app.status_bar.set_status(f"Error in {tool}")

    elif etype == "approval_request":
        call_id = event.get("call_id", "")
        if app._auto_approve:
            # Auto-approve: skip the modal, send approval directly
            from nexusagent.interfaces.tui.websocket import send_approval

            await send_approval(app, call_id, True)
            app.status_bar.set_status("Ready")
        else:
            tool = event.get("tool", "?")
            args = event.get("args", {})
            app.status_bar.set_status("Awaiting approval...")
            from nexusagent.interfaces.tui_widgets import ApprovalModal

            approved = await app.push_screen_wait(ApprovalModal(tool, args, call_id))
            from nexusagent.interfaces.tui.websocket import send_approval

            await send_approval(app, call_id, approved)
            app.status_bar.set_status("Ready")

    elif etype == "response_chunk":
        content = event.get("content", "")
        if app._current_assistant is None:
            from nexusagent.widgets.messages import AssistantMessage

            app._current_assistant = AssistantMessage()
            _mount_with_limit(app, app._current_assistant)
        await app._current_assistant.append_token(content)
        app.status_bar.set_status("Streaming...")

    elif etype == "response":
        content = event.get("content", "")
        if app._current_assistant:
            # Pass raw content to AssistantMessage — it uses Textual Markdown widget
            final = content if content else None
            if final:
                app._current_assistant.finalize(final)
            app._current_assistant = None
        elif content:
            from nexusagent.widgets.messages import AssistantMessage

            msg = AssistantMessage()
            msg.finalize(content)
            _mount_with_limit(app, msg)

        app._busy = False
        app.status_bar.set_spinner(False)
        process_next_in_queue(app)
        app.status_bar.set_status("Ready")
        app._current_tool = None
        # Auto-scroll to bottom after response — use call_later because
        # layout dimensions haven't updated yet when widgets were just mounted
        try:
            chat = app.query_one("#chat")
            app.call_later(chat.scroll_end, animate=False)
        except Exception:
            pass

        app._request_count += 1
        tokens = event.get("tokens_used", 0)
        if tokens:
            app._total_tokens_used += tokens
            app.status_bar.set_tokens(app._total_tokens_used)
        ctx_used = event.get("context_used", 0)
        ctx_limit = event.get("context_limit", 0)
        if ctx_used and ctx_limit:
            app._context_used = ctx_used
            app._context_limit = ctx_limit
            app.status_bar.set_context(ctx_used, ctx_limit)
        app._busy = False
        app.status_bar.set_spinner(False)
        process_next_in_queue(app)
        app.status_bar.set_status("Ready")
        app._current_tool = None

    elif etype == "error":
        message = event.get("message", "Unknown error")
        _mount_error(app, message)
        app._busy = False
        app.status_bar.set_spinner(False)
        process_next_in_queue(app)
        app.status_bar.set_status("Error")

    elif etype == "session_closed":
        app.status_bar.set_status("Disconnected")
        app._busy = False
        app.status_bar.set_spinner(False)
        app._ws = None

    elif etype == "session_list":
        sessions = event.get("sessions", [])
        if sessions:
            lines = [f"Active Sessions ({len(sessions)})"]
            for s in sessions[:10]:
                sid = s.get("id", "?")[:12]
                status = s.get("status", "?")
                lines.append(f"  {sid}... [{status}]")
            msg = AppMessage("\n".join(lines))
            _mount_with_limit(app, msg)

    elif etype == "compact_result":
        status = event.get("status", "unknown")
        if status == "ok":
            summary = event.get("summary", "")[:100]
            msg = AppMessage(f"Compaction complete. {summary}")
            app.status_bar.set_status("Compaction done")
        else:
            error = event.get("error", "Unknown error")
            msg = AppMessage(f"Compaction failed: {error}")
            app.status_bar.set_status("Compaction failed")
        _mount_with_limit(app, msg)
        app._busy = False


def _handle_tool_call_event(app, event: dict) -> None:
    """Handle a tool_call event.

    Args:
        app: The NexusApp instance.
        event: The tool_call event dict.
    """
    tool = event.get("tool", "?")
    args = event.get("args", {})
    app._last_tool_name = tool

    msg = ToolCallMessage(
        tool=tool,
        args=args,
        status="running",
    )
    app._current_tool = msg
    _mount_with_limit(app, msg)

    if app._auto_approve and tool != "tool_search":
        from nexusagent.interfaces.tui.websocket import send_approval

        call_id = event.get("call_id", "")
        app._auto_approve_task = (
            __import__("asyncio").get_event_loop().create_task(send_approval(app, call_id, True))
        )

    app.status_bar.set_status(f"Running: {tool}")


def _handle_tool_result_event(app, event: dict) -> None:
    """Handle a tool_result event.

    Args:
        app: The NexusApp instance.
        event: The tool_result event dict.
    """
    output = event.get("output", "")
    success = event.get("success", True)

    if app._current_tool:
        app._current_tool.update_output(output)
        app._current_tool.update_status("success" if success else "failed")
    else:
        msg = ToolCallMessage(
            tool=app._last_tool_name,
            args="",
            output=output,
            status="success" if success else "failed",
        )
        _mount_with_limit(app, msg)

    app.status_bar.set_status("Processing response...")


def _mount_error(app, message: str) -> None:
    """Mount an error message in the TUI.

    Args:
        app: The NexusApp instance.
        message: The error message to display.
    """
    err = ErrorMessage(message=message)
    _mount_with_limit(app, err)


async def handle_slash_command(app, cmd: str) -> bool:
    """Parse and execute a slash command.

    Args:
        app: The NexusApp instance.
        cmd: The command string (including the leading /).

    Returns:
        True if the command was handled, False otherwise.
    """
    parts = cmd.strip().lower().split()
    command = parts[0] if parts else ""
    rest = parts[1:] if len(parts) > 1 else []

    if command in ("/help", "/h"):
        show_help(app)
        return True
    if command in ("/search", "/s"):
        query = " ".join(rest)
        if not query:
            msg = AppMessage("Usage: /search <query>")
            _mount_with_limit(app, msg)
            return True
        # Run search_web in background
        import asyncio

        from nexusagent.tools.research import search_web

        async def _do_search():
            result = search_web(query)
            msg = AppMessage(f"Search results for: {query}\n\n{result}")
            _mount_with_limit(app, msg)

        _ = asyncio.create_task(_do_search())  # noqa: RUF006
        msg = AppMessage(f"Searching for: {query}...")
        _mount_with_limit(app, msg)
        return True
    if command in ("/fetch", "/f"):
        url = " ".join(rest)
        if not url:
            msg = AppMessage("Usage: /fetch <url>")
            _mount_with_limit(app, msg)
            return True
        from nexusagent.tools.research import fetch_url

        async def _do_fetch():
            result = fetch_url(url)
            msg = AppMessage(f"Fetched: {url}\n\n{result}")
            _mount_with_limit(app, msg)

        _ = asyncio.create_task(_do_fetch())  # noqa: RUF006
        msg = AppMessage(f"Fetching: {url}...")
        _mount_with_limit(app, msg)
        return True
    if command in ("/new", "/n"):
        app.messages_container.clear()
        app._current_assistant = None
        app._current_tool = None
        app._seen_tool_calls.clear()
        app._seen_tool_results.clear()
        app._show_greeting()
        return True
    if command == "/clear":
        app.messages_container.clear()
        app._current_assistant = None
        app._current_tool = None
        app._show_greeting()
        return True
    if command in ("/expand", "/e"):
        return True  # Widgets auto-expand
    if command in ("/collapse", "/a"):
        return True  # TODO: collapse all
    if command in ("/quit", "/q"):
        app.action_quit()
        return True
    if command == "/status":
        status = "busy" if app._busy else "ready"
        auto = "ON" if app._auto_approve else "OFF"
        msg = AppMessage(
            f"Status: {status} | Session: {app.session_id} | "
            f"Queued: {len(app._pending_inputs)} | Auto-approve: {auto} | "
            f"Tokens: {app._total_tokens_used:,} | Requests: {app._request_count}"
        )
        _mount_with_limit(app, msg)
        return True
    if command == "/version":
        msg = AppMessage(
            f"NexusAgent {CLIENT_VERSION} | Model: {settings.agent.default_model} | "
            f"Session: {app.session_id} | Theme: {app._theme_name}"
        )
        _mount_with_limit(app, msg)
        return True
    if command == "/tokens":
        avg = app._total_tokens_used // app._request_count if app._request_count > 0 else 0
        msg = AppMessage(
            f"Token Usage\n"
            f"  Total: {app._total_tokens_used:,}\n"
            f"  Requests: {app._request_count}\n"
            f"  Avg/request: {avg:,}\n"
            f"  Model: {settings.agent.default_model}"
        )
        _mount_with_limit(app, msg)
        return True
    if command == "/model":
        msg = AppMessage(
            f"Model: {settings.agent.default_model}\n"
            f"Provider: {settings.agent.primary_provider}\n"
            f"Session: {app.session_id}"
        )
        _mount_with_limit(app, msg)
        return True
    if command == "/theme":
        cycle_theme(app)
        return True
    if command == "/auto":
        app.action_toggle_auto_approve()
        return True
    if command == "/compact":
        if app._ws and app._ws.open:
            await app._ws.send(json.dumps({"type": "compact"}))
            app.status_bar.set_status("Compacting...")
        return True
    if command == "/copy":
        msg = AppMessage("Copy not available — use terminal selection")
        _mount_with_limit(app, msg)
        return True
    if command == "/sessions":
        msg = AppMessage(f"Session: {app.session_id}")
        _mount_with_limit(app, msg)
        return True
    if command == "/threads":
        if app._ws and app._ws.open:
            await app._ws.send(json.dumps({"type": "list_sessions"}))
        return True
    if command == "/interrupt":
        app.action_interrupt()
        return True
    if command == "/undo":
        if app._ws and app._ws.open:
            await app._ws.send(json.dumps({"type": "undo"}))
        return True
    if command == "/redo":
        if app._ws and app._ws.open:
            await app._ws.send(json.dumps({"type": "redo"}))
        return True
    if command == "/skills":
        from nexusagent.skills import get_skills_summary, load_all_skills

        skills = load_all_skills()
        if skills:
            get_skills_summary(skills)
            lines = [f"Available Skills ({len(skills)})"]
            for name, skill in sorted(skills.items()):
                desc = skill.description or "No description"
                lines.append(f"  {name}: {desc}")
            msg = AppMessage("\n".join(lines))
            _mount_with_limit(app, msg)
        return True
    if command.startswith("/skill"):
        skill_name = rest[0] if rest else ""
        if not skill_name:
            msg = AppMessage("Usage: /skill <name>")
            _mount_with_limit(app, msg)
            return True
        from nexusagent.skills import get_skill_content, load_all_skills

        skills = load_all_skills()
        skill_content = get_skill_content(skills, skill_name)
        if skill_content:
            lines = [f"Skill: {skill_name}"]
            for line in skill_content.split("\n")[:20]:
                lines.append(f"  {line}")
            if len(skill_content.split("\n")) > 20:
                lines.append(f"  ... ({len(skill_content.split(chr(10)))} lines total)")
            msg = AppMessage("\n".join(lines))
            _mount_with_limit(app, msg)
        return True

    msg = AppMessage(f"Unknown command: {command}. Type /help for available commands.")
    _mount_with_limit(app, msg)
    return True


def cycle_theme(app) -> None:
    """Cycle to the next available theme.

    Args:
        app: The NexusApp instance.
    """
    try:
        idx = ALL_THEMES.index(app._theme_name)
        app._theme_name = ALL_THEMES[(idx + 1) % len(ALL_THEMES)]
    except ValueError:
        app._theme_name = "nexus-dark"
    app.theme = app._theme_name
    msg = AppMessage(f"Theme: {app._theme_name}")
    _mount_with_limit(app, msg)


def show_help(app) -> None:
    """Show the help panel.

    Args:
        app: The NexusApp instance.
    """
    lines = [
        "Available Commands",
        "  /help      Show this help",
        "  /search <q> Web search (Exa/Tavily)",
        "  /fetch <url> Fetch URL content",
        "  /new       New conversation",
        "  /clear     Clear messages",
        "  /expand    Expand all",
        "  /collapse  Collapse all",
        "  /status    Session status",
        "  /compact   Trigger compaction",
        "  /version   Version info",
        "  /tokens    Token usage",
        "  /model     Model info",
        "  /theme     Cycle theme",
        "  /auto      Toggle auto-approve",
        "  /skills    List skills",
        "  /skill <n> Show skill",
        "  /quit      Exit",
        "",
        "Keyboard Shortcuts",
        "  Ctrl+C  Interrupt",
        "  Q       Quit",
        "  C       Clear",
        "  E       Expand",
        "  A       Collapse",
    ]
    msg = AppMessage("\n".join(lines))
    _mount_with_limit(app, msg)


def format_args_str(app, args: dict) -> str:
    """Format tool arguments for display.

    Args:
        app: The NexusApp instance (unused, kept for compat).
        args: The arguments dict.

    Returns:
        Formatted string representation.
    """
    from nexusagent.interfaces.tui_formatters import format_arg_value, truncate

    if not isinstance(args, dict):
        return truncate(format_arg_value(args), 80)
    parts = []
    for k, v in args.items():
        parts.append(f"{k}={truncate(format_arg_value(v), 60)}")
    return ", ".join(parts)


def process_next_in_queue(app) -> None:
    """Process the next message in the input queue.

    Args:
        app: The NexusApp instance.
    """
    if not app._pending_inputs:
        return
    next_msg = app._pending_inputs.pop(0)
    app._busy = True
    user_msg = UserMessage(content=next_msg)
    _mount_with_limit(app, user_msg)
    app.status_bar.set_status("Thinking...")
    app.status_bar.set_spinner(True)
    import asyncio

    asyncio.create_task(app._input_queue.put(next_msg))  # noqa: RUF006
    update_queue_status(app)


def update_queue_status(app) -> None:
    """Update the status bar with the current queue count.

    Args:
        app: The NexusApp instance.
    """
    count = len(app._pending_inputs)
    if count > 0:
        app.status_bar.set_status(f"{count} queued")
