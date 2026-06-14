# Kanban Phase 2 — Forward Audit

> **Date:** 2026-07-19
> **Auditor:** OWL (Lucien) — inline execution
> **Scope:** 6 high-priority issues from MASTER_AUDIT_REPORT.md
> **Method:** Direct code reading + ast-tools structural analysis

---

## Issue #1: TOCTOU Race in SessionManager

### Finding: ✅ CONFIRMED — but already mitigated

**Location:** `src/nexusagent/core/session.py:600-677`

The `SessionManager.get_or_create()` method (line 617-651) uses a classic double-check locking pattern:

```python
# Fast path: no lock needed for read (line 627)
existing = self._sessions.get(session_id)
if existing is not None:
    return existing

# Slow path: acquire lock to prevent duplicate creation (line 632)
async with self._lock:
    # Double-check after acquiring lock (line 634)
    existing = self._sessions.get(session_id)
    if existing is not None:
        return existing
```

**Verdict:** The TOCTOU concern is real in theory — between the fast-path read and the lock acquisition, another coroutine could create the same session. However, the double-check pattern on line 634-636 mitigates this: after acquiring the lock, it re-checks before creating. The only real risk is if two coroutines pass the fast-path check simultaneously, both acquire the lock sequentially, and both create — but the second one would overwrite the first in `self._sessions[session_id] = session` (line 650), leaking the first session.

**Actual risk level:** Low. The asyncio lock ensures serialized access. The "race" is only possible if two coroutines call `get_or_create()` with the same new session_id simultaneously, which is unlikely in practice (session IDs are UUIDs).

**Fix complexity:** S — add a set of "being created" session IDs checked under the lock.

---

## Issue #2: No NATS Durability (Ephemeral Subscriptions)

### Finding: ✅ CONFIRMED — but partially mitigated by JetStream

**Location:** `src/nexusagent/infrastructure/bus.py:57-82`

The `subscribe()` method creates standard NATS subscriptions:
```python
sub = await self.nc.subscribe(subject, cb=callback)
```

These are **ephemeral subscriptions** — if the consumer disconnects, messages published to that subject are lost.

**However**, the system already uses **JetStream KV** for result storage (line 44-52, 94-140):
```python
self.js = self.nc.jetstream()
self.kv = await self.js.create_key_value(bucket="nexus_results")
```

So task *results* are durable (stored in JetStream KV), but task *dispatch* messages (published via `publish()` on line 84-92) are NOT durable — they're fire-and-forget.

**Verdict:** The audit finding is correct for the dispatch path. If a worker is down when a task is published, the task is lost. The JetStream KV store only persists results, not the dispatch messages.

**Fix complexity:** M — would require JetStream consumers with durable names for the dispatch subject.

---

## Issue #3: `bytes` Crashes NATS Encoder

### Finding: ✅ CONFIRMED

**Location:** `src/nexusagent/infrastructure/bus.py:18-22`

```python
class NATSJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
```

The `default()` method only handles `datetime` and `date`. Any `bytes` object in a message payload will raise `TypeError: Object of type bytes is not JSON serializable`.

The `publish()` method (line 84-92) uses this encoder:
```python
payload = json.dumps(message, cls=NATSJSONEncoder).encode()
```

And `put_result()` (line 94-117) also uses it:
```python
payload = json.dumps(result, cls=NATSJSONEncoder).encode()
```

**Verdict:** Confirmed. If any tool result or task message contains `bytes` (e.g., binary file content, base64-encoded data), the NATS encoder will crash.

**Fix complexity:** S — add `bytes` handling to `NATSJSONEncoder.default()` (decode to str or use base64).

---

## Issue #4: NATS is Single Point of Failure

### Finding: ✅ CONFIRMED — architecturally fundamental

**Location:** `src/nexusagent/infrastructure/bus.py` (entire file), `src/nexusagent/core/worker.py:80-201`

The `NexusWorker` class (worker.py:80) connects to NATS in its `start()` method and subscribes to a subject. All task dispatch goes through NATS. If NATS goes down:

1. No new tasks can be dispatched (worker can't receive them)
2. `AgentBus.connect()` raises `NATSError` (bus.py:53-55)
3. Worker reconnects with `reconnect_time_wait` and `max_reconnect_attempts` (bus.py:40-41)
4. But during reconnection, all task dispatch is paused

**Verdict:** Confirmed. NATS is the sole transport for task dispatch. The system has reconnection logic but no fallback transport.

**Fix complexity:** L — would require a dual-transport architecture (NATS + HTTP fallback) or migrating dispatch to HTTP.

---

## Issue #5: 5 Global Singletons Block Multi-Tenancy

### Finding: ✅ CONFIRMED — 8 module-level singletons found

**Locations:**
| Singleton | File | Line |
|-----------|------|------|
| `session_manager = SessionManager()` | `core/session.py` | 677 |
| `worker = NexusWorker()` | `core/worker.py` | 205 |
| `worker_pool = WorkerPool()` | `core/worker.py` | 311 |
| `sdk = NexusSDK()` | `server/sdk.py` | 220 |
| `auth_manager = AuthManager()` | `infrastructure/auth.py` | 133 |
| `deep_research_orchestrator = DeepResearchOrchestrator()` | `core/orchestration.py` | 193 |
| `db_manager = DatabaseManager()` | `infrastructure/db/__init__.py` | 29 |
| `llm = LLMProvider()` | `llm/llm.py` | 129 |

Plus the lazy singleton in bus.py:
```python
_default_bus: AgentBus | None = None
def get_bus() -> AgentBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = AgentBus()
```

**Verdict:** Confirmed. 8+ module-level singletons. These share state across all requests/users, making multi-tenancy impossible without refactoring to instance-based or context-based patterns.

**Fix complexity:** L — would require dependency injection or context-local storage for all singletons.

---

## Issue #6: No MCP Support / No Codebase Indexing/RAG

### Finding: ⚠️ PARTIALLY CONFIRMED

**MCP Support:** Confirmed absent. Zero matches for "mcp" or "MCP" in `src/nexusagent/`. The tool registration system (`register_all.py`) uses a hardcoded list of tools — no dynamic MCP tool loading.

**Codebase Indexing/RAG:** **NOT absent.** The system has a full hybrid search index:
- `src/nexusagent/memory/index/index.py` — `HybridMemoryIndex` class (613 lines)
- Uses SQLite FTS5 + sqlite-vec for vector search
- Supports `index_file()`, `async_index_file()`, `search()`, `rebuild()`
- Embedding fallback chain: Gemini API → local sentence-transformers → SHA256 hash

**Verdict:** 
- No MCP support → Confirmed. Would need a plugin/MCP adapter layer.
- No RAG/indexing → **False**. The system has a capable hybrid search index. The audit finding was incorrect on this point — it may have been referring to the agent's *runtime* ability to search its own codebase (the index exists but may not be wired into the agent's tool loop).

**Fix complexity:** 
- MCP: L — new adapter layer for dynamic tool loading
- RAG wiring: M — connect existing `HybridMemoryIndex` to agent's tool loop

---

## Summary

| # | Issue | Confirmed? | Actual Risk | Fix Complexity |
|---|-------|------------|-------------|----------------|
| 1 | TOCTOU in SessionManager | ✅ Mitigated | Low | S |
| 2 | No NATS durability | ✅ Confirmed | Medium | M |
| 3 | bytes crashes NATS encoder | ✅ Confirmed | Medium | S |
| 4 | NATS is SPOF | ✅ Confirmed | High | L |
| 5 | 8 global singletons | ✅ Confirmed | Medium | L |
| 6 | No MCP / No RAG | ⚠️ Partial | MCP: High, RAG: Low | L/M |

**Key insight:** Issues #2, #3, #4 are all NATS-related and should be addressed together as a "NATS reliability" epic. Issue #1 is already mitigated. Issue #5 is architectural and should be a separate epic. Issue #6's RAG finding was wrong — the index exists but may need better agent integration.
