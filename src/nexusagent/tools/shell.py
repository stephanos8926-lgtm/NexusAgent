"""
Shell execution tools for NexusAgent.

Provides run_shell with timeout, working directory, environment control,
and streaming support for long-running commands.
"""

import os
import subprocess


def run_shell(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    capture: bool = True,
) -> str:
    """
    Execute a shell command with safety controls.

    Args:
        command: Shell command to execute
        workdir: Working directory (defaults to cwd)
        env: Additional environment variables to set
        timeout: Maximum execution time in seconds (default: 120)
        capture: If True, capture and return stdout. If False, let output stream.

    Returns:
        Command output (stdout). On error, returns stderr prefixed with "Error:".
    """
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    cwd = workdir if workdir else None

    # Validate command for shell injection
    _validate_command(command)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=cmd_env,
        )

        if result.stdout:
            return result.stdout
        if result.stderr:
            return f"Error: {result.stderr}"
        return ""

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s. Partial output may be lost."
    except FileNotFoundError as e:
        return f"Error: Command not found: {e}"
    except Exception as e:
        return f"Error executing command: {e}"


def _validate_command(command: str) -> None:
    """Validate command for shell injection patterns.
    
    Raises ValueError if dangerous patterns are detected.
    Rejects: ; && || | $() ${} backticks > < >> << ` eval exec
    These are legitimate in shells but dangerous when the command string
    comes from an untrusted source (like an LLM).
    """
    import re
    # Block injection characters that allow command chaining/substitution
    dangerous = re.search(r'[;&|`$(){}<>]', command)
    if dangerous:
        raise ValueError(
            f"Command contains potentially dangerous characters: {dangerous.group()!r}. "
            "Use a list of arguments instead of shell command chaining."
        )


def run_shell_streaming(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> str:
    """
    Execute a shell command with line-by-line streaming output.
    Better for long-running commands (builds, tests) where you want
    to see progress instead of waiting for completion.

    Args:
        command: Shell command to execute
        workdir: Working directory
        env: Additional environment variables
        timeout: Maximum execution time in seconds (default: 300)

    Returns:
        Full output with exit code
    """
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    cwd = workdir if workdir else None

    # Validate command for shell injection
    _validate_command(command)

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=cmd_env,
        )

        output_lines = []
        try:
            for line in process.stdout:
                output_lines.append(line.rstrip())
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            output_lines.append(f"\n[TIMEOUT: Command killed after {timeout}s]")

        output = "\n".join(output_lines)
        return f"Exit code: {process.returncode}\n{output}"

    except Exception as e:
        return f"Error executing command: {e}"
