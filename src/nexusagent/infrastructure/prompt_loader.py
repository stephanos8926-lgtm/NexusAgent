"""NEXUS.md prompt file loader with @ chaining and circular detection.

Resolution order:
  1. ~/.nexusagent/NEXUS.md (home directory) — always loaded first
  2. config/NEXUS.md (package root) — fallback if home file missing
  3. CWD/NEXUS.md (project-specific) — appended if present
  4. Any @file chains discovered during loading

For chat-time injection:
  Type @<path> on its own line in chat to inline a file's content.
  Circular chains are detected via visited-path tracking.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nexusagent.infrastructure.template_includes import (
    resolve_path as _resolve_path,
    load_prompt_content,
    PromptLoadError,
    CircularChainError,
    DEFAULT_MAX_CHAIN_DEPTH,
)

logger = logging.getLogger(__name__)


def load_nexus_prompt(
    package_root: Path | None = None,
    cwd: Path | str | None = None,
    max_depth: int = DEFAULT_MAX_CHAIN_DEPTH,
) -> str:
    """Load the complete NEXUS.md prompt.

    Resolution order:
      1. ~/.nexusagent/NEXUS.md from home directory (base prompt)
      2. config/NEXUS.md from package root (fallback)
      3. NEXUS.md from current working directory (project overrides)
    """
    if package_root is None:
        package_root = Path(__file__).parent.parent.parent

    if cwd is None:
        cwd = Path.cwd()
    elif isinstance(cwd, str):
        cwd = Path(cwd)

    parts: list[str] = []

    # 1. Base prompt from ~/.nexusagent/NEXUS.md (home directory)
    base_prompt_file = Path.home() / ".nexusagent" / "NEXUS.md"
    if not base_prompt_file.exists():
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
