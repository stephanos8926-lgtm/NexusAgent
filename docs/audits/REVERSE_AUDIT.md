# REVERSE AUDIT — NexusAgent

**Date:** 2026-07-18  
**Auditor:** OWL (Lucien)  
**Scope:** All output types traced back to entry points  
**Codebase:** src/nexusagent/ (82 files, ~13.6K lines)

---

## Methodology

This audit starts from every observable output (HTTP responses, WebSocket messages, log lines, DB records, TUI-rendered text, NATS messages, files on disk) and traces backward through the transformation chain to the original data source. For each output we document:

- **Source of truth** — where the data actually originates
- **Transformation chain** — every mutation between source and output
- **Failure modes** — what happens when any step fails
- **Data consistency** — whether output can diverge from ground truth

---

## 1. HTTP API RESPONSES

### 1.1 `POST /tasks` — Task Submission

**Output:** `{"task_id": "<uuid>", "status": "submitted"}`

| Aspect | Detail |
|--------|--------|
| **Source of truth** | Client-supplied JSON body (`SubmitTaskRequest`) |
| **Transformation chain** | `SubmitTaskRequest` Pydantic model → `uuid4()` for task_id → `task_repo.create_task()` (DB insert) → `sdk.submit_task()` (NATS publish) → JSON response |
| **Failure modes** | DB insert failure → 500 with `str(e)` (line 129). NATS publish failure → exception propagates → 500. DB insert succeeds but NATS publish fails → **orphaned task record** in DB with status "pending" that no worker will ever pick up |
| **Data consistency** | ⚠️ **Race condition**: task is inserted into DB, then published to NATS. If the server crashes between these two operations, the task exists in DB but is never processed. The `task_repo.create_task()` is idempotent (checks for existing ID), but the NATS publish in `sdk.submit_task()` is not — retrying the HTTP call creates a new UUID, so the original orphaned record stays orphaned |

**Sensitive data exposure:** The error path at line 129 returns `str(e)` directly to the client. If the DB path contains credentials or the NATS URL contains tokens, these leak in the error response.

### 1.2 `GET /tasks/{task_id}/status`

**Output:** `{"task_id": "<id>", "status": "<status_str>"}`

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `task_repo.get_task_status()` → `TaskModel.status` column in SQLite |
| **Transformation chain** | SQLAlchemy query → `task.status` string → wrapped in dict → JSON response |
| **Failure modes** | Task not found → returns `{"task_id": "...", "status": None}`. This is **not an error** — the client receives a 200 with `null` status, which is ambiguous (task doesn't exist vs. status not yet set) |
| **Data consistency** | Status is a free-text `String` column with no DB-level constraint. The `TaskStatus` StrEnum is only enforced in Python. Direct DB writes or bugs could insert invalid status strings |

### 1.3 `GET /tasks/{task_id}/result`

**Output:** `ResultSchema` JSON or 404

| Aspect | Detail |
|--------|--------|
| **Source of truth** | NATS JetStream KV store (`nexus_results` bucket) |
| **Transformation chain** | `bus.get_result(task_id)` → KV lookup → JSON decode → `ResultSchema(**data)` validation → JSON response |
| **Failure modes** | KV get returns None → 404. KV get times out (5s) → returns None → 404 (indistinguishable from "not found"). JSON decode failure → exception → 500 (unhandled). `ResultSchema` validation failure → exception → 500 (unhandled) |
| **Data consistency** | ⚠️ **Dual-write problem**: results are written to both the `ResultModel` table (DB) and the KV store (NATS). The API reads from KV only. If KV write succeeds but DB write fails (or vice versa), the two sources diverge. The DB `ResultModel` is essentially orphaned data |

### 1.4 `GET /health`

**Output:** `{"status": "ok", "version": "...", "nats": "connected"|"disconnected"}`

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `version.py` (importlib.metadata), `bus.nc` connection state |
| **Failure modes** | No failure modes — this is a simple read. However, `bus.nc` being truthy doesn't guarantee NATS is actually reachable (connection could be stale) |
| **Data consistency** | ⚠️ Reports "connected" even if NATS connection is in a degraded state (reconnecting, half-open). The health check doesn't verify JetStream is functional |

### 1.5 `GET /version`

**Output:** `{"version": "...", "minClient": "...", "server": "nexus-server", "uptime": <float>, "nats": "..."}`

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `version.py`, `time.monotonic()` |
| **Data consistency** | `uptime` uses `time.monotonic()` which is correct for elapsed time. No issues |

### 1.6 `GET /tasks` — Task Listing

**Output:** `{"tasks": [...], "count": N}`

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `task_repo.list_tasks()` → `TaskModel` table |
| **Transformation chain** | SQLAlchemy query → ORM objects → dict comprehension with `.isoformat()` for datetimes → JSON |
| **Failure modes** | `created_at` or `updated_at` is None → `isoformat()` returns `None` string (handled with ternary). `metadata_json` is None → returns `None` instead of `{}` (no default handling in the dict comprehension) |
| **Data consistency** | ⚠️ `metadata` field in response comes from `metadata_json` column. If the column contains invalid JSON (manually edited), the entire endpoint fails with an unhandled exception |

### 1.7 `POST /tasks/{task_id}/cancel`

**Output:** `{"task_id": "...", "status": "cancelled"}` or 400

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `task_repo.cancel_task()` — checks current status, sets to FAILED |
| **Failure modes** | Task already completed/failed → 400. Task not found → 400. **The status is set to FAILED, not CANCELLED** — the response says "cancelled" but the DB says "failed". This is a semantic inconsistency |
| **Data consistency** | ⚠️ **Naming mismatch**: response claims "cancelled" but DB status is `TaskStatus.Failed`. Any downstream system reading the DB will see "failed", not "cancelled" |

### 1.8 `POST /tasks/{task_id}/retry`

**Output:** `{"task_id": "...", "status": "re-queued"}` or 400

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `task_repo.retry_task()` — resets status to PENDING |
| **Failure modes** | Task not in FAILED state → 400. The retry re-publishes to NATS with **hardcoded description "retried"** (line 214), losing the original task description |
| **Data consistency** | ⚠️ **Data loss on retry**: The retried task's description is always "retried" regardless of the original task. The original description is not fetched from the DB and re-attached |

### 1.9 `GET /workers`

**Output:** Worker status with circuit breaker state

| Aspect | Detail |
|--------|--------|
| **Source of truth** | Module-level `_agent_breaker` and `_nats_breaker` CircuitBreaker instances |
| **Data consistency** | Reports `"status": "running"` as a hardcoded string — doesn't actually check if the worker task is alive. If the worker task crashed, this still reports "running" |

### 1.10 `GET /tools`

**Output:** Tools grouped by category

| Aspect | Detail |
|--------|--------|
| **Source of truth** | `_REGISTRY` dict in `tools/registry/core.py` |
| **Transformation chain** | `list_all_tools()` → iterate `_REGISTRY.values()` → group by `t.category` → dict with name/description/parameters |
| **Failure modes** | `t.parameters` could be None or missing → included as-is in JSON. No validation on the output shape |
| **Data consistency** | The `parameters` field comes from the tool registration and is not validated against the actual function signature. Stale registrations could advertise non-existent parameters |

---

## 2. WEBSOCKET SESSION MESSAGES

### 2.1 Event Stream (Server → Client)

All WebSocket events flow through `Session._enqueue()` → `asyncio.Queue` → `event_stream()` generator → `websocket.send_json()`.

**Event types and their origins:**

| Event Type | Origin | Transformation |
|------------|--------|----------------|
| `session_status` | `session.status` string | Direct passthrough |
| `thinking` | `ThinkingEvent(content="Processing...")` | Hardcoded string, not from LLM |
| `tool_call` | `Session._handle_message_token()` | Extracts `tool_call_chunks` from `AIMessageChunk`, deduplicates by `call_id` |
| `tool_result` | `Session._handle_message_token()` or `_handle_update()` | Extracts from `ToolMessage.content`, deduplicates by `call_id` |
| `response_chunk` | `Session._handle_message_token()` | Accumulates text from `AIMessageChunk.content` |
| `response` | `Session.send()` → `_extract_agent_response()` | Complex extraction from agent result (see §2.2) |
| `error` | `Session.send()` exception handler or session status check | `str(exc)` or hardcoded "Session is not active" |
| `session_closed` | `Session.close()` | `{"type": "session_closed"}` — no payload |
| `session_list` | `session_repo.list_sessions()` | DB → dict comprehension → JSON |
| `compact_result` | `session.pre_compaction_flush()` | Summary truncated to 200 chars |

### 2.2 `_extract_agent_response()` — The Critical Output Transformer

This function (session.py lines 30-71) is the **single most important output transformer** in the codebase. It converts the raw agent result into the string that becomes the `response` event.

**Transformation chain:**
```
Agent result (dict/list/str/BaseMessage)
  → If dict with "messages": iterate reversed, find last non-SystemMessage
    → If content is list: recurse
    → Return content or str(msg)
  → If dict with "response"/"result"/"content": return str(value)
  → If dict: return str(dict)  ← ⚠️ fallback
  → If list of dicts: extract "text" or "thinking" blocks
  → If list of other: str() each
  → If str: return as-is
  → Final fallback: str(result)
```

**Failure modes:**
- **Empty messages list** → returns `"No messages in response"` — this is a string, not an error, so the TUI renders it as a valid response
- **Content is empty string** → returns `str(msg)` which could be a LangChain message representation, not the actual content
- **Nested list content** → recurses correctly but could hit Python's recursion limit on deeply nested structures
- **Dict with no recognized keys** → returns `str(result)` which is the Python repr — this would look like `{'key': 'value'}` in the TUI, not a user-friendly message

### 2.3 WebSocket Input (Client → Server)

| Message Type | Handler | Validation |
|-------------|---------|------------|
| `user_input` | `session.send(content, images)` | `content` defaults to `""` if missing. `images` defaults to `[]`. No content-length validation |
| `approval` | `session.approve(call_id, approved)` | `approved` defaults to `False`. No validation that `call_id` is pending |
| `interrupt` | `session.interrupt()` | Sets `_cancel_flag = True` — but this is only checked AFTER the agent call completes, not during streaming |
| `list_sessions` | `session_repo.list_sessions(limit=20)` | Hardcoded limit of 20, ignores client's requested limit |
| `compact` | `session.pre_compaction_flush()` | No validation — triggers compaction even if not needed |
| `close` | `session.close()` | Clean shutdown |

**⚠️ Interrupt latency:** The `_cancel_flag` is set immediately, but it's only checked at line 401-402 AFTER `agent()` returns. During a long-running agent call (especially with streaming), the interrupt has no effect until the call completes. The WebSocket `receive_messages()` loop continues running, but the `send_events()` loop is blocked waiting for the agent.

---

## 3. TUI RENDERING

### 3.1 Event-to-Widget Pipeline

```
WebSocket JSON → _handle_event() → Widget.mount() → Textual render
```

**Data transformations in `_handle_event()`:**

1. **`tool_call` event**: Args dict → `format_arg_value()` → `truncate(60)` → joined as `k=v, k=v` string. If args is not a dict, truncated to 80 chars. **⚠️ Truncation at 60 chars per value means long file paths or code snippets are silently cut off in the TUI**

2. **`tool_result` event**: Output string → `ToolCallMessage.update_output()` → stored as-is. Rendering truncates at 10,000 chars with a truncation notice. **⚠️ The 10K char limit is in the widget's `render()` method, not enforced at the event level — the full output is stored in memory even if not displayed**

3. **`response_chunk` event**: Content → `AssistantMessage.append_token()` → accumulated in widget. **⚠️ No limit on accumulated token length — a very long response will consume unbounded memory in the widget**

4. **`response` event**: Content → `render_markdown()` → RichLog markup. Code blocks > 20 lines are truncated. **⚠️ The markdown renderer uses regex-based parsing, not a proper markdown parser — nested markdown (bold inside italic, etc.) renders incorrectly**

### 3.2 `render_markdown()` — Data Loss Analysis

The regex-based renderer (tui_formatters.py lines 22-63):

- **Code blocks**: Extracted first, replaced with placeholders, then restored. If the placeholder string `__CODE_BLOCK_N__` appears in user text, it will be **silently replaced with code block content** from a different block
- **Inline code**: Replaced with `[reverse]...[/reverse]` — if the code contains backticks, the regex stops at the first closing backtick
- **Bold/italic**: Simple regex — `**bold**` inside a code block will still be processed (code block extraction happens first, but the restored dim text still contains the `[b]` tags)
- **No escaping of existing Rich markup**: If agent output contains `[bold]` or `[dim]`, it will be interpreted as Rich markup. The `_escape()` function only escapes `[` and `]` for non-markup text, but the markdown rendering happens before escaping

### 3.3 `format_tool_result_for_display()` — Truncation Chain

Tool output passes through multiple truncation layers:

1. `format_tool_result_for_display()` dispatches to per-tool formatters
2. Shell output: 15 lines max, then `+N more lines`
3. File read: 12 lines max, then `+N more lines`
4. Generic JSON: 6 keys max, 120 chars per value, 5 list items max
5. `truncate_output()`: 400 chars head/tail split
6. `ToolCallMessage._truncate_output()`: 300 chars
7. `ToolCallMessage.render()`: 10,000 chars absolute max

**⚠️ A tool producing 100KB of output will be truncated at every layer, but the full 100KB is stored in the widget's `_output` attribute. Memory is not freed.**

### 3.4 Queue Management

The TUI maintains an `_input_queue` (asyncio.Queue) and `_pending_inputs` (list). When the user sends a message while the agent is busy:

1. Message is appended to `_pending_inputs`
2. When the current response completes, `_process_next_in_queue()` pops the first item
3. A new `asyncio.create_task(self._input_queue.put(next_msg))` is created (line 684)

**⚠️ The `asyncio.create_task()` call at line 684 has a `# noqa: RUF006` suppression — the task is fire-and-forget with no error handling. If the queue is full or the WebSocket is closed, the task fails silently.**

---

## 4. LOG OUTPUT

### 4.1 Logging Configuration

Configured in `server/server.py` line 22-24:
```python
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
```

**⚠️ `logging.basicConfig()` is called at module import time in `server.py`. If any other module calls `basicConfig()` first (e.g., during import), this configuration is silently ignored.**

### 4.2 Sensitive Data in Logs

| Location | What's logged | Risk |
|----------|---------------|------|
| `bus.py:43` | NATS connection URL | May contain credentials in URL |
| `bus.py:79` | NATS subscription errors | Low |
| `llm.py:66` | Provider and model name | Low |
| `llm.py:93,124` | Full API error messages | **May contain API keys in error responses** |
| `worker.py:130` | Task ID and description | Task descriptions may contain sensitive info |
| `worker.py:180` | Full exception with traceback | **May contain file paths, code snippets** |
| `session.py:432` | Agent invocation failure with traceback | **Full exception chain** |
| `config.py:128` | Config file load failure | May contain file path |
| `auth.py:114` | Decryption failure type only | Low — doesn't log the key |

### 4.3 Log Volume

The retry decorators (`retry_with_backoff`) log a warning on every retry attempt. With 3 attempts and multiple NATS operations, a single task submission can generate 6+ warning logs. The circuit breaker logs on every state transition.

**⚠️ No rate limiting or sampling on log output — a failing service will generate unbounded log volume.**

---

## 5. DATABASE STATE

### 5.1 Schema

Four tables: `tasks`, `results`, `sessions`, `messages`.

**Schema drift risks:**
- `TaskModel.status` is a free-text `String` column — no CHECK constraint. The `TaskStatus` StrEnum is only enforced in Python code
- `ResultModel.success` is `Integer` (0/1) — not a Boolean. SQLite doesn't enforce the 0/1 range
- `MessageModel.tool_args` is `JSON` — stores arbitrary dicts. No schema validation on what's stored
- `TaskModel.metadata_json` is `JSON` — same issue

### 5.2 Orphaned Records

| Scenario | Orphaned Data | Impact |
|----------|---------------|--------|
| Task created in DB, NATS publish fails | `tasks` row with status "pending" forever | Invisible task leak |
| Session created, server crashes before first message | `sessions` row with status "active" forever | Session appears active but is unreachable |
| Message added to DB but agent fails | `messages` row with user message but no assistant response | Conversation history is incomplete |
| Result written to DB but KV write fails | `results` row exists but API returns 404 | Result is in DB but unretrievable via API |
| Session deleted via CLI | `sessions` row deleted, `messages` rows deleted (cascade in code) | ✅ Clean — but only if `delete_session()` is called |

### 5.3 `fork_session()` — Data Integrity

The fork operation (session_repo.py lines 162-199) copies messages within a single `get_session()` context. However, `get_session()` uses `async with self.async_session()` which auto-commits on success. The fork creates a new session and copies messages — if the copy loop fails partway through, **some messages are copied and others aren't**, with no rollback (the session was already added).

**⚠️ `fork_session()` is not atomic — partial failure leaves a forked session with incomplete message history.**

### 5.4 `delete_session()` — SQL Injection Risk

```python
await session.execute(
    text("DELETE FROM messages WHERE session_id = :sid"),
    {"sid": session_id},
)
```

This uses parameterized queries — ✅ safe from SQL injection. However, the raw SQL bypasses SQLAlchemy's ORM, so any future schema changes to the `messages` table won't be caught by the ORM.

---

## 6. NATS MESSAGES

### 6.1 Published Messages

| Subject | Publisher | Payload | Format |
|---------|-----------|---------|--------|
| `tasks.submit` | `NexusSDK.submit_task()` | `TaskSchema.model_dump()` | JSON with NATSJSONEncoder |
| `nexus_results` (KV) | `AgentBus.put_result()` | `ResultSchema.model_dump()` | JSON with NATSJSONEncoder |

### 6.2 Message Loss Scenarios

1. **NATS publish fails**: `bus.publish()` retries 3 times with backoff, then raises. The exception propagates to the caller. For `/tasks` endpoint, this means the task was created in DB but never published — **orphaned task**.

2. **KV put fails**: `bus.put_result()` retries 3 times, then raises. In `worker.py:handle_task()`, the exception is caught by the outer `except` block, which tries to save a failure result. But if the KV put for the failure result also fails, the error is logged and **the task result is lost**.

3. **Subscription fails**: `bus.subscribe()` retries 3 times, then raises. In `NexusWorker.start()`, this exception propagates to the lifespan handler, which logs it and re-raises — **server fails to start**.

4. **Message arrives but worker is down**: NATS JetStream will retain the message (if configured with `ack_wait`). But the code uses `subscribe()` (ephemeral), not `pull_subscribe()` or queue group. **If no worker is running when the message is published, the message is lost**.

### 6.3 Message Duplication

- NATS provides at-least-once delivery by default. The `handle_task()` callback could receive the same message multiple times.
- `task_repo.create_task()` is idempotent (checks for existing ID), so duplicate task creation is safe.
- But the agent task itself could be executed multiple times, producing **duplicate results** in the KV store (overwritten) and **duplicate result rows** in the DB (different primary keys possible).

### 6.4 `NATSJSONEncoder` — Serialization Gaps

```python
class NATSJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
```

**⚠️ `bytes` objects are not handled.** If any message field contains `bytes` (e.g., binary data in metadata), serialization fails with `TypeError`. The `TaskSchema.model_dump()` could contain `bytes` if metadata includes binary data.

---

## 7. FILE OUTPUTS

### 7.1 Files Created/Modified

| File | Creator | Validation |
|------|---------|------------|
| `~/.nexusagent/config/nexusagent.yaml` | Config system | YAML parsed, Pydantic validated |
| `~/.nexusagent/data/nexus.db` | `DatabaseManager` | SQLite, schema created via `Base.metadata.create_all()` |
| `~/.nexusagent/auth/.master.secret` | `AuthManager.initialize_wizard()` | 0o600 permissions |
| `~/.nexusagent/auth/keystore.json` | `AuthManager.save_key()` | 0o600 permissions, Fernet encrypted |
| `~/.nexusagent/auth/.master.salt` | `AuthManager._get_salt()` | 0o600 permissions |
| `~/.nexusagent/sessions/{id}/memory/` | `Session.__init__()` | Directory created, no file validation |
| `~/.nexusagent/NEXUS.md` | User or prompt system | Loaded and parsed, no validation |

### 7.2 Memory Files

The `HybridMemoryManager` writes to `self.memory_dir` (default `~/.nexusagent/sessions/{session_id}/memory/`). Files are created by the memory system with no size limits or rotation.

**⚠️ A long-running session with frequent memory writes will accumulate files indefinitely. No cleanup mechanism exists.**

### 7.3 Tool File Operations

File tools (`read_file`, `write_file`, `edit_file`, etc.) operate within a workspace root set by `set_workspace_root()`. The path jail prevents writing outside the workspace, but:

- **No validation on file content** — tools can write arbitrary bytes
- **No file size limits** — `read_file` reads the entire file into memory
- **No atomic writes** — `write_file` writes directly, so a crash mid-write corrupts the file

---

## 8. LLM RESPONSES

### 8.1 `LLMProvider.generate()` — Output Chain

```
LLM API (Gemini/OpenRouter)
  → LLMResponse(content=response.text, model_used=..., provider=...)
  → Returned to caller
```

**Failure modes:**
- **Gemini**: `response.text` could raise `ValueError` if the response was blocked by safety filters. This is caught by the retry decorator and retried — but safety blocks won't change on retry, causing all 3 attempts to fail
- **OpenRouter**: `response.choices[0].message.content` could be `None` if the model returns no content. This would create `LLMResponse(content=None, ...)` which would fail downstream when `str` operations are applied
- **Timeout**: Both paths raise `TimeoutError` which is caught and retried. After 3 failures, the `TimeoutError` propagates

### 8.2 `ImageAttachment.encode()` — Data Flow

```
File path or URL
  → If URL: return URL directly
  → If local file: read bytes → base64 encode → data URI
  → Return data URI string
```

**Failure modes:**
- File not found → exception caught in `Session._build_user_message()`, replaced with `[Image could not be loaded: <path>]` text block
- File too large → no size check before reading into memory. A 1GB image file would be read entirely into memory before encoding
- **The `max_image_size_mb` setting in `AgentConfig` is never checked in the code** — it's defined but not enforced

---

## 9. ERROR HANDLING SUMMARY

### 9.1 Error Propagation Map

```
LLM API Error
  → retry_with_backoff (3 attempts)
    → All fail → exception propagates
      → run_agent_task() catches → returns {"result": None, "error": str(e), "success": False}
        → WorkerPool._execute_bounded() receives error dict
          → If on_failure="abort": returns "Aborted: {e}"
          → If on_failure="retry": continues loop
          → If on_failure="escalate": returns "Escalated: {e}"

Agent Invocation Error (session.py)
  → Caught at line 431
    → Logged with exc_info
    → HookEvent.ERROR fired (if hooks enabled)
    → ErrorEvent enqueued → WebSocket → TUI renders error message

NATS Connection Error
  → AgentBus.connect() raises
    → lifespan handler catches → logs → re-raises → server fails to start

DB Error
  → get_session() context manager rolls back → re-raises
    → Caller catches (most do) → logs warning → continues with degraded state
```

### 9.2 Swallowed Exceptions

| Location | Exception | Impact |
|----------|-----------|--------|
| `session.py:338-339` | DB write failure for user message | Message lost, agent still processes |
| `session.py:418-419` | DB write failure for assistant message | Response shown to user but not persisted |
| `session.py:428-429` | Memory write failure | Memory silently lost |
| `session.py:546-547` | Compaction flush failure | Pre-compaction memory lost |
| `session.py:578-579` | Session status update failure | Session shows as "active" in DB after close |
| `worker.py:118-119` | Heartbeat failure | Silent — heartbeat retries next cycle |
| `bus.py:146-147` | Subscription unsubscribe failure | Silent — connection closing anyway |
| `hooks/__init__.py:135-140` | Hook callback failure | Logged, other hooks continue |

### 9.3 Error Message Quality

**Good:**
- Tool access denied messages include the role, policy, and suggestion to use `tool_search()`
- Circuit breaker errors include the breaker name and state
- Auth errors distinguish between missing key, invalid key, and unconfigured auth

**Poor:**
- `create_task` error returns raw `str(e)` — may leak internal paths
- `get_task_result` returns generic "Result not found or timed out" — can't distinguish between "not ready" and "never existed"
- `_extract_agent_response` fallback returns `str(result)` — Python repr in user-facing output
- `cancel_task` returns "Task not found or already completed/failed" — can't distinguish the two cases

---

## 10. DATA CONSISTENCY MATRIX

| Output | Source of Truth | Can Diverge? | Mechanism |
|--------|----------------|--------------|-----------|
| Task status (API) | `TaskModel.status` in DB | ⚠️ Yes | Worker updates status asynchronously; stale reads possible between DB write and NATS publish |
| Task result (API) | NATS KV store | ⚠️ Yes | KV and DB are dual-written; API reads KV only |
| Task result (DB) | `ResultModel` table | ⚠️ Yes | Written by worker, but API doesn't read from it |
| Session status | `SessionModel.status` in DB | ⚠️ Yes | In-memory `session.status` is updated first, DB update is async and can fail |
| Message history | `MessageModel` table | ⚠️ Yes | DB writes are best-effort; failures are logged but not retried |
| TUI display | In-memory widget state | ⚠️ Yes | Widgets accumulate state that can't be reconstructed from DB |
| Memory index | `~/.nexusagent/sessions/{id}/memory/` | ⚠️ Yes | File-based memory is independent of DB; compaction can lose data |
| Circuit breaker state | Module-level variables | ❌ No | In-memory only, no persistence |
| Worker status (API) | Hardcoded "running" | ⚠️ Yes | Doesn't actually check worker health |

---

## 11. CRITICAL FINDINGS

### 🔴 High Priority

1. **Orphaned tasks on NATS failure** — Task is created in DB but never published. No cleanup job exists.
2. **Retry task loses description** — `retry_task` endpoint hardcodes `"description": "retried"`, losing the original task.
3. **Cancel uses wrong status** — Sets DB status to `FAILED` but returns `"cancelled"` to client.
4. **No NATS message durability** — Ephemeral subscriptions mean messages published with no worker are lost.
5. **`bytes` not serializable in NATS encoder** — Will crash if metadata contains binary data.

### 🟡 Medium Priority

6. **Fork session is not atomic** — Partial failure leaves incomplete session.
7. **Memory writes unbounded** — No size limits or rotation for session memory files.
8. **`max_image_size_mb` never enforced** — Config field exists but is not checked in code.
9. **Interrupt only checked post-agent** — `_cancel_flag` is not checked during streaming, only after `agent()` returns.
10. **TUI queue fire-and-forget** — `asyncio.create_task` at line 684 has no error handling.
11. **Health check doesn't verify NATS** — Only checks if `bus.nc` is truthy, not if it's actually connected.
12. **Worker status is hardcoded** — Always reports "running" regardless of actual state.

### 🟢 Low Priority

13. **`render_markdown` placeholder collision** — `__CODE_BLOCK_N__` in user text causes incorrect rendering.
14. **Log sensitive data** — API errors and tracebacks may contain credentials or file contents.
15. **`logging.basicConfig` at import time** — May be silently ignored if called after other logging setup.
16. **No DB constraints on status columns** — Free-text status allows invalid values.
17. **`sync_wrapper` in `retry_on_false` is missing `return decorator`** — The sync path of `retry_on_false` (line 231) falls through without returning the decorator, causing `None` to be returned for sync functions.

---

## 12. TRANSFORMATION CHAIN DIAGRAMS

### 12.1 Task Submission → Worker Completion

```
Client HTTP POST
  → SubmitTaskRequest (Pydantic validation)
  → task_repo.create_task() [DB write]
  → sdk.submit_task()
    → TaskSchema.model_dump() [Pydantic serialization]
    → json.dumps(..., cls=NATSJSONEncoder) [JSON encoding]
    → bus.publish("tasks.publish", payload) [NATS publish]
  → {"task_id": id, "status": "submitted"} [HTTP response]

... (async, possibly minutes later) ...

NATS message delivery
  → NexusWorker.handle_task()
    → json.loads(msg.data.decode()) [JSON decode]
    → TaskSchema(**data) [Pydantic validation]
    → task_repo.create_task() [DB write — idempotent]
    → task_repo.update_task_status(PROCESSING) [DB write]
    → _run_agent_task()
      → Agent() creation
      → agent(state) [LLM invocation — minutes]
      → _extract_agent_response() [result extraction]
    → task_repo.save_result() [DB write]
    → task_repo.update_task_status(COMPLETED) [DB write]
    → bus.put_result() [NATS KV write]
```

### 12.2 User Message → TUI Display

```
User types message in TUI
  → ChatInput.Submitted event
  → _handle_slash_command() check
  → _input_queue.put(message)
  → ws.send(json.dumps({"type": "user_input", "content": msg}))
  → [WebSocket to server]

Server receives
  → session_websocket() receives JSON
  → session.send(content)
    → db_repo.add_message() [DB write — best effort]
    → Build messages list (system + context + memory + history + user)
    → agent({"messages": messages}) [LLM invocation]
    → _extract_agent_response() [result extraction]
    → ResponseEvent(content=final_content).model_dump()
    → session._enqueue(event)
    → event_stream() → websocket.send_json(event)

TUI receives
  → ws.recv() → json.loads()
  → _handle_event({"type": "response", "content": "..."})
  → render_markdown(content) [regex-based markdown rendering]
  → AssistantMessage.finalize(rendered)
  → Textual renders widget
```

---

## 13. RECOMMENDATIONS

1. **Fix `retry_task` description loss** — Fetch the original task description from DB before re-publishing.
2. **Fix `cancel_task` status** — Add a `CANCELLED` status to `TaskStatus` enum and use it consistently.
3. **Add NATS message durability** — Use pull subscriptions or queue groups instead of ephemeral subscriptions.
4. **Handle `bytes` in NATSJSONEncoder** — Add `bytes` handling or validate metadata before serialization.
5. **Make `fork_session` atomic** — Wrap the entire operation in a single transaction.
6. **Enforce `max_image_size_mb`** — Add a check in `ImageAttachment.encode()` or `Session._build_user_message()`.
7. **Add task cleanup job** — Periodically scan for tasks stuck in "pending" for >N minutes and mark them failed.
8. **Fix `retry_on_false` sync path** — Add missing `return decorator` at line 231.
9. **Add DB constraints** — Use CHECK constraints on status columns to prevent invalid values.
10. **Improve interrupt handling** — Check `_cancel_flag` during streaming, not just after agent completion.
