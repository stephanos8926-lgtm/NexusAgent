# Coding Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement essential coding tools (File System Access, Shell Command Execution) for the NexusAgent.

**Architecture:** Define Python functions as tools, wrap them in a registry, and expose them to the DeepAgents SDK.

**Tech Stack:** Python 3.12+, `deepagents`, `pathlib`, `subprocess`.

---

### Task 1: Define File System Tools

**Files:**
- Create: `src/nexusagent/tools/fs.py`
- Test: `tests/tools/test_fs.py`

- [ ] **Step 1: Implement `read_file` tool**

```python
# src/nexusagent/tools/fs.py
import os
from pathlib import Path

def read_file(path: str) -> str:
    """Reads the content of a file."""
    p = Path(path).resolve()
    # Basic security check
    if not p.exists():
        return f"Error: File {path} does not exist"
    return p.read_text()
```

- [ ] **Step 2: Implement `write_file` tool**

```python
# src/nexusagent/tools/fs.py
def write_file(path: str, content: str) -> str:
    """Writes content to a file."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Successfully wrote to {path}"
```

- [ ] **Step 3: Write tests**

```python
# tests/tools/test_fs.py
from nexusagent.tools.fs import read_file, write_file
import tempfile

def test_fs_tools():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
        tmp.write("hello")
        tmp_path = tmp.name
    
    assert read_file(tmp_path) == "hello"
    
    write_file(tmp_path, "world")
    assert read_file(tmp_path) == "world"
```

- [ ] **Step 4: Commit**
`git add src/nexusagent/tools/fs.py tests/tools/test_fs.py`
`git commit -m "feat: implement file system tools"`

### Task 2: Define Shell Command Tool

**Files:**
- Create: `src/nexusagent/tools/shell.py`
- Test: `tests/tools/test_shell.py`

- [ ] **Step 1: Implement `run_shell` tool**

```python
# src/nexusagent/tools/shell.py
import subprocess

def run_shell(command: str) -> str:
    """Executes a shell command."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.stderr}"
```

- [ ] **Step 2: Write tests**

```python
# tests/tools/test_shell.py
from nexusagent.tools.shell import run_shell

def test_shell_tool():
    result = run_shell("echo hello")
    assert result.strip() == "hello"
```

- [ ] **Step 3: Commit**
`git add src/nexusagent/tools/shell.py tests/tools/test_shell.py`
`git commit -m "feat: implement shell command tool"`

### Task 3: Integrate Tools into DeepAgents

**Files:**
- Modify: `src/nexusagent/agent.py`

- [ ] **Step 1: Update Agent to register tools**

```python
# src/nexusagent/agent.py
from nexusagent.tools.fs import read_file, write_file
from nexusagent.tools.shell import run_shell
# ... inside Agent class ...
def __init__(self, *args: Any, **kwargs: Any) -> None:
    model_name = os.getenv("AGENT_MODEL", "gemini-3.1-flash-lite")
    self._inner = create_deep_agent(
        model=model_name,
        tools=[read_file, write_file, run_shell]
    )
```

- [ ] **Step 2: Commit**
`git add src/nexusagent/agent.py`
`git commit -m "feat: register coding tools with agent"`
