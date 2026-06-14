# Forward Audit — NexusAgent Data Flow Analysis

**Date:** 2026-07-18  
**Auditor:** OWL (automated)  
**Scope:** All entry points (CLI, TUI, SDK, WebSocket, Web UI) through to outputs  
**Methodology:** AST-based structural analysis + full source read of 18 key files

---

## Executive Summary

NexusAgent has **5 entry points** that funnel into **2 core execution paths** (NATS-backed worker pool and direct agent invocation). The architecture is fundamentally sound but has **critical gaps in auth enforcement at 3 of 5 entry points**, **inconsistent error propagation**, and **several race conditions** in concurrent access patterns.

| Severity | Count | Categories |
|----------|-------|------------|
| 🔴 CRITICAL | 4 | Auth bypass, data loss, race condition |
| 🟠 HIGH | 6 | Missing validation, error swallowing, resource leak |
| 🟡 MEDIUM | 8 | Inconsistent patterns, weak defaults, missing limits |
| 🔵 LOW | 5 | Code quality, documentation gaps |

---

## 1. CLI ENTRY (`src/nexusagent/interfaces/cli.py`)

### Flow: `main` → `submit` / `run` / `session_cmd` → SDK or WorkerPool → output

#### 1.1 `submit` command (lines 93–130)

**Data In:**
- `task` (str) — Click argument, no validation (any string accepted)
- `skip_version_check` (bool) — flag to bypass preflight

**Transformations:**
1. Optional `preflight()` — HTTP GET to `/version` on server, checks semver compatibility
2. `sdk.submit_task({"description": task})` → NATS publish to `tasks.submit`

**Side Effects:**
- NATS publish (if server running)
- Log output to stderr

**Output:** Task ID string to stdout, or error to stderr

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 1.1.1 | 🟡 MEDIUM | **No input validation on `task`**: Empty strings, extremely long strings, and special characters are all accepted. Click's `argument` provides no constraints. |
| 1.1.2 | 🔴 CRITICAL | **No auth enforcement**: The CLI `submit` command calls `sdk.submit_task()` without any API key. The SDK's `submit_task` publishes directly to NATS without authentication. Anyone who can reach the NATS server can submit tasks. |
| 1.1.3 | 🟠 HIGH | **Error handling is string-based**: `except Exception as e` checks `"NATS" in str(type(e))` — fragile pattern that misses `nats.errors.Error` subclasses and fails on wrapped exceptions. |
| 1.1.4 | 🟡 MEDIUM | **Version check is non-fatal**: `preflight()` returns `True` even on version mismatch (only prints warning). This is documented but could lead to silent incompatibility. |

#### 1.2 `run` command (lines 146–192)

**Data In:**
- `task` (str) — description
- `working_dir` (str, default `"."`) — no path validation or jail
- `max_turns` (int, default 20) — no upper bound
- `wall_time` (float, default 1800.0) — no upper bound
- `memory_mode` (Choice: isolated/scoped/shared) — validated by Click
- `acceptance` (tuple, multiple) — no validation
- `model` (str, optional) — no validation of model name format
- `max_depth` (int, default 3) — no upper bound

**Transformations:**
1. Builds `TaskContract` from parameters
2. `worker_pool.spawn(contract, depth=0)` → creates `SubAgentHandle`
3. `handle.wait(timeout=wall_time + 60)` → polls for result

**Side Effects:**
- Agent execution: file reads/writes, shell commands, git operations
- NATS publishes (task + result)
- DB writes (task creation, status updates, result storage)
- File system mutations in `working_dir`

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 1.2.1 | 🔴 CRITICAL | **No path jail on `working_dir`**: The `working_dir` parameter is passed directly to the agent and used as `cwd` for shell commands. A malicious or erroneous value like `/` or `../../etc` could cause the agent to operate on arbitrary filesystem paths. The TUI sets workspace root via `set_workspace_root()` but the CLI does not. |
| 1.2.2 | 🟠 HIGH | **No upper bound on `max_turns`**: A user can pass `--max-turns 999999` which would cause the `WorkerPool._execute_bounded` loop (line 272) to run indefinitely if the agent doesn't reach a terminal state. |
| 1.2.3 | 🟠 HIGH | **No upper bound on `wall_time`**: Similarly, `---wall-time 999999` would set an extremely long timeout. The `handle.wait(timeout=wall_time + 60)` on line 184 would wait for that duration. |
| 1.2.4 | 🟡 MEDIUM | **Task ID is truncated user input**: `task_id=f"cli-{task[:20]}"` (line 157) — two different tasks with the same first 20 characters get the same ID, causing collisions in DB and NATS KV. |
| 1.2.5 | 🟡 MEDIUM | **No validation of `model` format**: The model string is passed directly to the LLM provider. An invalid model name will only fail at LLM invocation time, wasting a turn cycle. |

#### 1.3 `session_cmd` command (lines 202–278)

**Data In:**
- `action` (Choice: list/resume/fork/rename/delete) — validated by Click
- `session_id` (str, optional) — no format validation
- `new_id` (str, optional) — no format validation
- `working_dir` (str, optional) — no validation
- `status` (Choice: active/idle/closed) — validated by Click
- `limit` (int, default 20) — no upper bound

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 1.3.1 | 🟡 MEDIUM | **No session ID format validation**: Any string is accepted as `session_id`. The system uses UUID-based IDs, but the CLI doesn't enforce this. Invalid IDs will silently fail (return "not found"). |
| 1.3.2 | 🟠 HIGH | **Fork/rename have no confirmation**: Destructive operations (`delete`, `rename`, `fork`) execute immediately without confirmation prompt. A typo could destroy session data. |
| 1.3.3 | 🔵 LOW | **No auth on session operations**: Session data in the DB is accessible without authentication. Any process with DB access can read all session history. |

---

## 2. TUI ENTRY (`src/nexusagent/interfaces/tui.py`)

### Flow: `NexusApp` → WebSocket → server `session_websocket` → `Session.send()` → agent → event stream

#### 2.1 WebSocket Connection (lines 284–364)

**Data In:**
- `session_id` (str) — auto-generated as `uuid.uuid4()[:8]`
- `api_key` (str) — from `settings.client.api_key`
- Server version check via HTTP GET to `/version`

**Transformations:**
1. Pre-connect version check (`_check_server_version`) — non-blocking
2. WebSocket connect with `Authorization: Bearer {api_key}` header
3. Exponential backoff retry (6 attempts, base 1s)

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 2.1.1 | 🟠 HIGH | **API key sent in WebSocket `Authorization` header over potentially non-TLS connection**: The TUI connects to `ws://127.0.0.1:{port}` (line 286). While localhost-only, the API key is transmitted in plaintext. If the server is ever exposed over a network, credentials are leaked. |
| 2.1.2 | 🟡 MEDIUM | **Version check is fire-and-forget**: `_check_server_version()` (line 292) runs before connection but its result only produces a UI message. The WebSocket connects regardless of version mismatch. |
| 2.1.3 | 🔵 LOW | **No message size limit on WebSocket**: The TUI's `receive_events()` (line 317) processes `json.loads(raw)` on incoming messages with no size check. A malicious or compromised server could send multi-megabyte JSON to exhaust memory. |

#### 2.2 User Input Handling (lines 702–726)

**Data In:**
- Text from `ChatInput` widget
- Slash commands (e.g., `/help`, `/compact`, `/skill`)

**Transformations:**
1. Strip whitespace
2. Route slash commands to `_handle_slash_command()`
3. If busy, queue in `_pending_inputs` (FIFO)
4. Otherwise, put on `_input_queue` (asyncio.Queue)
5. WebSocket sends `{"type": "user_input", "content": msg}`

**Side Effects:**
- User message widget mounted
- Status bar updated
- Message sent over WebSocket to server

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 2.2.1 | 🟠 HIGH | **No input sanitization**: User text is sent as-is to the server. While the agent system prompt provides guidance, there's no filtering of control characters, null bytes, or extremely long messages. |
| 2.2.2 | 🟡 MEDIUM | **Queue has no size limit**: `_pending_inputs` (line 141) is a plain `list` with no max size. In a busy session, if the agent is slow, messages accumulate unboundedly in memory. |
| 2.2.3 | 🟡 MEDIUM | **Slash command injection**: The `/compact` command (line 571) sends `{"type": "compact"}` over WebSocket. There's no validation that this is a legitimate user action — a crafted message could trigger compaction. |
| 2.2.4 | 🔵 LOW | **`/undo` and `/redo` are no-ops**: Commands are sent to the server (lines 591-597) but the server's WebSocket handler doesn't handle `type: "undo"` or `type: "redo"`, so they silently do nothing. |

#### 2.3 Event Handling (lines 367–489)

**Data In:**
- JSON events from WebSocket: `session_status`, `thinking`, `tool_call`, `tool_result`, `tool_error`, `approval_request`, `response_chunk`, `response`, `error`, `session_closed`

**Transformations:**
1. Parse JSON
2. Route by `type` field
3. Mount appropriate widget to message container

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 2.3.1 | 🟠 HIGH | **Silent JSON parse failure**: `json.JSONDecodeError` is caught (line 320) and the message is silently skipped. If the server sends malformed JSON, the TUI gives no indication. |
| 2.3.2 | 🟡 MEDIUM | **No event type validation**: Unknown event types are silently ignored. While not harmful, this makes debugging protocol issues difficult. |
| 2.3.3 | 🟡 MEDIUM | **Auto-approve races with approval modal**: When `_auto_approve` is enabled (line 401), the TUI sends approval immediately. But if an `approval_request` event arrives simultaneously, both the auto-approval and the modal could approve/deny the same call. |

---

## 3. SDK ENTRY (`src/nexusagent/server/sdk.py`)

### Flow: `NexusSDK.submit_task()` → NATS publish → worker → NATS KV result → `SDK.get_result()`

#### 3.1 `submit_task` (lines 62–73)

**Data In:**
- `task_data` (dict) — arbitrary keys, only `description` is required by `TaskSchema`

**Transformations:**
1. Copy dict (avoids caller mutation)
2. Extract or generate `task_id`
3. Validate through `TaskSchema` (Pydantic)
4. Publish to NATS subject `tasks.submit`

**Side Effects:**
- NATS publish

**Output:** `task_id` (str)

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 3.1.1 | 🔴 CRITICAL | **No auth on SDK methods**: The SDK is a client-side library with no authentication. Anyone who can instantiate `NexusSDK()` and reach the NATS server can submit tasks, cancel tasks, and read results. The SDK is used by both the server (trusted) and CLI (untrusted) — there's no distinction. |
| 3.1.2 | 🟠 HIGH | **Task ID collision**: If `task_data` contains an `id` key, it's used as-is (line 68). Two callers could submit tasks with the same ID, causing the second to overwrite the first in NATS KV. |
| 3.1.3 | 🟡 MEDIUM | **No rate limiting**: `submit_task` and `submit_batch` have no rate limiting. A caller can flood NATS with tasks. |
| 3.1.4 | 🟡 MEDIUM | **`submit_batch` is sequential**: Line 162-164 submits tasks one at a time instead of using NATS batch publish. For large batches, this is unnecessarily slow. |

#### 3.2 `get_result` (lines 84–98)

**Data In:**
- `task_id` (str)

**Transformations:**
1. Connect to NATS (if not connected)
2. Fetch from JetStream KV `nexus_results` bucket
3. Parse JSON, validate through `ResultSchema`

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 3.2.1 | 🟠 HIGH | **No result expiration**: Results stored in NATS KV have no TTL. Over time, the KV bucket grows unboundedly. Old results from completed tasks accumulate forever. |
| 3.2.2 | 🟡 MEDIUM | **Polling in `wait_for_result`**: Line 139-145 polls every `poll_interval` seconds. For a 300s timeout with 1s interval, this is 300 NATS KV reads. No exponential backoff or watch/notify mechanism. |

#### 3.3 `cancel_task` / `retry_task` (lines 113–127)

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 3.3.1 | 🟠 HIGH | **Cancel is DB-only, not NATS**: `cancel_task` (line 117) only updates the DB status. It does not publish a cancellation message to NATS. A worker that has already picked up the task will continue executing. |
| 3.3.2 | 🟡 MEDIUM | **Retry description is hardcoded**: Line 126 always submits `{"description": "retried", "priority": 1}`. The original task description is lost. |

---

## 4. WEBSOCKET ENTRY (`src/nexusagent/server/server.py` → `session_websocket`)

### Flow: WebSocket accept → `SessionManager.get_or_create` → `Session.send()` → agent → event queue → WebSocket send

#### 4.1 Connection Handling (lines 270–377)

**Data In:**
- `session_id` (str) — URL path parameter, no format validation
- `api_key` (str) — query parameter `?api_key=xxx`
- Incoming messages: `user_input`, `approval`, `interrupt`, `list_sessions`, `compact`, `close`

**Transformations:**
1. API key verification via `verify_api_key()`
2. WebSocket accept
3. Create `Agent(role="full", policy="permissive")`
4. Create or retrieve `Session` via `SessionManager`
5. Set workspace root via `set_workspace_root(session.working_dir)`
6. Two concurrent tasks: `send_events()` and `receive_messages()`

**Side Effects:**
- Session created/cached in `SessionManager`
- Agent execution: file I/O, shell commands, git ops
- DB writes (messages, session status)
- Memory system writes (hybrid memory)

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 4.1.1 | 🟠 HIGH | **Agent is always `role="full"` with `policy="permissive"`**: Line 298 hardcodes these values. The WebSocket endpoint has no way to request a restricted agent. Every interactive session has full tool access. |
| 4.1.2 | 🟠 HIGH | **No session ID validation**: `session_id` from the URL path (line 273) is used as-is. Any string is valid. This means path traversal characters (`../`) could be used as session IDs, though they're only used as dictionary keys so there's no direct exploit. |
| 4.1.3 | 🟠 HIGH | **No message validation on incoming WebSocket messages**: Line 321 does `msg.get("type")` but doesn't validate that required fields exist. For example, `approval` messages (line 332) access `msg["call_id"]` without checking if it exists — a `KeyError` would crash the `receive_messages` coroutine and disconnect the client. |
| 4.1.4 | 🟡 MEDIUM | **`list_sessions` returns all sessions**: Line 338 calls `session_repo.list_sessions(limit=20)` with no filtering by ownership. Any authenticated user can see all session metadata. |
| 4.1.5 | 🟡 MEDIUM | **No rate limiting on WebSocket messages**: A client can send unlimited `user_input` messages. The server processes them sequentially (via `Session.send`), but there's no backpressure mechanism. |
| 4.1.6 | 🔵 LOW | **`compact` message exposes internal state**: Line 353 returns the first 200 characters of compaction context, which could leak sensitive information from the conversation history. |

#### 4.2 HTTP Endpoints (lines 93–264)

**Auth Enforcement:**

| Endpoint | Auth | Issue |
|----------|------|-------|
| `POST /tasks` | ✅ `verify_api_key` | — |
| `GET /tasks/{id}/status` | ✅ `verify_api_key` | — |
| `GET /tasks/{id}/result` | ✅ `verify_api_key` | — |
| `GET /health` | ❌ None | **Exposes server status to unauthenticated requests** |
| `GET /version` | ❌ None | **Exposes version info to unauthenticated requests** |
| `GET /tasks` | ✅ `verify_api_key` | — |
| `POST /tasks/{id}/cancel` | ✅ `verify_api_key` | — |
| `POST /tasks/{id}/retry` | ✅ `verify_api_key` | — |
| `GET /workers` | ✅ `verify_api_key` | — |
| `GET /tools` | ✅ `verify_api_key` | — |
| `WS /sessions/{id}/ws` | ✅ API key in query param | — |

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 4.2.1 | 🟡 MEDIUM | **`/health` and `/version` are unauthenticated**: These endpoints expose server version and NATS connection status. While not directly exploitable, they aid reconnaissance. |
| 4.2.2 | 🟠 HIGH | **No pagination limit enforcement**: `list_tasks` (line 179) accepts `limit` and `offset` as query params with no maximum. A request with `limit=1000000` could exhaust memory. |
| 4.2.3 | 🟡 MEDIUM | **CORS allows credentials with specific origins**: Lines 72-84 correctly restrict origins to localhost and use `allow_credentials=True`. This is well-implemented but would break if deployed to a remote server. |

---

## 5. WEB UI ENTRY (`src/nexusagent/interfaces/web_ui.py`)

### Flow: Gradio `handle_submit` → `NexusSDK.submit_task()` → NATS → result

#### 5.1 `handle_submit` (lines 13–32)

**Data In:**
- `text` (str) — from Gradio Textbox, no validation
- `sdk` (NexusSDK | None) — optional dependency injection

**Transformations:**
1. Check for empty text
2. Generate task ID: `str(uuid.uuid4())[:8]`
3. `sdk.submit_task({"id": task_id, "description": text})`

**Side Effects:**
- NATS publish

**Output:** `(log_message, status)` tuple for Gradio UI

**Findings:**

| # | Severity | Finding |
|---|----------|---------|
| 5.1.1 | 🔴 CRITICAL | **No authentication whatsoever**: The Web UI has no API key, no auth middleware, no session management. Anyone who can reach the Gradio port (7860) can submit tasks. The `NexusSDK()` is instantiated without credentials (line 16). |
| 5.1.2 | 🟠 HIGH | **No input validation**: The `text` input (line 13) is checked for emptiness but has no length limit, character filtering, or sanitization. |
| 5.1.3 | 🟠 HIGH | **No CSRF protection**: Gradio's `submit_btn.click()` (line 74) has no CSRF token. If the Gradio UI is exposed over a network, cross-site request forgery is possible. |
| 5.1.4 | 🟡 MEDIUM | **Task ID is truncated UUID**: `str(uuid.uuid4())[:8]` (line 21) gives only 16^8 ≈ 4.3 billion possible IDs. While unlikely, collisions are possible with high throughput. |
| 5.1.5 | 🟡 MEDIUM | **No result retrieval**: The Web UI submits tasks but never retrieves results. The `handle_submit` function only confirms submission. There's no polling or WebSocket for results. |
| 5.1.6 | 🟡 MEDIUM | **Gradio launched on `0.0.0.0`**: Line 86 binds to all interfaces, exposing the UI to the network. Combined with no auth, this is a significant exposure. |

---

## 6. CROSS-CUTTING CONCERNS

### 6.1 Auth Enforcement Summary

| Entry Point | Auth Mechanism | Effective? |
|-------------|---------------|------------|
| CLI `submit` | None | ❌ No auth |
| CLI `run` | None | ❌ No auth |
| CLI `session` | None | ❌ No auth |
| TUI | API key in WebSocket header | ⚠️ Partial (localhost only) |
| SDK | None | ❌ No auth (library) |
| Server HTTP | `X-API-Key` header | ✅ Enforced on most endpoints |
| Server WebSocket | API key in query param | ✅ Enforced |
| Web UI | None | ❌ No auth |

**Root Cause:** The SDK (`NexusSDK`) is designed as a client library without auth. The server's HTTP endpoints enforce auth via `verify_api_key`, but the SDK's direct NATS access bypasses this entirely. The CLI and Web UI use the SDK directly, inheriting this gap.

### 6.2 Data Integrity

| # | Severity | Finding |
|---|----------|---------|
| 6.2.1 | 🟠 HIGH | **NATS at-most-once delivery**: The `bus.publish()` method (bus.py line 84-92) uses `nc.publish()` which is fire-and-forget with no acknowledgment. If NATS is partitioned, tasks can be silently lost. |
| 6.2.2 | 🟠 HIGH | **No transaction boundary between DB and NATS**: In `NexusWorker.handle_task()` (worker.py lines 135-175), the DB update and NATS publish are separate operations. If the process crashes between them, the DB shows "processing" but no worker picks up the task. The heartbeat mechanism (line 106-119) mitigates but doesn't eliminate this. |
| 6.2.3 | 🟡 MEDIUM | **Event queue overflow**: `Session._event_queue` (session.py line 197) has `maxsize=1000`. If the TUI is slow to process events (e.g., during heavy tool output), `put_nowait()` (line 597) will raise `asyncio.QueueFull`. This exception is not caught and will crash the session. |
| 6.2.4 | 🟡 MEDIUM | **No deduplication on NATS retry**: If NATS redelivers a message (e.g., before acknowledgment timeout), the worker will process the same task twice. The `create_task` call uses `INSERT OR IGNORE` semantics (implied by the repo), but the agent will execute twice. |

### 6.3 Race Conditions

| # | Severity | Finding |
|---|----------|---------|
| 6.3.1 | 🔴 CRITICAL | **TOCTOU in `SessionManager.get_or_create`**: Lines 627-635 have a check-then-act pattern. The fast path (line 627) reads without lock, then acquires lock and double-checks. However, between the first check and the lock acquisition, another coroutine could create the session. The double-check on line 634 mitigates this, but the `Session()` constructor (line 642) runs inside the lock, meaning session creation blocks all other session lookups. |
| 6.3.2 | 🟠 HIGH | **WorkerPool semaphore + dict race**: `WorkerPool._run_worker` (line 237) acquires the semaphore but `self._active` dict modifications (lines 231, 263) happen outside the lock. `list_active()` (line 307) reads the dict without synchronization. In async context this is usually safe due to the GIL, but `self._active.pop()` on line 263 can interleave with `self._active[worker_id] = handle` on line 231. |
| 6.3.3 | 🟡 MEDIUM | **Shared mutable bus singleton**: `get_bus()` (bus.py line 161) returns a module-level global. Multiple test runs or concurrent event loops can share the same bus instance. The `set_bus()` function exists for testing but is not used in production. |
| 6.3.4 | 🟡 MEDIUM | **Thread-local policy context in async code**: `set_policy_context()` (policy.py line 30) uses `contextvars.ContextVar`, which is async-safe. However, `run_agent_task()` (agent.py line 155) is called via `loop.run_in_executor()` (worker.py line 53) in a thread pool. The context variable set in the async context may not propagate to the thread, causing policy checks to use default values. |

### 6.4 Error Handling Patterns

| # | Severity | Finding |
|---|----------|---------|
| 6.4.1 | 🟠 HIGH | **Inconsistent error response format**: The server returns `HTTPException` with `detail=str(e)` (server.py line 129), but the SDK returns `None` on failure (sdk.py line 96), and the CLI prints raw exception messages. There's no standardized error schema. |
| 6.4.2 | 🟠 HIGH | **Error swallowing in session**: `Session.send()` (session.py lines 336-339, 416-419) catches DB write failures and logs warnings but continues execution. If the DB is down, messages are processed but not persisted — data loss on restart. |
| 6.4.3 | 🟡 MEDIUM | **Worker error recovery is best-effort**: `NexusWorker.handle_task()` (worker.py lines 179-201) catches exceptions and tries to mark the task as failed, but if the error occurs during JSON parsing (line 127), `msg.data` may be invalid and the inner `json.loads` on line 183 will also fail, leaving the task stuck in "processing" state. |

---

## 7. RECOMMENDATIONS (Prioritized)

### P0 — Critical (fix immediately)

1. **Add auth to SDK NATS path**: Either authenticate NATS connections or route SDK calls through the HTTP API where `verify_api_key` is enforced.
2. **Add auth to Web UI**: Require API key for Gradio routes, or bind to localhost only.
3. **Fix TOCTOU in SessionManager**: Use a per-session-id lock instead of a global lock to avoid blocking all session creation.
4. **Add path jail for CLI `working_dir`**: Validate and restrict working directory to prevent filesystem traversal.

### P1 — High (fix before next release)

5. **Add input validation layer**: Validate task descriptions (length, characters), model names, and session IDs at every entry point.
6. **Fix cancel to propagate via NATS**: Publish a cancellation message so in-flight workers can stop.
7. **Add pagination limits**: Enforce maximum `limit` on all list endpoints.
8. **Fix WebSocket message validation**: Check required fields before accessing them to prevent `KeyError` crashes.
9. **Add result TTL to NATS KV**: Expire old results to prevent unbounded growth.
10. **Standardize error responses**: Define an error schema and use it across all entry points.

### P2 — Medium (fix in next sprint)

11. **Add rate limiting**: On SDK `submit_task`, HTTP endpoints, and WebSocket messages.
12. **Fix task ID generation**: Use full UUIDs instead of truncated strings.
13. **Add message size limits**: On WebSocket receive and Gradio input.
14. **Handle QueueFull in Session._enqueue**: Catch and log instead of crashing.
15. **Fix policy context propagation to threads**: Ensure `contextvars` propagate through `run_in_executor`.

---

## Appendix A: Data Flow Diagrams

### CLI Submit Flow
```
User → CLI submit(task) → preflight() → HTTP GET /version
                                    ↓ (warn on mismatch)
                             sdk.submit_task({description: task})
                                    ↓
                             TaskSchema validation (Pydantic)
                                    ↓
                             NATS publish → tasks.submit
                                    ↓
                             NexusWorker.handle_task()
                                    ↓
                             DB create_task → status=PROCESSING
                                    ↓
                             _run_agent_task() → Agent.__call__()
                                    ↓
                             DB save_result → status=COMPLETED
                                    ↓
                             NATS KV put_result
```

### TUI WebSocket Flow
```
User → ChatInput → on_chat_input_submitted()
                        ↓
                  _input_queue.put(message)
                        ↓
                  WebSocket send → {"type": "user_input", "content": ...}
                        ↓
                  Server session_websocket()
                        ↓
                  SessionManager.get_or_create()
                        ↓
                  Session.send(message)
                        ↓
                  DB add_message (user)
                        ↓
                  Agent.invoke({messages: [...]})
                        ↓
                  Event queue → WebSocket send_json()
                        ↓
                  TUI _handle_event() → widget mount
```

### Web UI Flow
```
User → Gradio Textbox → handle_submit(text)
                              ↓
                        NexusSDK() → submit_task({id, description})
                              ↓
                        NATS publish → tasks.submit
                              ↓
                        (No result retrieval — fire and forget)
```

---

## Appendix B: Files Analyzed

| File | Lines | Role |
|------|-------|------|
| `interfaces/cli.py` | 332 | CLI entry point |
| `interfaces/tui.py` | 787 | TUI entry point |
| `interfaces/web_ui.py` | 90 | Web UI entry point |
| `server/server.py` | 402 | HTTP + WebSocket server |
| `server/sdk.py` | 220 | SDK client library |
| `core/agent.py` | 178 | Agent creation + execution |
| `core/session.py` | 677 | Session management |
| `core/worker.py` | 311 | Worker pool + task execution |
| `core/subagent.py` | ~189 | Sub-agent handle |
| `infrastructure/config.py` | 193 | Configuration loading |
| `infrastructure/auth.py` | 133 | Fernet keystore |
| `infrastructure/api_auth.py` | 57 | API key verification |
| `infrastructure/bus.py` | 172 | NATS JetStream bus |
| `infrastructure/db/` | ~200 | Database layer |
| `llm/models.py` | ~178 | Pydantic schemas |
| `hooks/__init__.py` | ~176 | Hook system |
| `tools/registry/policy.py` | 281 | Policy enforcement |
