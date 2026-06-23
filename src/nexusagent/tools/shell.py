"""Shell execution tools for NexusAgent.

Provides run_shell with timeout, working directory, environment control,
and streaming support for long-running commands.

SECURITY: Uses shell=False with shlex.split() to prevent shell injection.
Commands are split into argument arrays, not passed to a shell interpreter.
"""

import os
import shlex
import subprocess
from pathlib import Path

# Workspace root for path jail — all shell commands must run within this directory
_SHELL_WORKSPACE_ROOT: Path | None = None

MAX_OUTPUT_BYTES = 1024 * 1024  # 1MB output cap to prevent memory exhaustion

def set_shell_workspace_root(path: str) -> None:
    """Set the workspace root directory for shell command path jail."""
    global _SHELL_WORKSPACE_ROOT
    import pathlib
    _SHELL_WORKSPACE_ROOT = pathlib.Path(path).resolve()

def _validate_workdir(workdir: str | None) -> str | None:
    """Validate workdir is within workspace root if set."""
    if workdir is None:
        return None
    if _SHELL_WORKSPACE_ROOT is None:
        return workdir
    import pathlib
    resolved = pathlib.Path(workdir).resolve()
    try:
        resolved.relative_to(_SHELL_WORKSPACE_ROOT)
    except ValueError:
        raise PermissionError(
            f"SAFETY: workdir '{workdir}' resolves to '{resolved}' which is outside "
            f"the workspace root '{_SHELL_WORKSPACE_ROOT}'"
        ) from None
    return str(resolved)


def _split_command(command: str) -> list[str]:
    """Split a command string into an argument list safely.

    Uses shlex.split() which handles quoting correctly and does NOT
    invoke a shell. This prevents shell injection attacks.
    """
    try:
        return shlex.split(command)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {e}") from e


def _truncate_output(output: str) -> str:
    """Truncate output to MAX_OUTPUT_BYTES to prevent memory exhaustion."""
    encoded = output.encode("utf-8")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return output
    # Truncate at a character boundary
    truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    truncated += f"\n[OUTPUT TRUNCATED: exceeded {MAX_OUTPUT_BYTES:,} bytes]"
    return truncated


def run_shell(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    capture: bool = True,
) -> str:
    """Execute a shell command with safety controls.

    Uses shell=False with shlex.split() to prevent shell injection.
    Output is truncated to 1MB to prevent memory exhaustion.

    Returns structured output with stdout, stderr, and exit code.
    """
    try:
        cmd_args = _split_command(command)
    except ValueError as e:
        return f"[ERROR] {e}"

    if not cmd_args:
        return "[ERROR] Empty command"

    cmd_env = os.environ.copy()
    if env:
        # Sanitize env vars — only allow alphanumeric + underscore keys
        for k, v in env.items():
            if k.replace("_", "").replace("-", "").isalnum():
                cmd_env[k] = str(v)

    cwd = _validate_workdir(workdir)

    try:
        result = subprocess.run(
            cmd_args,
            shell=False,  # SECURITY: never use shell=True
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=cmd_env,
        )

        parts = []
        if result.stdout:
            parts.append(_truncate_output(result.stdout.rstrip()))
        if result.stderr:
            parts.append(f"[stderr] {_truncate_output(result.stderr.rstrip())}")
        if result.returncode != 0 and not result.stderr:
            parts.append(f"[exit code {result.returncode}]")

        return "\n".join(parts) if parts else f"[exit code {result.returncode}]"

    except subprocess.TimeoutExpired as e:
        partial = _truncate_output(e.stdout) if e.stdout else ""
        return f"[TIMEOUT after {timeout}s]\n{partial}"
    except FileNotFoundError as e:
        return f"[ERROR] Command not found: {e.filename}"
    except PermissionError:
        return f"[ERROR] Permission denied: {cmd_args[0]}"
    except OSError as e:
        return f"[ERROR] {e}"


def run_shell_streaming(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> str:
    """Execute a shell command with line-by-line streaming output.

    Uses shell=False with shlex.split() to prevent shell injection.
    Output is truncated to 1MB to prevent memory exhaustion.
    """
    try:
        cmd_args = _split_command(command)
    except ValueError as e:
        return f"[ERROR] {e}"

    if not cmd_args:
        return "[ERROR] Empty command"

    cmd_env = os.environ.copy()
    if env:
        for k, v in env.items():
            if k.replace("_", "").replace("-", "").isalnum():
                cmd_env[k] = str(v)

    cwd = _validate_workdir(workdir)

    try:
        process = subprocess.Popen(
            cmd_args,
            shell=False,  # SECURITY: never use shell=True
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=cmd_env,
        )

        output_lines = []
        total_bytes = 0
        try:
            for line in process.stdout:
                total_bytes += len(line.encode("utf-8"))
                if total_bytes > MAX_OUTPUT_BYTES:
                    output_lines.append(
                        f"\n[OUTPUT TRUNCATED: exceeded {MAX_OUTPUT_BYTES:,} bytes]"
                    )
                    break
                output_lines.append(line.rstrip())
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            output_lines.append(f"\n[TIMEOUT: killed after {timeout}s]")

        output = "\n".join(output_lines)
        return f"[exit code {process.returncode}]\n{output}"

    except FileNotFoundError as e:
        return f"[ERROR] Command not found: {e.filename}"
    except PermissionError:
        return f"[ERROR] Permission denied: {cmd_args[0]}"
    except OSError as e:
        return f"[ERROR] {e}"
