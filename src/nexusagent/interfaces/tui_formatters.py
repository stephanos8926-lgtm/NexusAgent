"""TUI output formatting and markdown rendering utilities.

Extracted from interfaces/tui.py to reduce the 1433L monolith.
Contains: all _format_* methods, markdown renderers, truncation, escaping.
"""

import json
import logging
import re
import textwrap
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Markdown rendering (unified — replaces _simple_markdown + _enhanced_markdown)
# ═══════════════════════════════════════════════════════════════════════════


def render_markdown(text: str, *, code_blocks: bool = True) -> str:
    """Render markdown-like text to RichLog markup.

    Single unified renderer replacing the old _simple_markdown / _enhanced_markdown
    pair. Handles bold, italic, inline code, and optionally fenced code blocks.

    Args:
        text: Raw markdown text.
        code_blocks: If True, extract and format fenced code blocks.
                     If False, strip them (for simple display).
    """
    if code_blocks:
        # Extract code blocks first, replace with placeholders
        code_blocks_list: list[tuple[str, str]] = []

        def replace_code_block(m: re.Match) -> str:
            lang = m.group(1) or ""
            code = m.group(2)
            idx = len(code_blocks_list)
            code_blocks_list.append((lang, code))
            return f"__CODE_BLOCK_{idx}__"

        text = re.sub(r'```(\w*)\n(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'[reverse]\1[/reverse]', text)

    # Bold and italic
    text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'[i]\1[/i]', text)

    if code_blocks:
        # Restore code blocks with dim/styled formatting
        for i, (lang, code) in enumerate(code_blocks_list):
            lang_label = f"[dim]({lang})[/dim] " if lang else ""
            code_lines = code.split("\n")
            if len(code_lines) > 20:
                code = "\n".join(code_lines[:20]) + f"\n[dim]... +{len(code_lines) - 20} more lines[/dim]"
            styled = f"{lang_label}[dim]{code}[/dim]"
            text = text.replace(f"__CODE_BLOCK_{i}__", styled)

    return text


# ═══════════════════════════════════════════════════════════════════════════
# Output formatting — per-tool display formatters
# ═══════════════════════════════════════════════════════════════════════════


def format_tool_result_for_display(
    tool_name: str, success: bool, output: str,
    max_chars: int = 400,
) -> str:
    """Format a tool result for display using per-tool dispatch."""
    if not output or not output.strip():
        return "[dim](empty)[/dim]"

    dispatch = {
        "run_shell": format_shell_output,
        "run_shell_streaming": format_shell_output,
        "shell": format_shell_output,
        "read_file": format_read_file_output,
        "read_multiple_files": format_read_file_output,
        "write_file": lambda o: format_write_file_output(o, tool_name),
        "write_multiple_files": lambda o: format_write_file_output(o, tool_name),
        "edit_file": lambda o: format_write_file_output(o, tool_name),
        "apply_patch": lambda o: format_write_file_output(o, tool_name),
    }

    # Git tools
    if tool_name.startswith("git_"):
        return format_git_output(output, tool_name)

    # Search tools
    if tool_name in ("search_web", "search_local_docs"):
        return format_search_output(output)

    # Subagent
    if tool_name == "spawn_subagent":
        return format_subagent_output(output)

    # Matched tool
    if tool_name in dispatch:
        return dispatch[tool_name](output)

    # Default: generic JSON/smart formatter
    return format_tool_output_generic(output, max_chars)


def format_shell_output(output: str) -> str:
    """Format shell command output: show exit code + truncated stdout."""
    lines = output.strip().split("\n")
    exit_code = None
    clean_lines = []
    for line in lines:
        if line.startswith("Exit code:") or line.startswith("exit code:"):
            with ContextlibSuppress(ValueError):
                exit_code = int(line.split(":")[-1].strip())
        elif not line.startswith("Error:"):
            clean_lines.append(line)

    result = "\n".join(clean_lines[:15])
    suffix = ""
    if len(clean_lines) > 15:
        suffix = f"\n[dim]... +{len(clean_lines) - 15} more lines[/dim]"

    code_str = ""
    if exit_code is not None:
        code_color = "green" if exit_code == 0 else "red"
        code_str = f"[{code_color}]exit {exit_code}[/{code_color}] "

    return f"{code_str}{result}{suffix}"


def format_read_file_output(output: str) -> str:
    """Format read_file output: show line count + content preview."""
    lines = output.strip().split("\n")
    content_lines = [line for line in lines if not re.match(r'^\d+\|', line)]
    line_count = len(content_lines)

    preview_lines = content_lines[:12]
    preview = "\n".join(preview_lines)
    suffix = ""
    if line_count > 12:
        suffix = f"\n[dim]... +{line_count - 12} more lines[/dim]"

    return f"[b cyan]({line_count} lines)[/b cyan] {preview}{suffix}"


def format_write_file_output(output: str, tool_name: str) -> str:
    """Format write_file/edit_file output: show success indicator."""
    cleaned = output.strip()
    path_match = re.search(
        r'(?:written|saved|patched)\s+(?:to\s+)?["\']?([\w./~_-]+)["\']?',
        cleaned, re.IGNORECASE,
    )
    path = path_match.group(0) if path_match else cleaned[:80]
    return f"[green]✓ {tool_name}[/green] → {path}"


def format_git_output(output: str, tool_name: str) -> str:
    """Format git tool output: show command + result summary."""
    lines = output.strip().split("\n")
    meaningful = [line for line in lines if line.strip()][:10]
    result = "\n".join(meaningful)
    suffix = ""
    if len(lines) > 10:
        suffix = f"\n[dim]... +{len(lines) - 10} more lines[/dim]"
    return f"[b orange]git {tool_name[4:]}[/b orange] {result}{suffix}"


def format_search_output(output: str) -> str:
    """Format search_web output: show result count + top URLs."""
    result_count = output.count("Title:")
    urls = re.findall(r'URL:\s*(\S+)', output)
    url_preview = "\n".join(f"  🔗 {u}" for u in urls[:3])
    suffix = ""
    if len(urls) > 3:
        suffix = f"\n[dim]  ... +{len(urls) - 3} more URLs[/dim]"
    return f"[b cyan]({result_count} results)[/b cyan]\n{url_preview}{suffix}"


def format_subagent_output(output: str) -> str:
    """Format spawn_subagent output: show task + status."""
    cleaned = output.strip()
    id_match = re.search(r'worker\s+(\S+)', cleaned)
    status_match = re.search(r'status:\s*(\w+)', cleaned)
    worker_id = id_match.group(1) if id_match else "?"
    status = status_match.group(1) if status_match else "?"
    return f"[b purple]subagent {worker_id}[/b purple] status: [yellow]{status}[/yellow]"


def format_tool_output_generic(output: str, max_chars: int = 400) -> str:
    """Format tool output — parse JSON into human-readable form."""
    if not output or not output.strip():
        return "[dim](empty)[/dim]"

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            for key in ("content", "result", "output", "stdout", "text", "message", "data"):
                if data.get(key):
                    val = data[key]
                    if isinstance(val, str):
                        return _escape(val.strip())
                    return _escape(json.dumps(val, indent=2, default=str))
            preview = {}
            for k, v in list(data.items())[:6]:
                v_str = str(v)
                if len(v_str) > 120:
                    v_str = v_str[:117] + "..."
                preview[k] = v_str
            lines = [f"[b]{k}[/b]: {v}" for k, v in preview.items()]
            if len(data) > 6:
                lines.append(f"[dim]... +{len(data) - 6} more keys[/dim]")
            return "\n".join(lines)
        if isinstance(data, list):
            if len(data) == 0:
                return "[dim](empty list)[/dim]"
            if len(data) <= 5:
                items = []
                for item in data:
                    s = str(item)
                    if len(s) > 200:
                        s = s[:197] + "..."
                    items.append(f"  • {s}")
                return "\n".join(items)
            items = []
            for item in data[:5]:
                s = str(item)
                if len(s) > 200:
                    s = s[:197] + "..."
                items.append(f"  • {s}")
            items.append(f"[dim]  ... +{len(data) - 5} more items[/dim]")
            return "\n".join(items)
        return _escape(str(data))
    except (json.JSONDecodeError, TypeError):
        pass

    cleaned = output.strip()
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return _escape(cleaned)


# ═══════════════════════════════════════════════════════════════════════════
# Truncation and escaping
# ═══════════════════════════════════════════════════════════════════════════


def truncate_output(output: str, max_chars: int = 400) -> str:
    """Truncate long output with head/tail and char count indicator."""
    if len(output) <= max_chars:
        return output
    head = output[:max_chars // 2]
    tail = output[-(max_chars // 2):]
    return f"{head}\n[dim]... ({len(output):,} chars total) ...[/dim]\n{tail}"


def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def format_arg_value(value: Any) -> str:
    """Format a tool argument value for display."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and len(value) > 200:
        return textwrap.shorten(value, width=200, placeholder="...")
    return _escape(str(value))


def _escape(text: str) -> str:
    """Escape RichLog markup characters in text."""
    return text.replace("[", "\\[").replace("]", "\\]")


# ── Contextlib suppress helper (avoids import at module level) ─────────────

class ContextlibSuppress:
    """Minimal context manager to suppress specific exceptions."""

    def __init__(self, *exceptions):
        """Initialize with the exception types to suppress.

        Args:
            *exceptions: Exception classes to catch and suppress.
        """
        self.exceptions = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return bool(exc_type is not None and issubclass(exc_type, self.exceptions))
