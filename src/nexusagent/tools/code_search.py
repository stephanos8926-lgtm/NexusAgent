"""
Code search tool for NexusAgent.

Provides local code search using ripgrep (rg) with structured output.
Falls back to grep if ripgrep is not available.
"""

import re
import shutil
import subprocess


def _has_rg() -> bool:
    """Check if ripgrep is available."""
    return shutil.which("rg") is not None


def search_code(
    query: str,
    path: str = ".",
    file_pattern: str | None = None,
    context_lines: int = 2,
    max_results: int = 50,
    case_sensitive: bool = False,
) -> str:
    """
    Search code using ripgrep (or grep as fallback).

    Args:
        query: Search pattern (regex supported)
        path: Directory or file to search in
        file_pattern: Glob pattern to filter files (e.g., "*.py", "*.ts")
        context_lines: Number of context lines around each match
        max_results: Maximum number of results to return
        case_sensitive: If True, case-sensitive search

    Returns:
        Structured search results with file paths, line numbers, and context.
        Format:
        ```
        Found N matches:

        --- path/to/file.py (line 42) ---
        40| context line
        41| context line
        42> MATCH LINE
        43| context line
        ```
    """
    if _has_rg():
        cmd = ["rg", "--no-heading", "--line-number"]
        if not case_sensitive:
            cmd.append("--ignore-case")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend(["--max-count", str(max_results)])
        cmd.append(query)
        cmd.append(path)
    else:
        # Fallback to grep
        cmd = ["grep", "-rn"]
        if not case_sensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if file_pattern:
            cmd.extend(["--include", file_pattern])
        cmd.append(query)
        cmd.append(path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            return f"Found {len(lines)} matches:\n\n{result.stdout.strip()}"
        elif result.returncode == 1:
            return f"No matches found for: {query}"
        else:
            return f"Search error: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "Error: Search timed out after 30s"
    except Exception as e:
        return f"Error searching: {e}"


def find_symbol(
    symbol: str,
    path: str = ".",
    file_pattern: str | None = None,
) -> str:
    """
    Find all occurrences of a symbol (function, class, variable definition).

    Searches for common definition patterns:
    - Python: `def symbol`, `class symbol`
    - JS/TS: `function symbol`, `class symbol`, `const symbol`, `let symbol`
    - Go: `func symbol`
    - Rust: `fn symbol`, `struct symbol`, `impl symbol`

    Args:
        symbol: Symbol name to find
        path: Directory to search in
        file_pattern: Glob pattern to filter files

    Returns:
        Structured results showing where the symbol is defined and used
    """
    # Build regex for common definition patterns
    # Always escape the symbol to prevent regex injection
    safe_symbol = re.escape(symbol)
    patterns = [
        rf"def\s+{safe_symbol}\b",  # Python
        rf"class\s+{safe_symbol}\b",  # Python/JS/Java
        rf"function\s+{safe_symbol}\b",  # JS
        rf"(const|let|var)\s+{safe_symbol}\b",  # JS
        rf"func\s+{safe_symbol}\b",  # Go
        rf"fn\s+{safe_symbol}\b",  # Rust
        rf"struct\s+{safe_symbol}\b",  # Rust/Go
        rf"impl\s+{safe_symbol}\b",  # Rust
        rf"interface\s+{safe_symbol}\b",  # TS/Java
        rf"type\s+{safe_symbol}\b",  # TS
    ]

    query = "|".join(patterns)
    return search_code(query, path=path, file_pattern=file_pattern, context_lines=1)


def find_references(
    symbol: str,
    path: str = ".",
    file_pattern: str | None = None,
    max_results: int = 100,
) -> str:
    """
    Find all references to a symbol (not just definitions).

    Args:
        symbol: Symbol name to find references for
        path: Directory to search in
        file_pattern: Glob pattern to filter files
        max_results: Maximum number of results

    Returns:
        All lines containing the symbol
    """
    return search_code(
        symbol,
        path=path,
        file_pattern=file_pattern,
        max_results=max_results,
        context_lines=1,
    )
