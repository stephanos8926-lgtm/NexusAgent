# Reverse Audit: Cross-Agent Memory Implementation Plan

> **Date:** 2026-06-20
> **Auditor:** OWL (Lucien)
> **Plan:** `docs/plans/2026-06-20-cross-agent-memory.md`
> **Forward Audit:** `docs/specs/audits/forward-audit-cross-agent-memory.md`
> **Scope:** Find what the plan MISSES or gets wrong — security, race conditions, leaks, error handling, test gaps, integration gaps, performance, data model

---

## Summary

The forward audit validated that the plan is *feasible* but needs adjustments. This reverse audit goes further: it identifies **gaps the plan entirely omits** — issues that neither the plan nor the forward audit adequately address. The plan is a good structural blueprint but is **silent on several critical engineering concerns** that will cause bugs, security vulnerabilities, or operational failures if not addressed before or during implementation.

**Overall assessment: ⚠️ INCOMPLETE** — the plan covers the happy path well but misses edge cases, failure modes, security boundaries, and operational concerns.

---

## 🔴 CRITICAL — Will Cause Bugs or Security Issues

### 1. Path Traversal via `parent_memory_dir`

**Gap:** The plan's `inherit_from()` method accepts `parent_dir: str | Path` and directly calls `Path(parent_dir)` with **zero validation**. An attacker or buggy caller could pass `../../etc` or `/etc/passwd` as `parent_memory_dir`, causing the `_parent_index` to open an arbitrary SQLite database.

**Code location:** Step 2 of the plan:
```python
def inherit_from(self, parent_dir: str | Path) -> None:
    self.parent_memory_dir = Path(parent_dir)
    if self.parent_memory_dir.exists():
        self._parent_index = HybridMemoryIndex(str(self.parent_memory_dir))
```

**What's missing:**
- No check that `parent_dir` is within the expected workspace/session directory tree
- No check that `parent_dir` actually contains a valid memory directory structure (could point to any directory)
- No normalization via `.resolve()` to prevent symlink-based traversal
- No validation that the path doesn't escape a safe root (e.g., `~/.nexusagent/`)

**Impact:** A malicious sub-agent or crafted `TaskContract.parent_memory_id` could cause the system to read from or index arbitrary directories on the filesystem.

**Fix needed:** Add path validation — resolve the path, verify it's under the expected root, and verify it contains a `.memory/index.sqlite` before opening.

---

### 2. `_parent_index` Never Closed — Resource Leak

**Gap:** The plan adds `_parent_index: HybridMemoryIndex` via `inherit_from()` but **never closes it**. The `HybridMemoryManager.close()` method only closes `self.index` (the own index):

```python
def close(self):
    self.index.close()  # Only closes own index!
```

**What's missing:**
- `close()` must also close `self._parent_index` if it exists
- No `__del__` or context manager support for the parent index
- If `inherit_from()` is called multiple times (e.g., CLI `memory inherit` used repeatedly), the previous `_parent_index` is silently replaced — leaking the old SQLite connection/embedder

**Impact:** Each `inherit_from()` call that replaces a previous parent leaks an `HybridMemoryIndex` (including its `EmbeddingProvider` and any cached resources). In long-running sessions with multiple sub-agent spawns, this accumulates.

**Fix needed:** In `close()`, add `if self._parent_index: self._parent_index.close()`. In `inherit_from()`, close the previous `_parent_index` before replacing it.

---

### 3. `_discover_cross_session_memories` Leaks `HybridMemoryIndex` Instances

**Gap:** This is a **pre-existing bug** that the plan doesn't address but will interact with. In `manager.py` lines 67-86:

```python
async def _search_session(sess_info: dict) -> list[dict]:
    mem_dir = sess_info.get("memory_dir")
    if not mem_dir:
        return []
    index = HybridMemoryIndex(mem_dir)  # Created but NEVER CLOSED
    results = await asyncio.to_thread(index.search_sync, ...)
    return results  # index goes out of scope but close() never called
```

Each call creates a new `HybridMemoryIndex` (which opens an SQLite connection in `__init__` via `_init_db()`) but **never calls `close()`**. The `HybridMemoryIndex.close()` method only clears the embedder reference, but the `_init_db()` connection is opened-and-closed per method call, so the immediate leak is minor. However, the `EmbeddingProvider` created in `__init__` (line 56) may hold HTTP sessions or thread pools.

**Impact:** Under heavy cross-session memory discovery, this leaks `EmbeddingProvider` instances and their internal resources. The plan's new `_parent_index` makes this worse by adding another index that can be leaked.

**Fix needed:** The plan should include fixing this pre-existing leak as part of the cross-agent memory work, since it's in the same code path.

---

### 4. `get_or_create()` Recursive Call Drops `parent_memory_dir`

**Gap:** The plan says to add `parent_memory_dir` to `get_or_create()` but doesn't address the recursive call at lines 223-228 of `manager.py`:

```python
return await self.get_or_create(
    session_id=session_id,
    working_dir=working_dir,
    agent=agent,
    db_repo=db_repo,
    # memory_dir and injected_memories are ALREADY dropped here
    # parent_memory_dir would also be dropped!
)
```

This is the wait-loop fallback path — when one coroutine is already creating a session and another waits. The recursive call already drops `memory_dir` and `injected_memories` (a pre-existing bug). Adding `parent_memory_dir` without fixing this means sessions created via this path will **silently lose all memory configuration**.

**Impact:** Under concurrent session creation (which is the whole point of the `_creating` set + wait loop), the second coroutine gets a session with no memory dir and no parent memory link. This is a **silent data loss** bug.

**Fix needed:** The recursive call must pass through all memory-related parameters. This should be fixed as part of Step 4.

---

### 5. No Handling of Parent Directory Deletion Mid-Session

**Gap:** The plan's `inherit_from()` checks `if self.parent_memory_dir.exists()` at setup time, but there's **no handling for the parent directory being deleted while the sub-agent is running**. The `_parent_index` holds a reference to `parent_memory_dir/.memory/index.sqlite` — if that directory is deleted (e.g., parent session cleanup, manual deletion, disk pressure), subsequent `recall()` or `get_memory_context()` calls will:

1. Try to query a non-existent SQLite file
2. Get SQLite errors (file not found or corrupted database)
3. Have no fallback — the plan doesn't specify error handling for this case

**Impact:** Sub-agent crashes with unhandled SQLite exceptions if parent memory is cleaned up before the sub-agent finishes. In production, this is common — parent sessions may close and clean up memory while sub-agents are still running.

**Fix needed:** `recall()` and `get_memory_context()` should wrap parent index searches in try/except, log a warning, and gracefully degrade to own-index-only results.

---

## 🟠 HIGH — Important Gaps to Fix Before Implementation

### 6. Concurrent `promote_to_parent()` — SQLite Write Conflicts

**Gap:** The plan says "After sub-agent completes, call `promote_to_parent()`" but doesn't address what happens when **multiple sub-agents promote to the same parent simultaneously**. The `HybridMemoryIndex` uses SQLite with per-method connections — multiple writers promoting files to the same parent directory will cause:

1. `SQLITE_BUSY` errors when two workers try to write to the parent's `index.sqlite` simultaneously
2. File-level conflicts when two workers try to copy markdown files to the parent's `bank/` directory with the same slug-based filename
3. Index corruption if two `async_index_file()` calls interleave on the same SQLite database

**Impact:** With `max_workers=4` in `WorkerPool`, up to 4 sub-agents could try to promote to the same parent simultaneously. This will cause intermittent SQLite errors and potentially corrupted indices.

**Fix needed:** Add a file-based lock (e.g., `filelock` or `fcntl.flock`) on the parent's `.memory/promote.lock` during promotion. Or use SQLite WAL mode + busy timeout. The plan should specify this.

---

### 7. `promote_to_parent()` File Naming Collisions

**Gap:** The plan's `promote_to_parent()` copies markdown files from child's `bank/` to parent's `bank/`. But `FileMemory.write_entry()` generates filenames as:

```python
slug = re.sub(r"[^a-z0-9]+", "-", description.lower())[:40].strip("-")
timestamp = datetime.now(UTC).strftime("%Y%m%d")
filename = f"{slug}-{timestamp}.timestamp}.md"
```

If two sub-agents write memories with the same description (e.g., "User prefers dark mode"), they'll generate **identical filenames**. When both promote to the parent, the second copy will silently overwrite the first.

**Impact:** Memory loss during promotion — the second sub-agent's memory overwrites the first's.

**Fix needed:** Promotion should either use unique filenames (append worker_id or UUID) or use `remember()` on the parent's `HybridMemoryManager` instead of raw file copy (which re-indexes properly and handles dedup).

---

### 8. Worker Execution Path Completely Bypasses `HybridMemoryManager`

**Gap:** The plan's Step 6 says "Wire into WorkerPool" but the forward audit already flagged this as the "most problematic step." The actual execution path is:

```
WorkerPool._run_worker() → _execute_bounded() → _run_agent_task() → run_agent_task()
```

`run_agent_task()` creates an `Agent` directly — **no Session, no HybridMemoryManager**. The worker's memory setup is just `_setup_workspace_context()` which sets a thread-local `_ws_memory_dir` for filesystem tools. There is **no mechanism** for the worker to inherit parent memories.

The plan's architecture diagram shows:
```
Sub-Agent Session (Worker)
    ├── hybrid_memory/          ← Worker's own memory directory
    └── parent_memory_dir → symbolic reference to parent's memory_dir
```

But workers **don't have a `Session`** — they have a `TaskSchema` and a `state` dict. The plan doesn't explain how to bridge this gap.

**Impact:** As designed, the plan's Step 6 is unimplementable without either:
- Creating a `Session` for each worker (major architectural change)
- Adding `HybridMemoryManager` support to `run_agent_task()` (moderate change)
- Limiting the feature to Session-based sub-agents only (scope reduction)

**Fix needed:** The plan must explicitly choose one of these approaches and detail the implementation. The forward audit recommended Option A (add `HybridMemoryManager` to `run_agent_task()`), but this is a significant addition that changes the plan's scope.

---

### 9. `parent_memory_id` in `TaskContract` Is a Session ID, Not a Directory Path

**Gap:** The plan conflates `parent_memory_id` (a session ID string in `TaskContract`) with `parent_memory_dir` (a filesystem path). The plan says:

> "Pass `parent_memory_dir` from the orchestrator's session"

But `TaskContract.parent_memory_id` is a **session ID** (e.g., `"abc-123-def"`), not a directory path. To convert it to a directory, you need to:
1. Look up the session in the database via `db_repo.get_session(parent_memory_id)`
2. Extract `memory_dir` from the session record
3. Handle the case where `memory_dir` is NULL (session was created before the column existed)

The plan doesn't mention this lookup step at all.

**Impact:** If implemented as the plan literally says, `inherit_from()` would receive a session ID string like `"abc-123-def"` and try to open it as a filesystem path, which would fail.

**Fix needed:** The plan must specify that `parent_memory_id` requires a DB lookup to resolve to `parent_memory_dir` before calling `inherit_from()`.

---

### 10. No `parent_memory_id` Column in Session Database Model

**Gap:** The plan's Step 8 (CLI `memory family` command) requires tracking parent-child session relationships in the database. But `SessionModel` has no `parent_memory_id` or `parent_session_id` column:

```python
class SessionModel(Base):
    id = Column(String, primary_key=True)
    working_dir = Column(String, nullable=False, default=".")
    memory_id = Column(String, nullable=True)
    memory_dir = Column(String, nullable=True)
    status = Column(String, default="active")
    # No parent_session_id!
```

**Impact:** The `memory family` CLI command cannot work without a schema migration. The promotion workflow also needs this to know which parent to promote to.

**Fix needed:** Add `parent_session_id = Column(String, nullable=True)` to `SessionModel` and create a migration.

---

### 11. `HybridMemoryManager.__init__` Creates Parent Directory Structure

**Gap:** The plan's Step 1 adds `parent_memory_dir: Path | None` to `__init__()`, but the existing `__init__` calls:

```python
self.workspace_dir.mkdir(parents=True, exist_ok=True)
```

If `parent_memory_dir` is accidentally passed as `workspace_dir` (e.g., due to parameter confusion), this would create a full memory directory structure inside the parent's memory directory. The plan doesn't guard against this.

**Impact:** Potential for creating nested memory directories if parameters are mixed up.

**Fix needed:** Add a check that `workspace_dir` and `parent_memory_dir` are not the same path (if both are provided).

---

## 🟡 MEDIUM — Nice-to-Have Improvements

### 12. Searching Two Indices on Every Recall — Performance Impact

**Gap:** The plan modifies `recall()` and `get_memory_context()` to search both own and parent indices on **every call**. For a sub-agent that recalls memory frequently (every turn), this doubles the search latency — two SQLite queries, two embedding lookups, and a merge step each time.

**What's missing:**
- No caching of parent search results
- No consideration of whether parent memories should be searched at all for certain queries
- No batching or prefetching of parent memories at sub-agent startup

**Impact:** Increased latency for every memory recall in sub-agents. The embedding computation (even with hash fallback) is non-trivial.

**Suggestion:** Consider prefetching parent memories at `inherit_from()` time and caching them, or at least document this as a known performance trade-off.

---

### 13. No Test for Parent Index Staleness

**Gap:** The plan's test list doesn't include a test for **parent index staleness** — what happens when the parent adds new memories after the sub-agent has already called `inherit_from()`? The `_parent_index` is a snapshot at inherit time; it won't reflect new parent memories.

**Impact:** Sub-agents may miss parent memories created after their spawn time. This may be intentional (snapshot semantics) but should be tested and documented.

**Suggestion:** Add a test that verifies parent memories added AFTER `inherit_from()` are NOT visible to the child (if snapshot semantics are intended), or implement re-indexing if live semantics are desired.

---

### 14. No Test for `inherit_from()` Called Multiple Times

**Gap:** The CLI command `memory inherit <parent_session_id>` suggests users can call `inherit_from()` multiple times. But there's no test for:
- Calling `inherit_from()` twice with different parents (does the first parent's index get properly closed?)
- Calling `inherit_from()` with the same parent twice (is it idempotent?)
- Calling `inherit_from()` with an invalid path after a valid one (does it gracefully degrade?)

**Impact:** Resource leaks and undefined behavior with repeated calls.

---

### 15. No Test for `promote_to_parent()` with Empty/Invalid Parent

**Gap:** The plan doesn't specify or test what happens when:
- `promote_to_parent()` is called but `parent_memory_dir` is None
- `promote_to_parent()` is called but the parent directory no longer exists
- `promote_to_parent()` is called with a `filter_fn` that rejects all memories (should return 0, but is this tested?)

---

### 16. `get_memory_context()` Doesn't Distinguish Parent vs Own Memories

**Gap:** The plan says to add a `[Parent]` prefix to parent context, but the current `get_memory_context()` formats all results identically:

```python
lines.append(f"Source: {source} (score: {score:.2f})")
```

When merging results from two indices, there's no way to tell which memories are from the parent vs own directory. The plan mentions a `[Parent]` prefix but doesn't specify how to implement it (the `HybridMemoryIndex.search()` results don't carry an "origin" flag).

**Impact:** The agent can't distinguish between its own memories and inherited parent memories, which may cause confusion about what it "knows" vs what it "inherited."

**Suggestion:** Add an `origin` field to search results during merge, and format parent memories with a `[Parent Memory]` prefix in `get_memory_context()`.

---

### 17. No Integration with `Memory` (Bank) System

**Gap:** The codebase has **two memory systems**:
1. `HybridMemoryManager` (file + SQLite index) — used by `Session`
2. `Memory` / `MemoryManager` (SQLite bank with `memory_id` scoping) — used by the older bank system

The `Memory` system already has `parent_memory_id`, `fork()`, and `merge()` methods (in `memory_bank.py`). The plan doesn't mention this existing system at all. If the goal is cross-agent memory, should both systems support it? Or is the bank system being deprecated?

**Impact:** Inconsistent feature set across memory systems. Developers may implement cross-agent memory in `HybridMemoryManager` but forget the `Memory` bank system.

---

### 18. No Cleanup of Worker Memory After Promotion

**Gap:** After `promote_to_parent()` copies memories to the parent, the plan doesn't specify what happens to the worker's own memory directory. Should it be deleted? Kept for audit? The worker's `bank/` directory and `index.sqlite` will persist on disk indefinitely.

**Impact:** Disk space leak from accumulated worker memory directories.

---

## 🟢 LOW — Minor Observations

### 19. Plan Uses "Symbolic Reference" Terminology Incorrectly

**Gap:** The plan's architecture diagram shows:
```
└── parent_memory_dir → symbolic reference to parent's memory_dir
```

This is not a symbolic link (symlink) — it's a path string stored in memory. The arrow notation is misleading and could confuse implementers into thinking they need to create actual symlinks.

---

### 20. No Documentation of `MemoryScope` Interaction

**Gap:** `TaskContract` already has a `memory_scope: MemoryScope` field with values `SHARED`, `ISOLATED`, `SCOPED`. The `Memory` bank system already implements these scopes. The plan doesn't explain how the new `parent_memory_dir` feature interacts with `memory_scope`. For example:
- If `memory_scope=ISOLATED`, should parent memory inheritance be disabled?
- If `memory_scope=SCOPED`, does this replace or complement the existing `parent_memory_id` in the bank system?

---

### 21. No Metrics or Observability

**Gap:** The plan doesn't mention any metrics for:
- How many sub-agents inherit from a given parent
- How many memories are promoted
- Search latency for dual-index recalls
- Failed inheritance attempts

In production, these would be important for debugging and performance monitoring.

---

### 22. CLI `memory family` Requires Schema Migration Not Mentioned

**Gap:** Step 8 adds a `memory family` CLI command that shows parent/child relationships. This requires:
1. A `parent_session_id` column on `SessionModel` (doesn't exist)
2. A database migration
3. A way to query child sessions given a parent

The plan doesn't mention any of these prerequisites.

---

### 23. `_get_entry_temporal_fields` Duplication Noted But Not Prioritized

**Gap:** Both the plan and forward audit note that `_get_entry_temporal_fields` is defined twice (lines 136 and 207 of `hybrid_memory.py`). The forward audit rates this as 🟢 Low. However, during implementation of the parent memory feature, a developer may accidentally modify only one copy, introducing subtle bugs. This should be cleaned up **before** the parent memory changes.

---

### 24. No Consideration of Embedding Provider Consistency

**Gap:** When `inherit_from()` creates a new `HybridMemoryIndex` for the parent directory, it gets its own `EmbeddingProvider` instance. If the parent and child use different embedding models or providers (e.g., parent used Gemini embeddings, child uses hash fallback), the vector spaces will be incompatible, and merged search results will have meaningless scores.

**Impact:** Inconsistent search quality when parent and child have different embedding configurations.

---

## What the Plan Gets Right

For completeness, here's what the plan handles well:

1. **Read-sharing + write isolation** is the correct architectural pattern
2. **Promotion as a separate step** is good — avoids automatic pollution of parent
3. **No circular deps** (parent never reads from child) is correct
4. **File-level promotion** (copy markdown files + re-index) is simpler and more robust than trying to merge SQLite databases
5. **Test coverage plan** is reasonable for the happy path
6. **CLI commands** are a nice touch for manual operations

---

## Recommended Additions to the Plan

| # | Addition | Priority |
|---|----------|----------|
| 1 | Add path validation to `inherit_from()` — resolve, verify under safe root | 🔴 Critical |
| 2 | Fix `close()` to also close `_parent_index` | 🔴 Critical |
| 3 | Fix `get_or_create()` recursive call to pass all params | 🔴 Critical |
| 4 | Add graceful degradation when parent dir is deleted mid-session | 🔴 Critical |
| 5 | Add file-based locking for concurrent `promote_to_parent()` | 🟠 High |
| 6 | Fix file naming collisions in promotion | 🟠 High |
| 7 | Explicitly document the worker execution path gap and chosen approach | 🟠 High |
| 8 | Clarify `parent_memory_id` (session ID) vs `parent_memory_dir` (path) | 🟠 High |
| 9 | Add `parent_session_id` column to `SessionModel` | 🟠 High |
| 10 | Fix `_discover_cross_session_memories` index leak | 🟠 High |
| 11 | Add `[Parent Memory]` prefix to merged search results | 🟡 Medium |
| 12 | Add tests for repeated `inherit_from()`, staleness, empty parent | 🟡 Medium |
| 13 | Document interaction with `MemoryScope` and bank system | 🟡 Medium |
| 14 | Clean up `_get_entry_temporal_fields` duplication before starting | 🟢 Low |
