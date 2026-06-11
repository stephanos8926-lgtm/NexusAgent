# Environment & Execution Guide

This document provides critical information for all agents working in this repository to avoid common environment pitfalls.

## Python Import & Path Issues

### The Problem: `ModuleNotFoundError` in `src` Layout
The project uses a `src` layout (all source code is in the `src/` directory). By default, the Python interpreter does not look inside the `src` folder for packages.

If you encounter a `ModuleNotFoundError: No module named 'nexusagent'`, it is NOT a bug in the code, but a pathing issue in the environment.

### The Cause: Shell Persistence
Agent tool calls are executed in non-interactive `bash` shells. These shells do **not** inherit environment variables (like `PYTHONPATH`) set in your user's `.zshrc` or `.bashrc` profiles.

### The Required Fix: Explicit Pathing
To ensure imports work correctly, **every** Python execution command must explicitly include the `src` directory in the `PYTHONPATH`.

**Correct Command Pattern:**
`PYTHONPATH=src python3 <command>`
or
`export PYTHONPATH=src && python3 <command>`

**Avoid:**
- Relying on `pip install -e .` (as it may not persist across different agent sessions or subagents).
- Assuming the current working directory is sufficient.

---

## Tool Failure Behaviors

### The `pytest` Crash (Exit Code 4)
In certain restricted environments, running `pytest` can cause a hard crash (Exit Code 4) due to how the tool attempts to resolve paths in sub-processes.

**The Workaround:**
If `pytest` fails with a non-standard exit code (like 4), pivot to using the standard `unittest` module or a custom Python script with `python3 -m unittest`. This is more stable in isolated shells.

---

## Summary for Agents
- **Symptom:** `ModuleNotFoundError` $\rightarrow$ **Fix:** Add `PYTHONPATH=src` to the command.
- **Symptom:** `pytest` crashes with Exit Code 4 $\rightarrow$ **Fix:** Use `python3 -m unittest`.
