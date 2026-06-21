# Forward Audit: Cross-Agent Memory Implementation Plan

> **Date:** 2026-06-20
> **Auditor:** OWL (Lucien)
> **Plan:** `docs/plans/2026-06-20-cross-agent-memory.md`
> **Scope:** Validate each plan step against the actual NexusAgent codebase

---

## Summary

The plan is **largely feasible** and well-aligned with the existing codebase. The core architecture (read-sharing, write-isolation, promotion) is sound and fits naturally into the existing `HybridMemoryManager` → `Session` → `SessionManager` → `WorkerPool` pipeline. However, several steps need adjustments to match actual method signatures, account for the existing cross-session memory system, and handle the worker execution path correctly.

**Overall assessment: ⚠️ NEEDS ADJUSTMENT** — implementable with the modifications detailed below.

---

## Step-by-Step Audit

### Step 1: Add `parent_memory_dir` to `HybridMemoryManager`

**File:** `src/nexusagent/memory/hybrid_memory.py` (236 lines)

| Check | Result |
|-------|--------|
| File exists | ✅ Yes |
| `__init__()` present | ✅ Line 35: `def __init__(self, workspace_dir: str \| Path)` |
| `remember()` present | ✅ Line 50: async, writes via `self.file_memory.write_entry()` |
| `recall()` present | ✅ Line 97: async, searches via `self.index.search()` |
| `get_memory_context()` present | ✅ Line 168: async, searches and formats |
| `HybridMemoryIndex` constructor | ✅ Takes `workspace_dir: str` (line 46 of index.py) |

**Verdict: ⚠️ NEEDS ADJUSTMENT**

The plan's concept is correct, but there's a critical structural issue:

1. **`HybridMemoryIndex` is tied to a single workspace directory.** Its constructor (line 46 of `index.py`) takes `workspace_dir: str` and builds the SQLite DB at `<workspace>/.memory/index.sqlite`. The plan's `_get_index()` method that returns "both own and parent indices" would require either:
   - A second `HybridMemoryIndex` instance for the parent directory, OR
   - A method that searches a second index and merges results.

2. **Recommended approach:** Add a `_parent_index: HybridMemoryIndex | None` attribute (not `_get_index()`). In `recall()` and `get_memory_context()`, search both `self.index` and `self._parent_index` (if set), then merge results. This is cleaner than a `_get_index()` method that returns a list.

3. **Duplicate method bug to note:** The current code has `_get_entry_temporal_fields` defined TWICE (lines 136 and 207 — identical signatures). This is pre-existing debt but should be cleaned up during this change.

---

### Step 2: Add `inherit_from()` method

**File:** `src/nexusagent/memory/hybrid_memory.py`

| Check | Result |
|-------|--------|
| Target class | ✅ `HybridMemoryManager` at line 28 |
| `HybridMemoryIndex` importable | ✅ `from nexusagent.memory.memory_index import HybridMemoryIndex` (line 16) |

**Verdict: ⚠️ NEEDS ADJUSTMENT**

The plan's `inherit_from()` method is well-designed but needs these adjustments:

1. **Import path:** The plan uses `HybridMemoryIndex(str(self.parent_memory_dir))` — this is correct since `HybridMemoryIndex` is already imported at line 16 via the compat shim.

2. **Attribute name mismatch:** The plan sets `self.parent_memory_dir` but Step 1 adds `parent_memory_dir` as a parameter. These are consistent — ✅.

3. **Missing: `_parent_index` initialization in `__init__`:** The plan should explicitly add `self._parent_index: HybridMemoryIndex | None = None` to `__init__()` so that `inherit_from()` can set it. The `inherit_from()` method should set `self._parent_index` (not just `self.parent_memory_dir`), and `recall()`/`get_memory_context()` should check `self._parent_index`.

4. **Type annotation:** The plan's `inherit_from(self, parent_dir: str | Path)` is correct. But it should also handle the case where the parent dir has no `.memory/index.sqlite` yet (graceful degradation).

---

### Step 3: Add `promote_to_parent()` method

**File:** `src/nexusagent/memory/hybrid_memory.py`

| Check | Result |
|-------|--------|
| `FileMemory.write_entry()` exists | ✅ In `memory_files.py` |
| Memory dict structure | ✅ Results from `recall()` have `file`, `content`, `score` keys |
| Confidence field in memories | ✅ Stored in YAML frontmatter of bank files |

**Verdict: ⚠️ NEEDS ADJUSTMENT**

1. **Accessing memories for promotion:** The plan's `filter_fn` receives a `memory_dict`, but the actual memory entries are stored as markdown files with YAML frontmatter in the `bank/` directory. The `promote_to_parent()` method needs to:
   - Read the worker's own `bank/` directory files
   - Parse YAML frontmatter to get confidence scores
   - Copy selected files to the parent's `bank/` directory
   - Re-index the parent's index for the new files

2. **Alternative approach (simpler):** Instead of parsing files, use `recall()` to get all memories, filter by confidence, then call `remember()` on the parent's `HybridMemoryManager`. But this requires a parent `HybridMemoryManager` instance, not just a directory path. The method signature should probably accept a parent `HybridMemoryManager` instance rather than just a directory.

3. **File copy vs. re-creation:** The simplest approach is to copy markdown files from `self.file_memory.bank_dir` to `parent_dir/bank/` and then call `parent_index.async_index_file()` for each copied file. The plan should specify this clearly.

---

### Step 4: Wire into `SessionManager`

**File:** `src/nexusagent/core/session/manager.py` (277 lines)

| Check | Result |
|-------|--------|
| `get_or_create()` exists | ✅ Line 138 |
| `Session` constructor | ✅ Takes `session_id`, `working_dir`, `agent`, `db_repo`, `memory_dir`, `injected_memories` |
| `memory_dir` parameter | ✅ Line 144: `memory_dir: str \| None = None` |

**Verdict: ⚠️ NEEDS ADJUSTMENT**

1. **Existing cross-session memory system:** The `SessionManager` ALREADY has a cross-session memory discovery system (lines 43-119: `_discover_cross_session_memories()`). This system searches previous sessions' memory indices and injects results as SystemMessages. The plan does NOT mention this existing system. The new `parent_memory_dir` feature should be additive, not a replacement.

2. **Parameter passing:** The plan says to add `parent_memory_dir` to `get_or_create()`. This is feasible — add it as an optional parameter and pass it to `Session()` constructor. However:
   - The `Session.__init__()` (line 41-49 of session.py) does NOT currently accept `parent_memory_dir`. Step 5 must add it first.
   - The `get_or_create()` call at line 189-196 passes `memory_dir` to `Session()`. The new `parent_memory_dir` should be passed here too.

3. **`get_parent_memory_dir(session_id)` method:** The plan mentions adding this to retrieve a session's parent memory dir. This requires storing the mapping somewhere. Options:
   - Add a `_parent_memory_dirs: dict[str, str]` dict to `SessionManager`
   - Store it in the database via `db_repo`
   - Store it on the `Session` object and access via `get().parent_memory_dir`
   
   The simplest approach is option 3 (store on Session, access via existing `get()` method). No new method needed on `SessionManager`.

4. **Missing: `get_or_create()` recursive call bug:** Line 223-228 has a recursive call that drops `memory_dir` and `injected_memories`. If `parent_memory_dir` is added, this recursive call must also pass it, or sessions created via the wait-loop path will lose the parent memory link.

---

### Step 5: Wire into `Session`

**File:** `src/nexusagent/core/session/session.py` (507 lines)

| Check | Result |
|-------|--------|
| `__init__()` exists | ✅ Line 41 |
| `HybridMemoryManager` import | ✅ Line 28: `from nexusagent.memory.memory import HybridMemoryManager` |
| `hybrid_memory` attribute | ✅ Line 73: `self.hybrid_memory = HybridMemoryManager(str(self.memory_dir))` |
| `self.memory_dir` | ✅ Line 70: `self.memory_dir = Path(memory_dir)` |

**Verdict: ✅ VERIFIED (with minor notes)**

This step is the most straightforward:

1. Add `parent_memory_dir: str | Path | None = None` to `Session.__init__()` parameters (after `injected_memories`).
2. Store as `self.parent_memory_dir`.
3. After `self.hybrid_memory.initialize()` (line 74), call `self.hybrid_memory.inherit_from(parent_memory_dir)` if provided.
4. The `Session.close()` method (line 384) already calls `self.hybrid_memory.close()` — no change needed.

**Minor note:** The `Session` import at line 28 uses `from nexusagent.memory.memory import HybridMemoryManager` (the compat shim). This is fine — `inherit_from()` will be on the `HybridMemoryManager` class regardless of import path.

---

### Step 6: Wire into Worker Pool

**File:** `src/nexusagent/core/worker/pool.py` (147 lines)

| Check | Result |
|-------|--------|
| `WorkerPool.spawn()` exists | ✅ Line 35 |
| `SubAgentHandle` | ✅ In `subagent.py`, takes `worker_id`, `contract`, `depth` |
| `TaskContract` has `parent_memory_id` | ✅ Line 64 of models.py: `parent_memory_id: str \| None = None` |
| Worker execution path | ✅ `_run_agent_task()` in `handler.py` line 34 |

**Verdict: ⚠️ NEEDS ADJUSTMENT — Significant gap**

This is the **most problematic step** in the plan. The issue is architectural:

1. **Workers don't use `Session` or `HybridMemoryManager` directly.** Looking at the execution path:
   - `WorkerPool._run_worker()` → `_run_agent_task()` (handler.py) → `run_agent_task()` (agent.py)
   - `run_agent_task()` creates an `Agent` instance directly (line 268 of agent.py) — no `Session`, no `HybridMemoryManager`
   - The worker's memory setup is in `_setup_workspace_context()` (agent.py line 308), which only sets a thread-local `_ws_memory_dir` for memory tools

2. **The plan assumes workers go through `Session`**, but they don't. Workers use `run_agent_task()` which bypasses the entire `Session` → `HybridMemoryManager` pipeline.

3. **Two implementation paths exist:**
   - **Path A (Simple):** Pass `parent_memory_dir` via `TaskContract.metadata` → `task.metadata` → `run_agent_task()` state → `_setup_workspace_context()`. The worker agent's memory tools (if any) could check for a `parent_memory_dir` in metadata.
   - **Path B (Full):** Create a `Session` for each worker (significant architectural change, out of scope).

4. **Recommended approach:** For Phase 1, use the `TaskContract.parent_memory_id` field (already exists at line 64 of models.py!) to pass the parent session ID. The `run_agent_task()` function can look up the parent session's memory directory from the DB and set it in the worker's metadata. The worker's `HybridMemoryManager` (if used) can then call `inherit_from()`.

5. **`promote_to_parent()` after completion:** The plan says to call this after sub-agent completion. In `WorkerPool._run_worker()` (line 55-82), after `_execute_bounded()` returns, there's no hook for post-processing. A callback or event system would be needed. The simplest approach: add an optional `on_complete` callback to `SubAgentHandle` or `TaskContract`.

---

### Step 7: Add tests

**File:** `tests/test_memory_cross_agent.py` (new)

| Check | Result |
|-------|--------|
| `tests/` directory exists | ✅ Confirmed |
| Existing memory tests | ✅ No `test_memory_*.py` files exist yet (good — no naming conflict) |
| Test framework | ✅ pytest (from AGENTS.md) |

**Verdict: ✅ VERIFIED**

Test file creation is straightforward. However:

1. **Multi-level inheritance test (grandparent → parent → child):** This requires creating 3 `HybridMemoryManager` instances with chained `inherit_from()` calls. Feasible but the test must create actual temp directories with memory files and indices.

2. **Write isolation test:** Must verify that `remember()` on a child manager does NOT create files in the parent's directory. This requires filesystem assertions.

3. **Missing test consideration:** The existing `_discover_cross_session_memories()` system in `SessionManager` should NOT be broken by these changes. A regression test should verify this.

---

### Step 8: Add CLI commands

**File:** `src/nexusagent/interfaces/cli.py` (574 lines)

| Check | Result |
|-------|--------|
| File exists | ✅ Yes |
| `memory` command group | ✅ Line 353: `@main.group("memory")` |
| Existing memory subcommands | ✅ `health` (line 358), `stats` (line 462) |
| Click framework | ✅ |

**Verdict: ⚠️ NEEDS ADJUSTMENT**

1. **`memory inherit <parent_session_id>`:** This command needs to look up the parent session's `memory_dir` from the database. The CLI already has access to `session_repo` (via `get_session_repo()`). Feasible.

2. **`memory promote [--min-confidence 0.7]`:** This needs to find the current session's parent and call `promote_to_parent()`. Requires:
   - A way to get the current session's `HybridMemoryManager` instance
   - The `promote_to_parent()` method to be implemented on `HybridMemoryManager`
   - The CLI would need to create a `HybridMemoryManager` for the current workspace, call `promote_to_parent()`, and clean up

3. **`memory family`:** This needs to show parent/child relationships. Currently, there's no database table or in-memory structure tracking these relationships. The plan needs to add:
   - A `parent_memory_id` field on sessions (already exists in `TaskContract` but NOT in the session DB model)
   - A way to query child sessions given a parent session ID

4. **Missing import:** The CLI would need to import `HybridMemoryManager` from `nexusagent.memory.memory` (already used indirectly via dream/health commands).

---

## 🔍 MISSING Pieces

### 1. `TaskContract.parent_memory_id` is unused for memory inheritance
The `TaskContract` model (line 64 of `models.py`) already has `parent_memory_id: str | None = None`, but it's never used by `WorkerPool`, `_run_agent_task()`, or `run_agent_task()`. The plan should explicitly wire this existing field into the worker execution path.

### 2. Worker agents don't use `HybridMemoryManager`
The biggest architectural gap. Workers go through `run_agent_task()` → `Agent` → `deepagents`, completely bypassing the `Session` → `HybridMemoryManager` pipeline. The plan must address how workers get memory inheritance. Options:
- **Option A:** Add `HybridMemoryManager` to `run_agent_task()` (create instance, call `inherit_from()`, inject context into agent state)
- **Option B:** Use the existing `_discover_cross_session_memories()` system (already in `SessionManager`) and pass results via `TaskContract.metadata`
- **Option C:** For Phase 1, only support `Session`-based sub-agents (not `WorkerPool`-based workers). This limits the feature but is much simpler.

### 3. No `parent_memory_id` in the session database model
The `parent_memory_id` field exists in `TaskContract` but there's no evidence of it in the session DB model. The `memory family` CLI command and the promotion workflow need this data persisted.

### 4. `_get_entry_temporal_fields` is duplicated
Pre-existing bug: the method is defined twice in `hybrid_memory.py` (lines 136 and 207). Should be fixed during this change.

### 5. `promote_to_parent()` needs a parent `HybridMemoryManager` instance
The method can't just receive a directory path — it needs a fully initialized `HybridMemoryManager` to write to the parent's file memory and re-index. The plan should specify how the parent manager is obtained (from `SessionManager.get()` or created on-the-fly).

### 6. No rollback/cleanup for failed inheritance
If `inherit_from()` succeeds but the worker fails, there's no mechanism to clean up. The plan should address:
- What happens if the parent memory dir is deleted between inheritance and promotion?
- What happens if two workers try to promote to the same parent simultaneously?

### 7. Thread safety of `HybridMemoryIndex` across workers
`HybridMemoryIndex` uses SQLite with a connection pool (`_DB_POOL`). Multiple workers calling `promote_to_parent()` simultaneously could cause SQLite locking issues. The plan should mention this and potentially add a file-based lock or use WAL mode.

### 8. `SessionManager.get_or_create()` recursive call drops parameters
Line 223-228 of `manager.py` has a recursive call that omits `memory_dir` and `injected_memories`. If `parent_memory_dir` is added, this recursive call must include it, or sessions created via the wait-loop path will silently lose the parent memory link.

---

## Adjusted Implementation Order

Given the findings, here's the recommended implementation order:

1. **Step 1 + Step 2 (combined):** Add `parent_memory_dir` + `_parent_index` to `HybridMemoryManager.__init__()`, add `inherit_from()`, modify `recall()` and `get_memory_context()` to search both indices.
2. **Step 3:** Add `promote_to_parent()` — implement as file copy + re-index.
3. **Step 5:** Wire into `Session` (simplest integration point).
4. **Step 4:** Wire into `SessionManager` — pass `parent_memory_dir` through `get_or_create()`.
5. **Step 7:** Write tests for the `HybridMemoryManager` changes (Steps 1-3).
6. **Step 6 (Phase 1 scope):** Wire into `WorkerPool` via `TaskContract.parent_memory_id` metadata — limited to passing the parent dir, with actual memory inheritance in `run_agent_task()`.
7. **Step 8:** Add CLI commands.

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Worker execution path bypasses `HybridMemoryManager` | 🔴 High | Use `TaskContract.parent_memory_id` + `run_agent_task()` integration |
| SQLite concurrent access during promotion | 🟡 Medium | Use WAL mode or file-based locking |
| `get_or_create()` recursive call drops params | 🟡 Medium | Explicit test for wait-loop path |
| `_get_entry_temporal_fields` duplication | 🟢 Low | Clean up during this change |
| Parent dir deleted between inheritance and promotion | 🟢 Low | Graceful degradation (log warning, skip promotion) |
