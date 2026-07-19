# M2 — Workspace Facts vs User Facts

**Goal:** Never mix README.md codebase claims with user instructions. Separate memory into two compartments: workspace-scoped facts and user-scoped facts.
**Current state:** Single `workspace_dir` with one `bank/` directory. All memories (codebase facts, user preferences, session observations) mixed together.

---

## Two compartments

```
workspace/
  .nexusagent/memory/
    bank/                ← Workspace facts (codebase, project config)
    users/               ← User facts (per-user, persisted across projects)
      sysop/
        bank/
          preferences/
          workflow-patterns/
          corrections/
      default/
        bank/
```

### Compartment comparison

| Property | Workspace Facts | User Facts |
|----------|----------------|------------|
| Scope | Per-project | Cross-project (shared across all projects) |
| Source | `WORKSPACE_FILE`, `TOOL_OUTPUT` | `USER_DIRECT`, `USER_INFERRED`, `MEMORY_INFERENCE` |
| Retention | Project lifetime | Permanent until explicitly removed |
| Recall priority | Before agent execution | Before every session |
| Index | Project-scoped HybridMemoryIndex | Global HybridMemoryIndex |
| Git-backed | Yes (project repo) | Yes (dedicated `~/.nexusagent/memory/users/` git repo) |

### User fact scope

User facts are stored in `~/.nexusagent/memory/users/<username>/`:
- Survive project deletion
- Persist across workspace switches
- Shared by all agents running as the same user
- Git-backed (separate repo from project)

### Workspace fact scope

Workspace facts are stored in `<workspace>/.nexusagent/memory/bank/`:
- Git-committed alongside project code
- Describe codebase structure, README claims, config values
- Validated during workspace setup

---

## How facts are tagged

Both compartments use the same `MemorySource` enum from M1, but they're stored in different directories and indexed separately.

| Fact type | Compartment | Source | Example |
|-----------|------------|--------|---------|
| "User prefers concise responses" | User | `USER_DIRECT` | `~/.nexusagent/memory/users/sysop/preferences/` |
| "NexusAgent uses FastAPI on port 8000" | Workspace | `WORKSPACE_FILE` | `<ws>/.nexusagent/memory/bank/` |
| "read_file returns file content as string" | Workspace | `TOOL_OUTPUT` | `<ws>/.nexusagent/memory/bank/` |
| "The system prompt has a trust section" | Workspace | `WORKSPACE_FILE` | `<ws>/.nexusagent/memory/bank/` |
| "User always uses Nushell on server" | User | `USER_INFERRED` | `~/.nexusagent/memory/users/sysop/` |
| "Steven corrected me about function signature" | User | `USER_DIRECT` | `~/.nexusagent/memory/users/sysop/corrections/` |

---

## API changes

### HybridMemoryManager

```python
class HybridMemoryManager:
    def __init__(self, workspace_dir, username="default", ...):
        self.workspace_dir = Path(workspace_dir)
        self.file_memory = FileMemory(str(self.workspace_dir))

        # User fact storage (cross-project)
        self.user_dir = Path.home() / ".nexusagent" / "memory" / "users" / username
        self.user_memory = FileMemory(str(self.user_dir))

        # Separate indices
        self.index = HybridMemoryIndex(str(self.workspace_dir))      # Workspace facts
        self.user_index = HybridMemoryIndex(str(self.user_dir))      # User facts

    async def remember(self, content, source=MemorySource.SYSTEM, ...):
        # Route to correct compartment based on source
        if source in (MemorySource.USER_DIRECT, MemorySource.USER_INFERRED):
            filepath = self.user_memory.write_entry(...)
            await self.user_index.async_index_file(rel_path)
        else:
            filepath = self.file_memory.write_entry(...)
            await self.index.async_index_file(rel_path)

    async def recall(
        self,
        query,
        scope="both",                    # "workspace" | "user" | "both"
        min_authority=0.0,
        ...
    ):
        results = []
        if scope in ("workspace", "both"):
            ws = await self.index.search(query, ...)
            results.extend(ws)
        if scope in ("user", "both"):
            us = await self.user_index.search(query, ...)
            results.extend(us)
        # Dedup by content hash, then trust-rank
        ...
```

### Session integration

```python
# In session.py:
# On session start, inject USER facts first (preferences, corrections)
user_memories = await memory.recall("user preferences", scope="user")
system_prompt = _inject_user_context(system_prompt, user_memories)

# On workspace command, inject WORKSPACE facts
workspace_memories = await memory.recall("codebase structure", scope="workspace")
system_prompt = _inject_workspace_context(system_prompt, workspace_memories)
```

---

## Migration

Existing workspace memories in `bank/` remain as workspace facts. No data loss.

For users with existing `~/.nexusagent/memory/` from cross-project memory, those become the initial user fact directory:

```python
if not self.user_dir.exists():
    # Check if old shared memory exists
    old_shared = Path.home() / ".nexusagent" / "memory"
    if old_shared.exists() and old_shared != self.workspace_dir:
        shutil.copytree(old_shared, self.user_dir)
        logger.info("Migrated shared memory to user fact directory: %s", self.user_dir)
```

---

## Files to modify

| File | Change | ± Lines |
|------|--------|---------|
| `memory/hybrid_memory.py` | Add `user_memory`, `user_index`, compartment-aware `remember()` routing, `scope` parameter on `recall()` | +40 |
| `memory/memory_files.py` | No changes (same API, different directory) | +0 |
| `core/session/session.py` | Inject user facts at session start, workspace facts on workspace commands | +15 |
| `infrastructure/config.py` | Add `memory.username: str = "default"`, `memory.user_facts_enabled: bool = True` | +6 |

## Config

```yaml
memory:
  username: sysop          # Per-user fact compartment
  user_facts_enabled: true
  user_facts_dir: ~/.nexusagent/memory/users/
```

## Effort

- Implementation: ~0.5 day
- Tests: ~0.5 day (compartment isolation, recall scope filtering, migration)
- Risk: Low (additive — existing workspace memory path unchanged)
