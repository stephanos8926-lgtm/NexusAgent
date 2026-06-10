# NexusAgent — Tools & API Layer: Semantic Map

> Generated from source code analysis of all 16 core files.
> Covers: tool inventory, API endpoints, WebSocket handlers, SDK methods, bus events, DB schema, auth, and issues.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Complete Tool Inventory](#2-complete-tool-inventory)
3. [API Endpoints](#3-api-endpoints)
4. [WebSocket Handlers](#4-websocket-handlers)
5. [SDK Reference](#5-sdk-reference)
6. [Bus / NATS Events](#6-bus--nats-events)
7. [Database Schema](#7-database-schema)
8. [Authentication System](#8-authentication-system)
9. [Web UI](#9-web-ui)
10. [Issues & Observations](#10-issues--observations)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────────┐  │
│  │  Web UI       │   │  SDK Client  │   │  External HTTP Clients  │  │
│  │  (Gradio)     │   │  (NexusSDK)  │   │  (curl, frontend, etc.) │  │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬─────────────┘  │
│         │                  │                        │                │
└─────────┼──────────────────┼────────────────────────┼────────────────┘
          │                  │                        │
          ▼                  ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI SERVER (server.py)                       │
│                                                                      │
│  HTTP Endpoints ◄──► API Auth (api_auth.py) ◄──► auth.py (keystore) │
│  WebSocket ◄──────► Sessions / Event Stream                          │
│  Routes ─────────► SDK (sdk.py) ──► Bus (bus.py) ──► NATS           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                     WORKER (co-located in-process)             │  │
│  │  Subscribes to NATS subjects, executes tasks via Agent+Tools   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    TOOL LAYER (tools/*)                              │
│                                                                      │
│  register_all.py ─── @register_tool() ───► registry.py (_REGISTRY)  │
│                                                                      │
│  Tools: fs.py │ shell.py │ git.py │ code_search.py │ patch.py       │
│          test_runner.py │ research.py                                │
│  Registered: spawn_subagent │ ask_user │ memory_search│memory_get    │
│               memory_write                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Request flow

1. Client sends HTTP request or WebSocket message
2. `api_auth.py` verifies `X-API-Key` header against Fernet-encrypted keystore (`auth.py`)
3. Server route delegates to `NexusSDK` which publishes to NATS JetStream via `AgentBus`
4. Worker receives task from NATS, creates `Agent` with role/policy, invokes tools from registry
5. Tool results flow back through bus events, session event stream, or KV store

---

## 2. Complete Tool Inventory

### 2.1 Tool Registry (`registry.py`)

**Purpose:** Global `_REGISTRY` dict, policy enforcement (permissive/restricted/strict), role-based manifests, tool search with fuzzy matching.

**Key classes/functions:**

| Symbol | Type | Description |
|--------|------|-------------|
| `ToolInfo` | dataclass | Metadata: name, func, description, parameters, example, category, returns, requires |
| `register_tool()` | decorator | Registers a function in `_REGISTRY` |
| `get_tool_info(name)` | function | Look up tool metadata |
| `list_all_tools()` | function | Return all registered tools |
| `tool_search()` | function | Policy-aware tool search with exact/fuzzy/category filtering |
| `require_policy(name)` | decorator | Enforce policy before tool execution |
| `check_tool_access(name)` | function | Returns error string or None |
| `set_policy_context(role, policy)` | function | Set thread-local policy |
| `ROLE_MANIFESTS` | dict | 9 roles: minimal, reader, writer, coder, tester, reviewer, debugger, researcher, full |
| `_is_tool_allowed()` | function | Core policy enforcement (3 modes) |

**Policy levels:**
- `permissive` — User-spawned agents. Auto-unlock on first call.
- `restricted` — Sub-agents. Enforced boundaries, can unlock within role.
- `strict` — Sandboxed sub-agents. Locked to initial manifest forever.

### 2.2 Complete Tool Table (27 tools)

#### Core Tools (3)

| Tool | Function | Category | Parameters | Returns |
|------|----------|----------|------------|---------|
| `tool_search` | `tool_search()` | `core` | query, exact, category, max_results | Formatted tool list/search results |
| `auto_correct` | `auto_correct()` | `core` | tool_name, kwargs | Correction message or validation confirmation |

#### File System Tools (7)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `read_file` | `read_file()` | `fs` | path, offset, limit | Tracks read files; line-range mode adds line numbers |
| `read_multiple_files` | `read_multiple_files()` | `fs` | paths (list) | Dict of path→content |
| `write_file` | `write_file()` | `fs` | path, content | **Requires read-first** for existing files |
| `write_multiple_files` | `write_multiple_files()` | `fs` | files (dict) | Bulk write, each must be read-first |
| `edit_file` | `edit_file()` | `fs` | path, old_text, new_text, start_line, end_line | Surgical edit with read-first + existence validation |
| `list_directory` | `list_directory()` | `fs` | path, recursive, max_depth, pattern, exclude | Nested dict tree; default excludes .git/__pycache__/node_modules/.venv |
| `apply_patch` | `apply_patch()` | `fs` | path, diff | Uses `patch-ng` library |

#### Shell Tools (2)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `run_shell` | `run_shell()` | `shell` | command, workdir, env, timeout (default 120) | `shell=False` + `shlex.split()` for injection prevention; 1MB output cap |
| `run_shell_streaming` | `run_shell_streaming()` | `shell` | command, workdir, env, timeout (default 300) | Line-by-line streaming for long-running commands |

#### Git Tools (9)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `git_status` | `git_status()` | `git` | workdir | `git status --short` |
| `git_diff` | `git_diff()` | `git` | file_path, cached, workdir | Supports `--cached` for staged changes |
| `git_log` | `git_log()` | `git` | count, file_path, oneline, workdir | Default: oneline, 10 commits |
| `git_branch` | `git_branch()` | `git` | workdir | `git branch -v` |
| `git_show` | `git_show()` | `git` | commit (default HEAD), workdir | `git show <ref> --stat` |
| `git_stash_push` | `git_stash_push()` | `git` | message, workdir | Write op |
| `git_stash_pop` | `git_stash_pop()` | `git` | workdir | Write op |
| `git_stash_list` | `git_stash_list()` | `git` | workdir | — |
| `git_commit` | `git_commit()` | `git` | message, files, workdir | Write op; `add -A` or specific files |
| `git_checkout_branch` | `git_checkout_branch()` | `git` | branch, create, workdir | Write op; supports `-b` for creation |

#### Test Runner Tools (2)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `run_tests` | `run_tests()` | `test` | workdir, test_path, framework, timeout (300) | Auto-detects: pytest/jest/vitest/maven/gradle/go/cargo |
| `run_single_test` | `run_single_test()` | `test` | test_path, workdir, framework, timeout (60) | Delegates to run_tests() |

#### Code Search Tools (3)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `search_code` | `search_code()` | `search` | query, path, file_pattern, context_lines, max_results (50), case_sensitive | ripgrep primary, grep fallback |
| `find_symbol` | `find_symbol()` | `search` | symbol, path, file_pattern | Cross-language: def/class/function/const/func/fn/struct/impl/interface/type |
| `find_references` | `find_references()` | `search` | symbol, path, file_pattern, max_results (100) | All occurrences, not just definitions |

#### Research / Web Tools (3)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `search_web` | `search_web()` | `web` | query | Exa primary → Tavily fallback; requires API keys |
| `search_local_docs` | `search_local_docs()` | `web` | query | Calls `npx ctx7@latest docs query` via subprocess |
| `fetch_url` | `fetch_url()` | `web` | url | httpx; HTML→text conversion; JSON pretty-print; 5000 char cap |

#### Orchestration Tools (1)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `spawn_subagent` | `spawn_subagent()` | `orchestration` | task, working_dir, max_turns (15), acceptance_criteria, memory_mode | Async; uses `worker_pool.spawn()` with `TaskContract` |

#### Interaction Tools (1)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `ask_user` | `ask_user()` | `interaction` | question, options | Returns fallback in headless; TUI modal in interactive |

#### Memory Tools (3)

| Tool | Function | Category | Parameters | Key Behavior |
|------|----------|----------|------------|-------------|
| `memory_search` | `memory_search()` | `memory` | query, max_results (6) | Async; hybrid keyword+vector via `HybridMemoryManager` |
| `memory_get` | `memory_get()` | `memory` | path, offset, limit (50) | Read memory file with path traversal guard |
| `memory_write` | `memory_write()` | `memory` | content, type, description, confidence, entities | YAML frontmatter + index via `HybridMemoryManager` |

### 2.3 Tool Categories Summary

| Category | Count | Tools |
|----------|-------|-------|
| `core` | 2 | tool_search, auto_correct |
| `fs` | 7 | read_file, read_multiple_files, write_file, write_multiple_files, edit_file, list_directory, apply_patch |
| `shell` | 2 | run_shell, run_shell_streaming |
| `git` | 9 | git_status, git_diff, git_log, git_branch, git_show, git_stash_push, git_stash_pop, git_stash_list, git_commit, git_checkout_branch |
| `test` | 2 | run_tests, run_single_test |
| `search` | 3 | search_code, find_symbol, find_references |
| `web` | 3 | search_web, search_local_docs, fetch_url |
| `orchestration` | 1 | spawn_subagent |
| `interaction` | 1 | ask_user |
| `memory` | 3 | memory_search, memory_get, memory_write |
| **Total** | **33** | (27 unique names; tool_search and auto_correct in core + 25 functional + 6 registered dynamically) |

### 2.4 Role Manifest Mapping

| Role | Tool Count | Key Inclusions |
|------|-----------|----------------|
| `minimal` | 1 | tool_search only |
| `reader` | 8 | All search + read tools, no modifications |
| `writer` | 5 | Read + write + edit + list |
| `coder` | 18 | Full dev: all fs, shell, git, test, search, patch |
| `tester` | 12 | Read, test, edit, search, git status/diff |
| `reviewer` | 11 | Read, search, git history/status, tests — no mutations |
| `debugger` | 14 | Read, edit, test, shell, stash — focused on fixing |
| `researcher` | 10 | Read, search, web — no mutations |
| `full` | All | Everything in `_REGISTRY` |

---

## 3. API Endpoints

### Server (`server.py`)

**Framework:** FastAPI with CORSMiddleware (allow_origins=["*"]).
**Auth:** All endpoints except `/health` require API key via `X-API-Key` header.

| Method | Path | Auth | Request Model | Response | Description |
|--------|------|------|---------------|----------|-------------|
| `GET` | `/health` | No | — | `{status, natS}` | Health check; reports NATS connection state |
| `POST` | `/tasks` | Yes | `SubmitTaskRequest {description, priority, metadata}` | `{task_id, status}` | Submit new task; saves to DB + publishes to NATS |
| `GET` | `/tasks` | Yes | Query: `status?`, `limit=50`, `offset=0` | `{tasks, count}` | List tasks with status filter + pagination |
| `GET` | `/tasks/{task_id}/status` | Yes | — | `{task_id, status}` | Get task status from DB |
| `GET` | `/tasks/{task_id}/result` | Yes | — | `ResultSchema` or 404 | Get task result; 404 if not found |
| `POST` | `/tasks/{task_id}/cancel` | Yes | — | `{task_id, status}` | Cancel pending/processing task |
| `POST` | `/tasks/{task_id}/retry` | Yes | — | `{task_id, status}` | Retry failed task; re-publishes to NATS |
| `GET` | `/workers` | Yes | — | `{workers: [...]}` | Worker status + circuit breaker states |
| `GET` | `/tools` | Yes | — | `{tools, total}` | All registered tools grouped by category |

**Note:** The `cancelled` status is set by `task_repo.cancel_task()` but the actual enum uses `TaskStatus.FAILED` for cancellation — this is a semantic issue (see Issues section).

### Request/Response Models

```python
# SubmitTaskRequest
class SubmitTaskRequest(BaseModel):
    description: str
    priority: int = 1
    metadata: dict = {}

# Responses are inline dicts (not Pydantic models in most cases)
```

---

## 4. WebSocket Handlers

### Session WebSocket (`/sessions/{session_id}/ws`)

**Path:** `ws://host:port/sessions/{session_id}/ws?api_key=xxx`

**Auth:** API key via query parameter; closes with code 4001 on failure.

**Server → Client Events** (via `session.event_stream()`):

| Event Type | Description |
|------------|-------------|
| `session_status` | `{type: "session_status", status: "..."}` — sent on connect |
| *(dynamic)* | All events from the session's event stream (agent messages, tool calls, etc.) |

**Client → Server Messages** (JSON):

| Message Type | Fields | Description |
|-------------|--------|-------------|
| `user_input` | `{type, content}` | Send user message to the agent |
| `approval` | `{type, call_id, approved}` | Approve/deny a tool call |
| `interrupt` | `{type}` | Interrupt current agent execution |
| `close` | `{type}` | Close the session |

**Key behaviors:**
- Creates an `Agent(role="full", policy="permissive")` per WebSocket connection
- Sets workspace root to `session.working_dir`
- Uses `session_manager.get_or_create()` for session lifecycle
- Runs two concurrent tasks: `send_events()` and `receive_messages()`
- On disconnect: marks session idle via `session_manager.mark_idle()`

---

## 5. SDK Reference

### `NexusSDK` class (`sdk.py`)

Global instance: `sdk = NexusSDK()`

**Lifecycle methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `connect()` | `→ None` | Ensure NATS connection established |
| `disconnect()` | `→ None` | Close NATS connection |
| `__aenter__` / `__aexit__` | context manager | Auto connect/disconnect |

**Task operations:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `submit_task(task_data)` | `dict → str` | Publish to `tasks.submit`; returns task_id |
| `get_task_status(task_id)` | `str → TaskStatus \| None` | Query from DB |
| `get_result(task_id)` | `str → ResultSchema \| None` | Fetch from JetStream KV |
| `list_tasks(status?, limit, offset)` | `→ list[dict]` | Paginated task list |
| `cancel_task(task_id)` | `str → bool` | Cancel via DB |
| `retry_task(task_id)` | `str → str \| None` | Retry via DB + re-publish |
| `submit_batch(tasks)` | `list[dict] → list[str]` | Sequential submit |

**Polling helpers:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `wait_for_result(task_id, timeout=300, poll_interval=1)` | `→ ResultSchema \| None` | Poll KV until result or timeout |
| `submit_and_wait(task_data, timeout, poll_interval)` | `→ ResultSchema \| None` | Submit + poll combined |

**Utility methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `health_check()` | `→ dict` | `{status, nats}` |
| `list_workers()` | `→ dict` | Worker + circuit breaker status (hardcoded "default" worker) |
| `list_tools()` | `→ dict` | Tools grouped by category (same as `/tools` endpoint) |

---

## 6. Bus / NATS Events

### `AgentBus` class (`bus.py`)

**Connection:**
- Connects to NATS via `settings.server.nats_url`
- JetStream enabled; KV bucket `nexus_results` (auto-created)
- JSON encoding with `NATSJSONEncoder` (handles datetime/date serialization)

**Subjects:**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `tasks.submit` | Publish (SDK) → Subscribe (Worker) | New task submission |

**Retry logic:**
- Subscribe: 3 attempts with exponential backoff (0.5s, 1s, 2s)
- KV put: 3 attempts with exponential backoff
- KV get: Single attempt with 5s timeout

**KV Store operations:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `put_result(task_id, result)` | `str, Any → None` | Store result payload (3 retries) |
| `get_result(task_id)` | `str → Any \| None` | Retrieve result; None on not-found/timeout |

**Global singleton:** `get_bus()` creates/returns `_default_bus`; `set_bus()` for testing.

---

## 7. Database Schema

### ORM: SQLAlchemy async with SQLite (`dbaiosqlite`)

### 7.1 Tables

#### `tasks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK | UUID task identifier |
| `description` | String | NOT NULL | Task description |
| `priority` | Integer | default=1 | Task priority |
| `status` | String | default="pending" | pending/processing/completed/failed |
| `created_at` | DateTime | default=now(UTC) | Creation timestamp |
| `updated_at` | DateTime | default=now(UTC), onupdate=now(UTC) | Last update |
| `metadata_json` | JSON | default={} | Arbitrary metadata |

#### `results`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `task_id` | String | PK | FK to tasks.id |
| `success` | Integer | default=0 | 1=success, 0=failure |
| `data` | String | nullable | Result data (text) |
| `error` | String | nullable | Error message |
| `completed_at` | DateTime | default=now(UTC) | Completion timestamp |
| `duration` | Float | nullable | Execution time in seconds |

#### `sessions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK | UUID session identifier |
| `working_dir` | String | NOT NULL, default="." | Agent working directory |
| `memory_id` | String | nullable | Associated memory ID |
| `status` | String | default="active" | active/idle/closed |
| `created_at` | DateTime | default=now(UTC) | Creation timestamp |
| `updated_at` | DateTime | default=now(UTC), onupdate=now(UTC) | Last update |

#### `messages`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK | UUID message identifier |
| `session_id` | String | NOT NULL | FK to sessions.id (logical, no DB constraint) |
| `role` | String | NOT NULL | user/assistant/system/tool |
| `content` | String | NOT NULL | Message content |
| `tool_name` | String | nullable | Tool name if tool call |
| `tool_args` | JSON | nullable | Tool arguments |
| `created_at` | DateTime | default=now(UTC) | Creation timestamp |

### 7.2 Repository Methods (`TaskRepository`)

| Method | Description |
|--------|-------------|
| `create_task(task_id, description, priority, metadata)` | Idempotent create; skips if exists |
| `update_task_status(task_id, status)` | Update status field |
| `get_task_status(task_id)` | → status string or None |
| `save_result(task_id, success, data, error, duration)` | Insert result row |
| `list_tasks(status?, limit, offset)` | Ordered by created_at DESC |
| `cancel_task(task_id)` | Sets status to FAILED; rejects if completed/failed |
| `retry_task(task_id)` | Sets status to PENDING; only from FAILED |

### 7.3 Repository Methods (`SessionRepository`)

| Method | Description |
|--------|-------------|
| `create_session(working_dir, memory_id?)` | → new session_id (UUID) |
| `get_session(session_id)` | → session dict or None |
| `update_status(session_id, status)` | Update session status |
| `add_message(session_id, role, content, tool_name?, tool_args?)` | → message_id |
| `get_messages(session_id, limit=100)` | → ordered message list |
| `list_sessions(status?, limit, offset)` | → ordered session list |
| `rename_session(session_id, new_id)` | Atomic rename; checks collision |
| `delete_session(session_id)` | Deletes messages + session |
| `fork_session(source_id, new_working_dir?)` | Deep-copies session + all messages |

**Note:** No actual foreign key constraints exist in the DB. The `messages.session_id → sessions.id` relationship is logical, enforced at the application level.

---

## 8. Authentication System

### Two-layer auth:

1. **API Key Auth** (`api_auth.py`):
   - Header: `X-API-Key`
   - Validates against Fernet-encrypted keystore
   - Fail-closed: rejects on missing/unknown errors

2. **Keystore** (`auth.py` — `AuthManager`):
   - Master secret: stored at `settings.auth.master_secret_path` (file, mode 0o600)
   - KDF: PBKDF2-HMAC-SHA256 with installation-specific salt
   - Encryption: Fernet (AES-128-CBC + HMAC-SHA256)
   - Keystore file: JSON dict of `{service: encrypted_key}`, mode 0o600
   - **Global instance:** `auth_manager = AuthManager()`

**Methods:**

| Method | Description |
|--------|-------------|
| `initialize_wizard(force)` | Generate master secret + salt (one-time setup) |
| `save_key(service, key)` | Encrypt + store API key |
| `get_key(service)` | Decrypt + return API key |

---

## 9. Web UI

### Gradio-based Web UI (`web_ui.py`)

**Title:** "NexusAgent Control Center"
**Port:** 7860
**Theme:** Dark industrial (orange-red #FF4B2B on charcoal #1A1A1A)

**Components:**
- Task definition text input
- "TRANSMIT TASK" submit button
- System output textarea (non-interactive)
- SDK status display

**Functions:**
- `handle_submit(text, sdk)` → submits via `NexusSDK.submit_task()`; returns (log_msg, status_str)
- `create_ui()` → `gr.Blocks`
- `run_ui()` → launches Gradio server on 0.0.0.0:7860

**Note:** The Web UI does NOT use the FastAPI server's `/tasks` endpoint. It creates its own `NexusSDK` instance in-process, bypassing HTTP entirely. The 8-character task ID displayed in the UI (`uuid4()[:8]`) is truncated for display — the actual UUID in NATS is full-length. This is potentially confusing.

---

## 10. Issues & Observations

### 10.1 Security Issues

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | **High** | `git.py` | **Shell injection**: `_run_git()` uses `shell=True` with string interpolation (`f"git {args}"`). While commands are built internally (not from user input), this is an anti-pattern. A crafted `commit` message like `"; rm -rf /;` would be interpreted by the shell. |
| 2 | **Medium** | `git.py` | Commit message and file paths in `git_commit()` are interpolated directly into shell strings without escaping. Malicious messages/paths can inject commands. |
| 3 | **Medium** | `server.py` | `CORSMiddleware` with `allow_origins=["*"]` and `allow_credentials=True` is permissive for production. |
| 4 | **Low** | `shell.py` | Env var sanitization uses `.replace("_", "").replace("-", "").isalnum()` which doesn't strip all dangerous characters (e.g., dots, spaces). |
| 5 | **Low** | `research.py` | `search_local_docs()` runs `npx ctx7@latest` — arbitrary package execution without pinning or integrity check. |
| 6 | **Medium** | `registry.py` | `_read_files` tracking is module-level (global state), not thread-local. Concurrent agents can pollute each other's read tracking. |

### 10.2 Design Issues

| # | Location | Issue |
|---|----------|-------|
| 1 | `sdk.py` / `server.py` / `web_ui.py` | `submit_task()` is duplicated in SDK and server. The HTTP endpoint calls both `task_repo.create_task()` AND `sdk.submit_task()` which also calls `submit_task()`. This is redundant and the task_repo call creates a DB row that may diverge from the NATS path. |
| 2 | `server.py` | WebSocket import on line 263 shadows the FastAPI `WebSocket` import on line 6 (both named `websocket`). The inner `from nexusagent.api_auth import verify_api_key` on line 250 is redundant — it's already imported at line 10. |
| 3 | `sdk.py` | `list_workers()` hardcodes a single "default" worker name. The circuit breaker references may fail if the worker module layout changes. |
| 4 | `db.py` | No actual foreign key constraints — referential integrity is application-enforced. Deleting a session doesn't cascade-delete its messages at the DB level. |
| 5 | `server.py` `/tasks/{task_id}/cancel` | Sets task status to `FAILED` internally (via `task_repo.cancel_task()`), not a distinct `CANCELLED` status. Clients querying status will see `failed` instead of `cancelled`. |
| 6 | `web_ui.py` | Task IDs displayed as 8-char truncations (`uuid4()[:8]`) can collide in high-throughput scenarios. The SDK returns full UUIDs. |
| 7 | `register_all.py` | The `fs` category has 7 tools including `apply_patch`, but the `coder` role manifest includes `apply_patch` separately — this means patch is registered as an `fs` tool but only available to roles that include it. This is correct but `apply_patch` could logically be its own category. |

### 10.3 Potential Bugs

| # | Location | Issue |
|---|----------|-------|
| 1 | `sdk.py:63` | `task_id = task_data.pop("id", ...)` mutates the copy but the original `task_data` `id` is used in server.py:102-109 before calling `sdk.submit_task()`. The `pop("id")` inside SDK extracts the ID correctly — but server.py:95 already extracted `task_id` and passes it in the dict, so the SDK's `pop("id")` handles it. This works but is fragile — if the caller doesn't include `id`, the SDK generates a new one, diverging from the DB row. |
| 2 | `registry.py:144-151` | `get_policy_context()` returns `set(ctx.unlocked)` — a copy, but this means callers can't modify the original. This is defensive but could be confusing. |
| 3 | `bus.py:46-51` | `create_key_value` error handling catches all `nats.errors.Error` — if the bucket exists but the user lacks permissions to attach, it will silently fail and try to attach anyway. |
| 4 | `tools/fs.py:14` | `_read_files` is a module-level `set()` — not thread-safe and shared across all tool invocations in the process. |

### 10.4 Missing Features

| Feature | Description |
|---------|-------------|
| No result deletion | KV store has no TTL or eviction for old results |
| No task deletion | Tasks can be cancelled but never deleted from DB |
| No auth for WebSocket beyond API key | Once connected, all messages are trusted; no per-session auth |
| No rate limiting | No rate limiting on task submission or API calls |
| No tool result streaming to API | Results only available via polling or WebSocket |

---

*Auto-generated from source analysis. 16 files read, 27+ tools cataloged, 9 API endpoints, 1 WebSocket handler, 15 SDK methods, 4 DB tables, 10 issues identified.*
