# Kanban Phase 2 — Reverse Audit

> **Date:** 2026-07-19
> **Auditor:** OWL (Lucien) — inline execution
> **Scope:** 6 high-priority issues — what the OBVIOUS fix misses
> **Method:** Code reading + cross-reference analysis + failure mode thinking

---

## Issue #1: TOCTOU Race in SessionManager

### Obvious Fix
Add a `_creating: set[str]` tracked under the lock to prevent duplicate creation.

### What It Misses

1. **Session ID collision is the wrong frame.** The real question is: when would two coroutines call `get_or_create()` with the same ID? If the answer is "never in practice" (UUIDs), the fix is pure overhead. If the answer is "user-spawned and system-spawned sessions can collide", then the real fix is namespace isolation, not lock hardening.

2. **Memory leak from overwritten sessions.** If the race *does* happen (two create paths, second overwrites first in `self._sessions`), the first Session object is dropped without calling `session.close()`. This means: DB status not updated to closed, memory files not flushed, NATS subscriptions not cleaned up. The "fix" of just checking `_creating` hides this leak.

3. **`mark_idle()` and `close()` races.** `mark_idle()` (session.py:653-662) checks `session.status == "active"` and then does an async DB update — but between the check and the DB write, another coroutine could call `close()`. The status could go "active → idle" after a close, leaving an orphan in the DB.

4. **No lock on `mark_idle()` or `close()`.** These methods don't acquire `self._lock` — they rely on dict-level atomicity. Under high concurrency, `close()` could pop a session while `mark_idle()` is mid-update.

**Hidden dependency:** The Session constructor creates a `memory_dir` on disk (`session.py:639-640`). If two Session objects are created for the same session_id (race), they both write to the same memory_dir — potential file corruption.

---

## Issue #2: No NATS Durability

### Obvious Fix
Use JetStream pull consumers with durable names instead of push subscriptions.

### What It Misses

1. **JetStream consumer semantics are different.** Push subscriptions are fire-and-forget; pull consumers require explicit acknowledgment. This means `handle_task()` in worker.py must change to manually ack/nack messages. If the worker crashes mid-processing, the message must be redelivered — but the worker might have partially processed it (written to DB but not completed). Idempotency becomes mandatory.

2. **Ordered delivery vs parallelism.** JetStream consumers deliver messages sequentially per subject by default. If task processing is slow, the worker could become a bottleneck. You'd need `deliver_policy=all` or multiple consumer names for parallelism — which changes the dispatch semantics.

3. **The real fix might be HTTP dispatch.** The audit found that task submission already has an HTTP path (FastAPI server). Dispatching via HTTP (POST to worker endpoint) with DB-backed durability would eliminate NATS as the dispatch transport entirely. This is architecturally simpler than adding durable NATS consumers.

4. **KV store is already durable but not transactional.** `put_result()` stores task results in JetStream KV, but there's no transaction wrapping "mark task running in DB + publish result to KV". If the process crashes between these two, the DB shows "running" forever but the result is in KV. A new durable consumer would need to handle this inconsistency.

5. **`subscribe()` retry logic is misleading.** The current retry (bus.py:69-82) retries subscription creation, not message redelivery. If the initial subscribe fails 3 times, the worker gives up entirely. A durable consumer would auto-reconnect.

---

## Issue #3: bytes Crashes NATS Encoder

### Obvious Fix
Add `bytes` handling to `NATSJSONEncoder.default()`:
```python
if isinstance(obj, bytes):
    return obj.decode('utf-8', errors='replace')
```

### What It Misses

1. **Encoding assumption is fragile.** Blindly decoding bytes as UTF-8 will corrupt binary data (file contents, images). The correct fix depends on context: if bytes represent text, decode; if binary, use base64. But the encoder has no context about what the bytes represent.

2. **The real question: why is bytes in the message?** Tool results should be strings. If a tool returns bytes, that's the tool's bug — not the encoder's. The fix should be at the tool boundary (ensure all tool results are strings), not at the serialization layer.

3. **Downstream consumers expect strings.** If the encoder silently converts bytes to strings, downstream code that checks `isinstance(result, bytes)` will break. The fix changes the contract.

4. **Other non-serializable types.** `bytes` is just one of many types that could fail: `set`, `Path`, `Exception`, custom objects. A comprehensive fix would need a more robust serialization strategy (e.g., `pydantic` model validation before NATS publish).

5. **The `put_result()` path serializes tool results.** If a tool returns a large binary result (e.g., `read_file` on a binary file), the entire result is serialized to JSON and stored in KV. This could hit NATS message size limits (default 1MB). The fix needs a size check.

---

## Issue #4: NATS is SPOF

### Obvious Fix
Add reconnection logic, health monitoring, and graceful degradation.

### What It Misses

1. **Reconnection already exists but is insufficient.** `bus.py:38-42` has `reconnect_time_wait` and `max_reconnect_attempts`. But `max_reconnect_attempts` is a config setting — if it's `-1` (infinite), the worker hangs forever trying to reconnect. If it's finite, the worker dies and tasks are lost.

2. **The real fix is architectural: decouple task submission from NATS.** The HTTP server already has task submission endpoints. Workers could poll the HTTP server for tasks instead of subscribing to NATS. This eliminates NATS as the dispatch transport while keeping it for optional real-time features.

3. **NATS JetStream is already a dependency for KV.** Even if dispatch moves to HTTP, the KV store (`nexus_results` bucket) still depends on NATS JetStream. So NATS can't be fully removed — it needs to be made optional at the dispatch layer.

4. **Worker crash detection is missing.** There's no heartbeat mechanism. If a worker process crashes (OOM, segfault), the dispatcher has no way to know. Tasks assigned to that worker stay "running" forever. The fix needs a heartbeat/lease system.

5. **Circular dependency: singletons prevent multi-NATS.** The `get_bus()` singleton (bus.py:161-166) creates one global bus. If you wanted to connect to multiple NATS servers (for HA), the singleton pattern prevents it. This connects to Issue #5.

---

## Issue #5: 8 Global Singletons

### Obbitrary Fix
Convert singletons to dependency injection or context-local storage.

### What It Misses

1. **Not all singletons are equal.** Some are stateless utilities (`llm = LLMProvider()`), some are stateful caches (`session_manager = SessionManager()`), some are connection pools (`worker_pool = WorkerPool()`). Each needs a different refactoring strategy:
   - Stateless: Can stay singleton (thread-safe by design)
   - Stateful caches: Need context-local or request-scoped instances
   - Connection pools: Need lifecycle management (startup/shutdown)

2. **The testing impact is massive.** Every test that relies on the singleton's state will break. The `worker_pool` singleton means all tests share the same pool — tests can't run in isolation. Refactoring to instance-based requires updating every test that imports these singletons.

3. **`set_bus()` is the only injection point.** Only `AgentBus` has a `set_bus()` override for testing. None of the other singletons have this. Adding injection points is prerequisite to testing the refactor.

4. **The refactoring order matters.** `session_manager` is used by `Session`, which is used by the server, which is used by the TUI. Refactoring it requires refactoring all dependents. A bottom-up approach (start with leaf singletons like `llm`, work up to `session_manager`) is safer.

5. **Multi-tenancy might not be the right goal.** The user runs a single-user system. Multi-tenancy adds complexity without immediate value. The real goal should be **testability** — making the code testable in isolation. This is a smaller, more valuable refactor.

---

## Issue #6: No MCP Support / No RAG

### Obvious Fix
Add MCP tool loading, wire HybridMemoryIndex into agent tool loop.

### What It Misses

1. **The RAG finding was wrong.** `HybridMemoryIndex` (613 lines) exists and is fully functional. The issue is that it's not wired into the agent's tool loop — the agent can't call `index.search()` during task execution. The fix is a tool registration, not an index implementation.

2. **MCP support requires a plugin architecture.** The current tool system (`register_all.py`) uses a hardcoded list of tools. Adding MCP requires:
   - A plugin interface (how tools are described)
   - A plugin loader (how tools are discovered)
   - A plugin sandbox (how tools are isolated)
   - A plugin lifecycle (how tools are started/stopped)
   
   This is a significant architectural addition, not just "add MCP loading."

3. **The memory index has a singleton problem too.** `_DB_POOL` in `memory/index/embeddings.py` is a module-level singleton. If you wanted per-tenant indexes, this would need refactoring (connects to Issue #5).

4. **MCP tools might conflict with existing tools.** If an MCP server provides a `read_file` tool, it would conflict with the existing `read_file` in `tools/fs.py`. The tool registry needs conflict resolution.

---

## Cross-Cutting Findings

### Dependency Graph
```
Issue #4 (NATS SPOF) ──depends──→ Issue #2 (NATS durability) ──depends──→ Issue #3 (bytes encoder)
Issue #5 (Singletons) ──blocks──→ Issue #4 (multi-NATS for HA)
Issue #5 (Singletons) ──blocks──→ Issue #6 (per-tenant MCP)
Issue #1 (TOCTOU) ──independent──→ all others
Issue #6 (MCP) ──independent──→ all others
```

### Optimal Fix Order
1. **Issue #3 (bytes encoder)** — S, no dependencies, prevents crashes
2. **Issue #1 (TOCTOU)** — S, no dependencies, prevents rare races  
3. **Issue #2 + #4 (NATS)** — M/L, should be one epic, may require architectural shift
4. **Issue #5 (Singletons)** — L, prerequisite for #6's multi-tenant variant
5. **Issue #6 (MCP/RAG)** — L, RAG wiring is easy (M), MCP is hard (L)

### Keystone Fix
**Issue #3 (bytes encoder) is the keystone.** It's the smallest fix, has no dependencies, and prevents a class of crashes that could cascade into other issues. Fix it first to stabilize the NATS layer before making architectural changes.

### What the Audit Got Wrong
- **Issue #6's "no RAG" finding was incorrect.** The codebase has a 613-line `HybridMemoryIndex` with FTS5 + sqlite-vec. The finding likely meant "the agent can't use the index at runtime" — which is a wiring issue, not a missing capability.
- **Issue #1's severity was overstated.** The double-check locking pattern already mitigates the TOCTOU. The real risk is session leak on the extremely rare race, not data corruption.
