"""
Shell execution tools for NexusAgent.

Provides run_shell with timeout, working directory, environment control,
and streaming support for long-running commands.
"""

import os
import shlex
import subprocess


def run_shell(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    capture: bool = True,
) -> str:
    """Execute a shell command with safety controls.

    Returns structured output with stdout, stderr, and exit code so the
    agent can debug failures and course-correct.
    """
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    cwd = workdir if workdir else None

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

        parts = []
        if result.stdout:
            parts.append(result.stdout.rstrip())
        if result.stderr:
            parts.append(f"[stderr] {result.stderr.rstrip()}")
        if result.returncode != 0 and not result.stderr:
            parts.append(f"[exit code {result.returncode}]")

        return "\n".join(parts) if parts else f"[exit code {result.returncode}]"

    except subprocess.TimeoutExpired as e:
        partial = e.stdout if e.stdout else ""
        return f"[TIMEOUT after {timeout}s]\n{partial}"
    except FileNotFoundError as e:
        return f"[ERROR] Command not found: {e}"
    except Exception as e:
        return f"[ERROR] {e}"


def run_shell_streaming(
    command: str,
    workdir: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> str:
    """Execute a shell command with line-by-line streaming output."""
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    cwd = workdir if workdir else None

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
            output_lines.append(f"\n[TIMEOUT: killed after {timeout}s]")

        output = "\n".join(output_lines)
        return f"[exit code {process.returncode}]\n{output}"

    except Exception as e:
        return f"[ERROR] {e}"
