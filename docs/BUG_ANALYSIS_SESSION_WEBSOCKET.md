# NexusAgent Bug Analysis — Session, WebSocket & Client/Server Issues

**Date:** 2026-07-23  
**Status:** Analysis only — no changes made  
**Scope:** Session handling, WebSocket protocol, client-server behavior

---

## Previously Identified Critical Bugs (from 2026-06-14 audit)

### 1. Thread-Local Policy Context Broken Across Async Boundaries
**File:** `src/nexusagent/core/agent.py:131`  
**Severity:** Critical  
**Issue:** `set_policy_context(role, policy)` uses `threading.local()` but `Agent.__init__` is called from async contexts (`WorkerPool._run_worker`). Thread-local doesn't propagate across coroutine boundaries.  
**Impact:** Sub-agents inherit wrong policy context from thread pool.  
**Fix:** Replace with `contextvars.ContextVar`.

### 2. SQLite Connection Leak in Research Graph
**File:** `src/nexusagent/core/graph.py:242-248`  
**Severity:** Critical  
**Issue:** `create_research_graph()` opens `sqlite3.connect()` → passes to `SqliteSaver` but never closes. Leaks one connection per research task.  
**Impact:** Resource exhaustion under load.  
**Fix:** Use context manager or store connection for cleanup.

### 3. Blocking `invoke()` in Async Context
**File:** `src/nexusagent/core/session/session.py:397`  
**Severity:** Critical  
**Issue:** `self.agent({"messages": messages})` calls blocking `invoke()` inside async `send()`. Blocks entire event loop for minutes.  
**Impact:** Freezes TUI, prevents heartbeat, breaks streaming.  
**Fix:** Use `astream()` (already partially implemented) or `run_in_executor()`.

### 4. Unbounded `asyncio.Queue` Memory Growth
**File:** `src/nexusagent/core/session/session.py:197`  
**Severity:** Critical  
**Issue:** `self._event_queue = asyncio.Queue()` (no maxsize). Fast producer (agent) + slow consumer (TUI) = unbounded growth.  
**Impact:** OOM during long sessions.  
**Fix:** `asyncio.Queue(maxsize=1000)` + backpressure.

### 5. `run_in_executor` + Thread-Local = Broken Policy in Workers
**File:** `src/nexusagent/core/worker.py:51-53`  
**Severity:** Critical  
**Issue:** `run_agent_task` runs via `run_in_executor` but `Agent.__init__` sets thread-local policy. Random thread = random/wrong policy.  
**Impact:** Security boundary violation.  
**Fix:** Use `contextvars` + run as coroutine directly.

---

## New Findings: WebSocket & Session Bugs

### 6. WebSocket Heartbeat Task Leaks on Error
**File:** `src/nexusagent/core/session/session.py:249-259`  
**Severity:** Warning  
**Issue:** `_heartbeat()` task created via `asyncio.create_task()` but never cancelled. If `astream` raises, heartbeat continues indefinitely.  
**Impact:** Memory leak, continued "Still thinking..." events after error.  
**Fix:** Store task reference, cancel in `finally` block.

### 7. No Explicit WebSocket Close on Session Close
**File:** `src/nexusagent/server/websocket.py:187-188`  
**Severity:** Warning  
**Issue:** `session.close()` called but WebSocket not explicitly closed. Relies on `WebSocketDisconnect` exception to trigger cleanup.  
**Impact:** Potential dangling connections.  
**Fix:** Call `await websocket.close()` in `finally` block after `session.close()`.

### 8. Origin Validation Uses Hardcoded List
**File:** `src/nexusagent/server/websocket.py:16-21`  
**Severity:** Suggestion  
**Issue:** `_WS_ALLOWED_ORIGINS` hardcoded. No config option for additional origins (e.g., custom domains, Tailscale IPs).  
**Impact:** Blocks legitimate connections in non-localhost deployments.  
**Fix:** Move to config (`settings.server.allowed_origins`).

### 9. Token Exchange Returns API Key Directly (Not JWT)
**File:** `src/nexusagent/server/routes.py:280-286`  
**Severity:** Warning  
**Issue:** `/auth/token` returns the raw API key as "token" with 300s expiry claim, but doesn't actually issue a short-lived JWT.  
**Impact:** API key exposed in browser storage/URLs; no real expiry enforcement.  
**Fix:** Issue signed JWT with actual expiry, validate on WS connect.

### 10. Rate Limit Middleware Skips `/sessions/` but Not `/sessions/{id}/ws`
**File:** `src/nexusagent/server/routes.py:38`  
**Severity:** Suggestion  
**Issue:** `request.url.path.startswith("/sessions/")` skips rate limiting for all session endpoints including WebSocket upgrade.  
**Impact:** WebSocket connections bypass rate limiting.  
**Fix:** Explicitly allow only `/health`, `/version`, `/auth/token`; rate limit WS upgrade.

---

## TUI-Specific Bugs

### 11. Auto-Approve Task Not Cancelled on Disconnect
**File:** `src/nexusagent/interfaces/tui/streaming.py:204-209`  
**Severity:** Warning  
**Issue:** `_auto_approve_task` created but never cancelled if WebSocket disconnects before approval sent.  
**Impact:** Orphaned task, potential error log spam.  
**Fix:** Track task, cancel in `action_quit` / disconnect handler.

### 12. Input Queue Poison Pill (`None`) Race Condition
**File:** `src/nexusagent/interfaces/tui/app.py:267`  
**Severity:** Suggestion  
**Issue:** `action_quit` puts `None` in queue, but `_ws_task` may already be cancelled. If `ws_loop` is in `receive_events()`, it never sees the `None`.  
**Impact:** Clean shutdown not guaranteed.  
**Fix:** Cancel `_ws_task` first, then drain queue.

### 13. Version Check Non-Blocking But No Retry
**File:** `src/nexusagent/interfaces/tui/websocket.py:48-69`  
**Severity:** Suggestion  
**Issue:** `check_server_version()` returns `False` on failure, but `ws_loop` proceeds anyway and will fail on `websockets.connect`.  
**Impact:** Confusing error ("Connection refused" instead of "Server unreachable").  
**Fix:** If version check fails, show error immediately; don't retry WS.

### 14. Working Directory URL Encoding Bug
**File:** `src/nexusagent/interfaces/tui/websocket.py:100-103`  
**Severity:** Warning  
**Issue:** `urllib.parse.quote(working_dir, safe='')` encodes everything including `/`, creating invalid query params like `?working_dir=home%2Fuser%2Fproject`.  
**Impact:** Server receives malformed path, workspace scoping fails.  
**Fix:** Use `quote(working_dir, safe='/')` or encode as path segment.

### 15. Spinner Stays On After Error
**File:** `src/nexusagent/interfaces/tui/streaming.py:146-152`  
**Severity:** Warning  
**Issue:** On `error` event, `set_spinner(False)` called but `_busy = False` then `set_status("Error")` — spinner state inconsistent.  
**Impact:** Spinner may remain visible after errors.  
**Fix:** Ensure `set_spinner(False)` in all terminal event paths.

---

## DeepAgents Reference Comparison

### DeepAgents Handles Differently:
| Feature | DeepAgents | NexusAgent Gap |
|---------|-----------|----------------|
| **State** | `DeepAgentState` with `DeltaChannel` reducer | Custom session state, no delta reducer |
| **Checkpointing** | `Checkpointer` (LangGraph) | SQLite + NATS, manual |
| **Human-in-loop** | `HumanInTheLoopMiddleware` + `interrupt_on` | Custom `approval_request` event |
| **Streaming** | `astream()` with `stream_mode="messages"` | Same, but wrapped in WebSocket |
| **Subagents** | `SubAgentMiddleware` (in-process) | NATS-based worker pool (distributed) |
| **Memory** | `MemoryMiddleware` (optional) | 4-layer hybrid system |
| **Filesystem** | `FilesystemMiddleware` + permissions | Custom tools + path jail |

### What NexusAgent Does That DeepAgents Doesn't:
- Multi-client architecture (TUI, CLI, Web, SDK)
- Persistent sessions with DB
- NATS-based distributed task orchestration
- Version negotiation / preflight
- Workspace-scoped memory isolation
- Dream cycle / compaction / provenance

---

## Recommended Priority Fixes

### Immediate (Blocking)
1. **Fix thread-local → contextvars** (agent.py, worker.py) — security boundary
2. **Fix SQLite connection leak** (graph.py) — resource exhaustion
3. **Fix blocking invoke in async** (session.py) — freezes TUI

### High (Stability)
4. **Bound event queue** (session.py) — OOM prevention
5. **Cancel heartbeat task on error** (session.py) — leak
6. **Explicit WS close on session close** (websocket.py) — dangling connections
7. **Fix working_dir URL encoding** (websocket.py) — workspace scoping

### Medium (Quality)
8. **Token exchange → JWT** (routes.py) — security
9. **Configurable allowed origins** (websocket.py) — deployability
10. **Rate limit WS upgrade** (routes.py) — DoS protection

### Low (Polish)
11. **Cancel auto-approve task** (streaming.py) — cleanup
12. **Fix spinner state on error** (streaming.py) — UX
13. **Version check UX** (websocket.py) — clarity
14. **Input queue race on quit** (app.py) — cleanup

---

## Test Coverage Gaps

| Area | Current Coverage | Gap |
|------|-----------------|-----|
| WebSocket auth flow | Partial (tests/test_auth.py) | No integration test for token exchange |
| WS reconnection logic | None | No test for exponential backoff |
| Session event streaming | Unit only | No E2E test with real TUI |
| Version negotiation | None | No test for mismatch handling |
| Workspace memory scoping | Unit (test_worker_workspace_scoping.py) | No WebSocket integration test |
| Approval flow | Partial | No test for auto-approve + interrupt |
| Compaction trigger | Unit | No E2E with WebSocket |

---

## Notes for External Audit

1. **Architecture is sound** — clear separation of concerns, proper async patterns mostly
2. **Critical bugs are known** — thread-local, SQLite leak, blocking invoke are documented
3. **DeepAgents used as library, not forked** — easier to upgrade, but custom middleware needed
4. **WebSocket protocol is simple but effective** — JSON events, good event taxonomy
5. **Memory system is a differentiator** — 4-layer with compaction/dream, not in DeepAgents
6. **Distributed workers via NATS** — unique vs DeepAgents' in-process subagents