"""NEXUS.md prompt file loader with @ chaining and circular detection.

Resolution order:
  1. config/NEXUS.md (package base) — always loaded first
  2. CWD/NEXUS.md (project-specific) — appended if present
  3. Any @file chains discovered during loading

For chat-time injection:
  Type @<path> on its own line in chat to inline a file's content.
  Circular chains are detected via visited-path tracking.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHAIN_DEPTH = 8
MAX_FILE_SIZE = 256 * 1024  # 256KB max per injected file


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

            # Circular detection
            if abs_path in visited:
                raise CircularChainError(
                    f"Circular prompt chain detected: {file_path}"
                )

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
                output_parts.append(
                    f"[prompt: {file_str} — TOO LARGE ({file_size} bytes)]"
                )
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


def load_nexus_prompt(
    package_root: Path | None = None,
    cwd: Path | str | None = None,
    max_depth: int = DEFAULT_MAX_CHAIN_DEPTH,
) -> str:
    """Load the complete NEXUS.md prompt.

    Resolution order:
      1. config/NEXUS.md from package root (base prompt)
      2. NEXUS.md from current working directory (project overrides)
    """
    if package_root is None:
        package_root = Path(__file__).parent.parent.parent

    if cwd is None:
        cwd = Path.cwd()
    elif isinstance(cwd, str):
        cwd = Path(cwd)

    parts: list[str] = []

    # 1. Base prompt from package config
    base_prompt_file = package_root / "config" / "NEXUS.md"
    if base_prompt_file.exists():
        try:
            base_content = base_prompt_file.read_text(encoding="utf-8")
            resolved = load_prompt_content(
                base_content,
                base_prompt_file.parent,
                visited={str(base_prompt_file.resolve())},
                max_depth=max_depth,
                label="NEXUS.md",
            )
            parts.append(resolved)
            logger.info("Loaded base prompt: %s (%d chars)", base_prompt_file, len(resolved))
        except Exception as e:
            logger.error("Failed to load base NEXUS.md: %s", e)
            parts.append(f"[ERROR loading base prompt: {e}]")
    else:
        logger.warning("Base NEXUS.md not found at %s", base_prompt_file)
        parts.append("You are NexusAgent, a helpful AI assistant that operates on the user's machine.")

    # 2. Project-specific prompt from CWD
    cwd_prompt_file = cwd / "NEXUS.md"
    if cwd_prompt_file.exists():
        try:
            cwd_content = cwd_prompt_file.read_text(encoding="utf-8")
            resolved = load_prompt_content(
                cwd_content,
                cwd_prompt_file.parent,
                visited={str(cwd_prompt_file.resolve())},
                max_depth=max_depth,
                label=f"{cwd}/NEXUS.md",
            )
            if resolved.strip():
                parts.append("--- Project Configuration ---")
                parts.append(resolved)
                logger.info("Loaded project prompt: %s", cwd_prompt_file)
        except CircularChainError as e:
            logger.error("Circular chain in project NEXUS.md: %s", e)
            parts.append(f"\n[WARNING: Circular reference in project NEXUS.md: {e}]")
        except Exception as e:
            logger.error("Failed to load project NEXUS.md: %s", e)
            parts.append(f"\n[WARNING: Could not load project prompt: {e}]")
    else:
        logger.debug("No project NEXUS.md found in %s", cwd)

    return "\n\n".join(parts)


def inject_file_at_reference(
    text: str,
    cwd: Path | str | None = None,
    max_depth: int = DEFAULT_MAX_CHAIN_DEPTH,
) -> str:
    """Process @file references in user chat input.

    When a user types @/path/to/file on its own line in chat,
    replace that line with the file's content inline.
    Includes a placeholder header with file path and byte count.
    """
    if cwd is None:
        cwd = Path.cwd()
    elif isinstance(cwd, str):
        cwd = Path(cwd)

    try:
        return load_prompt_content(
            text,
            cwd,
            visited=set(),
            depth=0,
            max_depth=max_depth,
            label="<chat>",
        )
    except (PromptLoadError, CircularChainError) as e:
        logger.warning("File injection error: %s", e)
        return f"[Error processing @ references: {e}]\n\n{text}"


def get_file_info_placeholder(file_path: Path) -> str:
    """Get a placeholder string for an injected file showing path and size."""
    try:
        size = file_path.stat().st_size
        return f"[file: {file_path} ({size:,} bytes)]"
    except Exception:
        return f"[file: {file_path} (size unknown)]"
