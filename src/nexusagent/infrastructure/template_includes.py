"""Template include logic — @file chain resolution for prompts.

Handles recursive @file injection with circular detection and size limits.
Used by prompt_loader.py for NEXUS.md loading and chat-time file injection.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHAIN_DEPTH = 8
MAX_FILE_SIZE = 256 * 1024  # 256KB max per injected file

# Allowed base directories for @file includes.
# Only files within these directories (or their subdirectories) are permitted.
_ALLOWED_INCLUDE_PATHS: list[Path] = []


def set_allowed_include_paths(paths: list[Path]) -> None:
    """Set the allowlist of base directories for @file includes.

    Args:
        paths: List of resolved, absolute Path objects. Only files within
               these directories (or their subdirectories) will be allowed.
    """
    _ALLOWED_INCLUDE_PATHS.clear()
    _ALLOWED_INCLUDE_PATHS.extend(paths)


def _is_path_allowed(resolved: Path) -> bool:
    """Check whether *resolved* (absolute) path is within the allowlist."""
    for base in _ALLOWED_INCLUDE_PATHS:
        try:
            resolved.relative_to(base)
            return True
        except ValueError:
            continue
    return False


class PromptLoadError(Exception):
    """Raised when a prompt file cannot be loaded."""

    pass


class CircularChainError(PromptLoadError):
    """Raised when a circular @file chain is detected."""

    pass


def resolve_path(path_str: str, relative_to: Path | None = None) -> Path:
    """Resolve a path string to an absolute Path."""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return p
    base = relative_to or Path.cwd()
    return (base / p).resolve()


def load_prompt_content(
    content: str,
    current_dir: Path,
    visited: set[str] | None = None,
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_CHAIN_DEPTH,
    label: str = "",
) -> str:
    """Recursively load prompt content, resolving @file chains.

    Only lines where @ is the first character (no space after) are treated
    as file references. "@ something" is kept as-is.
    """
    if visited is None:
        visited = set()

    if depth > max_depth:
        raise PromptLoadError(
            f"Max prompt chain depth ({max_depth}) exceeded at {label}. "
            "Check for deep or circular @file references."
        )

    lines = content.split("\n")
    output_parts: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Only match "@/path" or "@path" — @ must be first char, no space after
        if stripped.startswith("@") and len(stripped) > 1 and stripped[1] != " ":
            file_str = stripped[1:].strip()
            if not file_str:
                output_parts.append(line)
                continue

            file_path = resolve_path(file_str, current_dir)
            abs_path = str(file_path.resolve())

            # SECURITY: Path allowlist check — only allow files within permitted dirs
            if _ALLOWED_INCLUDE_PATHS and not _is_path_allowed(file_path.resolve()):
                logger.warning("Prompt chain path blocked by allowlist: %s", file_path)
                output_parts.append(f"[prompt: {file_str} — BLOCKED by path allowlist]")
                continue

            # Circular detection
            if abs_path in visited:
                raise CircularChainError(f"Circular prompt chain detected: {file_path}")

            if not file_path.exists():
                logger.warning("Prompt chain file not found: %s", file_path)
                output_parts.append(f"[prompt: {file_str} — NOT FOUND]")
                continue

            if not file_path.is_file():
                logger.warning("Prompt chain path is not a file: %s", file_path)
                output_parts.append(f"[prompt: {file_str} — NOT A FILE]")
                continue

            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                logger.warning("Prompt chain file too large (%d bytes): %s", file_size, file_path)
                output_parts.append(f"[prompt: {file_str} — TOO LARGE ({file_size} bytes)]")
                continue

            try:
                file_content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.error("Failed to read prompt chain file %s: %s", file_path, e)
                output_parts.append(f"[prompt: {file_str} — READ ERROR: {e}]")
                continue

            # Recursively resolve chains within this file
            new_visited = {*visited, abs_path}
            resolved = load_prompt_content(
                file_content,
                file_path.parent,
                visited=new_visited,
                depth=depth + 1,
                max_depth=max_depth,
                label=f"{label}/{file_path.name}" if label else file_path.name,
            )

            # Inject with file header showing path and size
            header = f"[Injected: {file_path} ({file_size:,} bytes)]"
            output_parts.append(f"{header}\n{resolved}")
            logger.debug("Prompt chain loaded: %s (%d bytes)", file_path, file_size)

        else:
            output_parts.append(line)

    return "\n".join(output_parts)
