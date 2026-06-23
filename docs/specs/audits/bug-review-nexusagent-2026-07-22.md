# Bug Review — NexusAgent 2026-07-22

**Auditor:** OWL (plan-and-audit high mode)
**Scope:** Logic bugs, security issues, code quality problems

---

## 🔴 Critical Bugs

### BUG-001: `refine_node` Silent Error Swallowing
**File:** `src/nexusagent/core/graph.py:125-127`
```python
except Exception as e:
    return {"plan_approved": True, "error": None}  # BUG: should be False
```
**Impact:** Failed plan refinement treated as success. Research workflow proceeds with flawed plan.
**Fix:** Return `{"plan_approved": False, "error": str(e)}`

---

### BUG-002: API Key in URL Query Parameter
**File:** `src/nexusagent/server/websocket.py:35`
```python
token = websocket.query_params.get("token")
effective_key = header_key or token
```
**Impact:** API keys logged in server access logs, browser history, proxy/CDN logs, Referer headers.
**Fix:** Deprecate query-param; implement token-exchange endpoint.

---

### BUG-003: Sync SQLite in Async Event Loop
**Files:** `src/nexusagent/memory/index/index.py` (7 locations), `src/nexusagent/memory/hybrid_memory.py:48-58`
```python
def search_sync(self, query: str, ...) -> list[MemoryItem]:
    conn = sqlite3.connect(self.db_path)  # New connection every call
    ...
```
Called from `session.send()` → `get_memory_context()` → blocks event loop.
**Fix:** Use persistent connection pool; call async `search()` instead.

---

### BUG-004: SessionManager Spin Loop No Timeout
**File:** `src/nexusagent/core/session/manager.py:82-88`
```python
while session_id in self._creating:
    await asyncio.sleep(0)  # No timeout!
```
If creating coroutine panics/cancelled, `session_id` stuck in `_creating` forever.
**Fix:** `asyncio.wait_for()` with 30s timeout, or `asyncio.Event` per session.

---

### BUG-005: `sanitize_tool_output` Always Marks Untrusted
**File:** `src/nexusagent/core/agent.py:52-53`
```python
def sanitize_tool_output(text: str) -> str:
    return f"{_UNTRUSTED_MARKER}\n{text}"  # Always!
```
**Impact:** LLM receives UNTRUSTED marker on EVERY tool output — cries wolf, degrades defense.
**Fix:** Only prepend when `_detect_injection()` returns `True`.

---

### BUG-006: No TLS/SSL Configuration
**File:** `src/nexusagent/server/server.py`
- FastAPI/uvicorn: no SSL args
- NATS: defaults to `nats://localhost:4222` (plaintext)
**Impact:** All traffic (API keys, code, secrets) transmitted in plaintext.

---

## 🟠 High Severity Bugs

### BUG-007: Session `send()` Double Message Conversion
**File:** `src/nexusagent/core/session/session.py:222-240`
```python
# Converts messages to dicts for compaction
messages_dict = [msg_to_dict(m) for m in messages]
# Compaction operates on dicts
compacted = await compaction.compact(messages_dict)
# Converts BACK to LangChain messages
messages = [dict_to_msg(d) for d in compacted]
```
**Impact:** 80+ objects created per turn; loses LangChain metadata (tool_call_id, response_metadata, etc.)

---

### BUG-008: Rate Limiter Memory Leak
**File:** `src/nexusagent/infrastructure/rate_limit.py:17`
```python
_RATE_LIMIT_PER_CLIENT: dict[str, list[float]] = {}
_RATE_LIMIT_CLEANUP = 300  # Defined but NEVER USED
```
**Impact:** Dict grows unboundedly across all clients forever.

---

### BUG-009: Module-Level `_read_files` Leaks Across Sessions
**File:** `src/nexusagent/tools/fs_base.py:16`
```python
_read_files: set[str] = set()  # Module-level!
```
**Impact:** Read-before-write tracking pollutes unrelated sessions.

---

### BUG-010: Bus Subscription Memory Leak
**File:** `src/nexusagent/infrastructure/bus.py`
```python
_subscriptions: list = []  # Never cleaned on unsubscribe
```

---

### BUG-011: SQLite Connection Leak in Graph
**File:** `src/nexusagent/core/graph.py:230-248`
```python
conn = sqlite3.connect(...)
try:
    workflow.compile()
except Exception:
    raise  # conn never closed!
```

---

### BUG-012: TUI Sliding Window Bypass (4 Paths)
**Files:** `interfaces/tui/input.py:47`, `interfaces/tui/websocket.py:61,72,158,174,182`
50-widget limit only enforced in `_mount_message()`. Direct `messages_container.mount()` calls bypass it.

---

### BUG-013: TUI `_busy` Not Reset on Disconnect
**File:** `src/nexusagent/interfaces/tui/websocket.py:165-178`
```python
except ConnectionClosedOK:
    return  # _busy NOT reset!
except ConnectionClosedError:
    # retry logic...
    return  # _busy NOT reset!
```
**Impact:** TUI permanently stuck in "busy" state after disconnect.

---

### BUG-014: TUI Approval Race Condition
**File:** `src/nexusagent/interfaces/tui/streaming.py:78-89,164-169`
Auto-approve task AND approval modal both fire for same tool call → duplicate approvals sent.

---

### BUG-015: TUI Stale Widget Refs After `/clear`
**File:** `src/nexusagent/interfaces/tui/streaming.py:265-266`
```python
app.messages_container.clear()
# _current_assistant and _current_tool still reference REMOVED widgets
```
Next `response_chunk` calls `update()` on unmounted widget → crash or data loss.

---

### BUG-016: TUI Unbounded Queues
**Files:** `interfaces/tui/input.py:38`, `interfaces/tui/app.py:178`
```python
_pending_inputs: list = []  # No max size
_input_queue = asyncio.Queue()  # No maxsize
```
Spamming Enter while agent busy → memory exhaustion DoS.

---

## 🟡 Medium Severity Bugs

### BUG-017: `llm/models.py` God Object
Imported by 17+ modules. Mixes domain (Task, Result) with infrastructure (MemoryScope, AgentEvent).

---

### BUG-018: `WorkerPool._execute_bounded` Misleading Error
**File:** `src/nexusagent/core/worker/pool.py:128-142`
```python
if first_turn_fails_with_retry:
    message = "Max turns reached. Last: None"  # Confusing!
```

---

### BUG-019: `Memory.merge` O(n²) Deduplication
**File:** `src/nexusagent/memory/memory_bank.py:220-240`
Deduplication in Python, not DB; compares content text not ID.

---

### BUG-020: `NexusWorker._heartbeat` None Dereference
**File:** `src/nexusagent/core/worker/worker.py:224-233`
```python
task_obj.status  # AttributeError if task deleted during heartbeat
```

---

### BUG-021: Prompt Injection via `@file` Chains
**File:** `src/nexusagent/infrastructure/template_includes.py:50-70`
No restriction on includable files. Malicious NEXUS.md could include sensitive files.

---

### BUG-022: Shell Access by Default
**File:** `src/nexusagent/infrastructure/config.py:43`
`run_shell` in default `enabled_tools`. Should be opt-in.

---

### BUG-023: Session ID Truncation Collision Risk
**File:** `src/nexusagent/interfaces/tui/app.py`
8 hex chars = 32 bits. Birthday paradox: ~77k sessions for 50% collision.

---

### BUG-024: No Data Encryption at Rest
**File:** `src/nexusagent/infrastructure/db/manager.py`
SQLite stores all conversation history in plaintext.

---

### BUG-025: Sensitive Data in Logs
**Files:** `server/routes.py:100`, `websocket.py:129`
Error handlers log full exception details including request bodies.

---

### BUG-026: `CompactionPipeline` Off-by-None Naming
**File:** `src/nexusagent/memory/compaction.py:191`
```python
keep_last=10  # Actually summarizes FIRST 10, keeps the rest!
```
Naming misleading — should be `summarize_first` or similar.

---

### BUG-027: `Agent.__init__` Race Condition on MCP Tool Loading
**File:** `src/nexusagent/core/agent.py:175-181`
`_ROLE_TOOLS` populated at module load before MCP tools loaded. First invocation uses stale list.

---

### BUG-028: `search_local_docs` Missing Timeout
**File:** `src/nexusagent/tools/research.py`
```python
subprocess.run(["npx", "ctx7", ...])  # No timeout!
```
Can hang indefinitely.

---

### BUG-029: History File No Integrity Verification
**File:** `src/nexusagent/widgets/chat_input.py`
`~/.nexusagent/history.json` — no integrity check. Symlink attacks possible.

---

### BUG-030: DB Type Inconsistency
**File:** `src/nexusagent/infrastructure/db/models.py`
`ResultModel.success` uses `Integer` (0/1) while Pydantic `ResultSchema` uses `bool`.

---

## 🔵 Low Severity / Code Quality

### BUG-031: `Agent._resolve_model` Misleading Docstring
**File:** `src/nexusagent/core/agent.py:104-157`
Docstring says returns model+provider but only returns model name.

---

### BUG-032: `bus.py` Shallow Health Check
**File:** `src/nexusagent/infrastructure/bus.py`
`check_health()` only checks `is_closed`, not actual NATS connectivity.

---

### BUG-033: Auth Module Eager Singleton
**File:** `src/nexusagent/infrastructure/auth.py`
Singleton created at import time, even in tests that don't need it.

---

### BUG-034: No Key Rotation Mechanism
**File:** `src/nexusagent/infrastructure/auth.py`
Once master key stored, no way to rotate without re-encrypting all keys.

---

### BUG-035: `double-quote-string-fixer` Conflicts with Quote Style
**File:** `.pre-commit-config.yaml`
Pre-commit hook conflicts with project's mixed quote conventions.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 6 |
| 🟠 High | 10 |
| 🟡 Medium | 13 |
| 🔵 Low | 5 |
| **Total** | **34** |

**Top Priority Fixes (This Sprint):**
1. BUG-001 through BUG-006 (6 critical from 2026-06-16)
2. BUG-012 through BUG-016 (5 new TUI critical/high)
3. BUG-007 through BUG-011 (5 high-severity core bugs)