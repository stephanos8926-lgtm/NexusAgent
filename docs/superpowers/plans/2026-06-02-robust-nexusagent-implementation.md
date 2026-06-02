# NexusAgent Robust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust coding tools, self-healing research loops, configuration management, and the Textual TUI client for NexusAgent.

**Architecture:** Event-driven architecture with enhanced tools (tree-based directory listing, batch operations, safety read-before-write, and unified-diff patch application). Configuration via YAML/text files.

**Tech Stack:** Python 3.12+, `uv`, `langgraph`, `deepagents`, `nats-py`, `textual`, `patch-ng` (or `diff-patch` equivalent).

---

### Task 1: Configuration Management

**Files:**
- Create: `config/system_prompt.txt`
- Create: `config/nexusagent.yaml`
- Modify: `src/nexusagent/server.py`
- Modify: `src/nexusagent/cli.py`

- [ ] **Step 1: Create system prompt template**

```text
# config/system_prompt.txt
You are an expert software engineer assistant.
... (detailed system prompt) ...
```

- [ ] **Step 2: Create runtime configuration**

```yaml
# config/nexusagent.yaml
server:
  nats_url: "nats://localhost:4222"
  db_path: "nexus.db"
client:
  tui_colors: "monokai"
loop_threshold: 4
post_research_retries: 4
```

- [ ] **Step 3: Update entry points to load config**

(Modify `server.py` and `cli.py` to load from these files)

- [ ] **Step 4: Commit**
`git add config/ src/nexusagent/server.py src/nexusagent/cli.py`
`git commit -m "feat: setup configuration management"`

### Task 2: Enhanced Coding Tools (FS + Safety)

**Files:**
- Modify: `src/nexusagent/tools/fs.py`
- Test: `tests/tools/test_fs_enhanced.py`

- [ ] **Step 1: Implement `list_directory` (tree structure)**

```python
# src/nexusagent/tools/fs.py
def list_directory(path: str, recursive: bool = False, max_depth: int = 2) -> dict:
    # ... logic to build nested dict structure ...
```

- [ ] **Step 2: Implement Read-Before-Write safety layer**

(Add session-based read tracking in `fs.py` tools)

- [ ] **Step 3: Implement batch operations**

```python
# src/nexusagent/tools/fs.py
def read_multiple_files(paths: list[str]) -> dict: ...
def write_multiple_files(files: dict[str, str]) -> str: ...
```

- [ ] **Step 4: Commit**
`git add src/nexusagent/tools/fs.py tests/tools/test_fs_enhanced.py`
`git commit -m "feat: implement enhanced file system tools with safety layer"`

### Task 3: Surgical Edit Tool (Patching)

**Files:**
- Create: `src/nexusagent/tools/patch.py`
- Test: `tests/tools/test_patch.py`

- [ ] **Step 1: Implement `apply_patch`**

```python
# src/nexusagent/tools/patch.py
import patch_ng # or similar
def apply_patch(path: str, diff: str) -> str: ...
```

- [ ] **Step 2: Commit**
`git add src/nexusagent/tools/patch.py tests/tools/test_patch.py`
`git commit -m "feat: implement surgical patch tool"`

### Task 4: Autonomous Research & Error Handling

**Files:**
- Create: `src/nexusagent/tools/research.py`
- Modify: `src/nexusagent/graph.py`

- [ ] **Step 1: Implement Research Tools (Exa/Context7)**

- [ ] **Step 2: Update Orchestrator with Loop Logic (Retries + Research)**

Modify LangGraph definition to detect loop counts, trigger research branches, and handle notifications (Telegram/Webhook).

- [ ] **Step 3: Commit**
`git add src/nexusagent/tools/research.py src/nexusagent/graph.py`
`git commit -m "feat: implement autonomous research and error handling"`

### Task 5: Textual TUI Client

**Files:**
- Create: `src/nexusagent/tui.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Implement TUI using Textual**

(Build terminal layout: Logs, Task input, Interactive error correction modal)

- [ ] **Step 2: Update `pyproject.toml` entry points**

`nexus = "nexusagent.tui:main"`

- [ ] **Step 3: Commit**
`git add src/nexusagent/tui.py pyproject.toml`
`git commit -m "feat: implement TUI interface"`
