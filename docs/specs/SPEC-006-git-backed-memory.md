# SPEC-006: Git-Backed Memory

> **Status:** Draft
> **Date:** 2026-07-22
> **Author:** OWL (Lucien)
> **Depends:** ADR-006 (3-tier memory model)

---

## Goal

Initialize a git repository in each memory directory so every memory write is committed, enabling full version history, diff, and rollback.

## Problem

Memory files are the canonical source of truth for agent knowledge, but they have no version history. If a memory is incorrectly deleted or modified, there's no way to recover the previous state.

## Solution

### Git Initialization

When `FileMemory.initialize()` creates the memory directory structure, also initialize a git repo:

```python
def initialize(self):
    # Create directory structure (existing)
    self.base_path.mkdir(parents=True, exist_ok=True)
    (self.base_path / "bank").mkdir(exist_ok=True)
    (self.base_path / "entities").mkdir(exist_ok=True)
    
    # Initialize git repo (new)
    if self.git_enabled and not (self.base_path / ".git").exists():
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.base_path, check=True
        )
        # Create initial commit
        subprocess.run(
            ["git", "add", "."],
            cwd=self.base_path, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init: memory directory", "--allow-empty"],
            cwd=self.base_path, check=True
        )
```

### Auto-Commit After Every Write

```python
def write_entry(self, ..., content: str, ...) -> str:
    # Write file (existing)
    path = self._write_to_bank(...)
    
    # Git commit (new)
    if self.git_enabled:
        self._git_commit(f"memory: add {description}", [path])
    
    return path
```

### Auto-Commit After Deletion

```python
def _git_delete(self, path: str, description: str):
    subprocess.run(["git", "rm", path], cwd=self.base_path, check=True)
    self._git_commit(f"memory: delete {description}", [path])
```

### Git Operations Module

**File:** `src/nexusagent/memory/git_ops.py` (new)

```python
class MemoryGitOps:
    """Git operations for memory directories."""
    
    def __init__(self, memory_dir: str, enabled: bool = True):
        self.memory_dir = Path(memory_dir)
        self.enabled = enabled
    
    def init_repo(self):
        """Initialize git repo if not exists."""
        if not (self.memory_dir / ".git").exists():
            subprocess.run(["git", "init", "--quiet"], cwd=self.memory_dir, check=True)
    
    def commit(self, message: str, files: list[str] | None = None):
        """Commit changes."""
        if not self.enabled:
            return
        if files:
            subprocess.run(["git", "add", *files], cwd=self.memory_dir, check=False)
        else:
            subprocess.run(["git", "add", "."], cwd=self.memory_dir, check=False)
        subprocess.run(
            ["git", "commit", "-m", message, "--allow-empty"],
            cwd=self.memory_dir, check=False  # Don't fail on empty commits
        )
    
    def log(self, limit: int = 10) -> list[dict]:
        """Get recent commits."""
        result = subprocess.run(
            ["git", "log", f"--max-count={limit}", "--pretty=format:%H|%ai|%s"],
            cwd=self.memory_dir, capture_output=True, text=True
        )
        # Parse output into list of dicts
        ...
    
    def diff(self, ref1: str, ref2: str) -> str:
        """Get diff between two refs."""
        ...
    
    def rollback(self, ref: str) -> bool:
        """Rollback to a specific commit."""
        ...
```

### Configuration

```python
# config.py additions
memory_git_enabled: bool = True
memory_git_auto_commit: bool = True
```

### Safety Guards

1. **Git failures are non-fatal** — memory operations succeed even if git fails
2. **`.gitignore`** excludes `*.sqlite`, `*.db`, binary files
3. **Auto-commit only tracks markdown files** in `bank/` and `entities/`
4. **Rate limiting** — max 1 git commit per second (batch rapid writes)

## Files to Create/Modify

| File | Change |
|------|--------|
| `src/nexusagent/memory/git_ops.py` | New — `MemoryGitOps` class |
| `src/nexusagent/memory/memory_files.py` | Add git init in `initialize()`, git commit in `write_entry()` |
| `src/nexusagent/infrastructure/config.py` | Add `memory_git_enabled`, `memory_git_auto_commit` |
| `src/nexusagent/tools/register_all.py` | Add `memory_git_log`, `memory_git_rollback` tools |

## Tests

1. `test_git_init_on_first_use` — Git repo created when FileMemory initializes
2. `test_git_commit_after_write` — Memory write triggers git commit
3. `test_git_commit_after_delete` — Memory deletion triggers git commit
4. `test_git_non_fatal` — Git failure doesn't break memory operations
5. `test_git_disabled` — When disabled, no git operations occur
6. `test_git_log` — Can retrieve commit history
7. `test_gitignore_excludes_binaries` — SQLite files not tracked

## Acceptance Criteria

- [ ] Git repo initialized on first use
- [ ] Every memory write committed automatically
- [ ] Git failures are non-fatal (memory ops succeed)
- [ ] Config option to disable git tracking
- [ ] `.gitignore` excludes binary files
- [ ] All tests pass with zero regressions
