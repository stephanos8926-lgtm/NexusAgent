# NexusAgent Semantic Codebase Index

> Generated: 2026-06-12
> Source files: 71 Python modules (excluding `__pycache__`)
> Total lines: ~10,125

---

## 1. Module Dependency Graph

### Package: `core/` — Agent, Session, Worker, Sub-Agent

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `core/agent.py` | `infrastructure.config`, `tools.register_all`, `tools.registry` | `core/worker.py`, `server/server.py` | **LOW** |
| `core/session.py` | `infrastructure.config`, `hooks`, `llm.models`, `infrastructure.prompt_loader`, `memory.memory` | `server/server.py` | **MED** |
| `core/worker.py` | `core.agent`, `infrastructure.bus`, `infrastructure.db`, `llm.models`, `core.subagent`, `infrastructure.utils.circuit`, `infrastructure.utils.retry` | `server/server.py` | **HIGH** |
| `core/subagent.py` | `llm.models` | `core/worker.py` | **LOW** |
| `core/graph.py` | `core.orchestration` | `core/worker.py` | **LOW** |
| `core/orchestration.py` | `llm.llm` | `core/graph.py` | **LOW** |

### Package: `tools/` — Tool Registration & Implementations

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `tools/register_all.py` | `tools.registry`, all tool modules | `core/agent.py` | **HIGH** |
| `tools/registry.py` (compat shim) | `tools.registry.*` | `core/agent.py`, `core/session.py`, `server/server.py`, `tools/register_all.py`, `sdk.py` | **HIGH** |
| `tools/registry/__init__.py` | `types`, `core`, `policy`, `search` | `tools/registry.py` | **MED** |
| `tools/registry/core.py` | `types`, `policy` (delayed) | `registry/__init__.py` | **LOW** |
| `tools/registry/policy.py` | `types`, `core` | `registry/__init__.py`, `core.py`, `search.py` | **MED** |
| `tools/registry/search.py` | `types`, `policy`, `core` | `registry/__init__.py` | **LOW** |
| `tools/registry/types.py` | (none internal) | `core.py`, `policy.py`, `search.py` | **HIGH** |
| `tools/fs.py` | — | `register_all.py`, `server/server.py` | **MED** |
| `tools/git.py` | — | `register_all.py` | **LOW** |
| `tools/shell.py` | — | `register_all.py` | **LOW** |
| `tools/research.py` | — | `register_all.py`, `orchestration.py` | **LOW** |
| `tools/code_search.py` | — | `register_all.py` | **LOW** |
| `tools/code_review.py` | — | `register_all.py` | **LOW** |
| `tools/test_runner.py` | — | `register_all.py` | **LOW** |
| `tools/patch.py` | — | `register_all.py` | **LOW** |
| `tools/write_todos.py` | — | `register_all.py` | **LOW** |

### Package: `memory/` — Two Memory Systems

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `memory/memory.py` | `llm.models`, `memory.index` | `core/session.py` | **MED** |
| `memory/memory_index.py` (compat shim) | `memory.index.*` | `memory/memory.py` | **LOW** |
| `memory/memory_files.py` | — | `memory/memory.py` | **LOW** |
| `memory/index/__init__.py` | `embeddings`, `index` | `memory_index.py` | **LOW** |
| `memory/index/embeddings.py` | `infrastructure.config` | `index.py`, `memory.py` | **MED** |
| `memory/index/index.py` | `embeddings` | `index/__init__.py` | **LOW** |
| `memory/compaction.py` | — | `core/session.py` | **LOW** |

### Package: `infrastructure/` — Config, DB, Bus, Auth, Utilities

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `infrastructure/config.py` | (none internal) | **14 modules** — nearly everything | **HIGH** |
| `infrastructure/bus.py` | `infrastructure.config` | `core/worker.py`, `server/server.py`, `server/sdk.py` | **HIGH** |
| `infrastructure/db/__init__.py` | `base`, `manager`, `models`, `session_repo`, `task_repo` | `worker.py`, `server.py` | **MED** |
| `infrastructure/db/manager.py` | `infrastructure.config`, `base` | `session_repo.py`, `task_repo.py` | **MED** |
| `infrastructure/db/session_repo.py` | `models` | `db/__init__.py` | **LOW** |
| `infrastructure/db/task_repo.py` | `models` | `db/__init__.py` | **LOW** |
| `infrastructure/db/models.py` | `base` | `session_repo.py`, `task_repo.py` | **MED** |
| `infrastructure/db/base.py` | — | `manager.py`, `models.py` | **MED** |
| `infrastructure/api_auth.py` | `infrastructure.auth` | `server/server.py` | **LOW** |
| `infrastructure/auth.py` | `infrastructure.config` | `api_auth.py` | **LOW** |
| `infrastructure/prompt_loader.py` | (none internal) | `core/session.py` | **LOW** |
| `infrastructure/utils/circuit.py` | (none internal) | `core/worker.py` | **LOW** |
| `infrastructure/utils/retry.py` | (none internal) | `core/worker.py`, `llm/llm.py` | **MED** |

### Package: `server/` — API and SDK

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `server/server.py` | `infrastructure.config`, `infrastructure.bus`, `infrastructure.api_auth`, `server.sdk`, `core.worker`, `core.agent`, `core.session`, `infrastructure.db`, `tools.registry`, `tools.fs` | (entry point) | **HIGH** |
| `server/sdk.py` | `infrastructure.bus`, `llm.models`, `core.worker`, `tools.registry` | `server/server.py` | **HIGH** |

### Package: `llm/` — LLM Provider

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `llm/llm.py` | `infrastructure.config`, `infrastructure.utils.retry` | `core/orchestration.py` | **LOW** |
| `llm/models.py` | (none internal) | `core/session.py`, `core/worker.py`, `core/subagent.py`, `memory/memory.py`, `server/sdk.py`, `interfaces/cli.py` | **HIGH** |

### Package: `interfaces/` — TUI and CLI

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `interfaces/tui.py` | `infrastructure.config` | (entry point) | **LOW** |
| `interfaces/cli.py` | `infrastructure.config`, `server.sdk`, `llm.models`, `core.worker` | (entry point) | **MED** |
| `interfaces/web_ui.py` | — | — | **LOW** |

### Package: `hooks/` — Event Hooks

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `hooks/__init__.py` | (none internal) | `core/session.py` | **LOW** |
| `hooks/builtins.py` | (none internal) | (loaded dynamically) | **LOW** |

### Package: `widgets/` — TUI Widgets

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `widgets/messages/*.py` | — | (used by TUI) | **LOW** |
| `widgets/theme/*.py` | — | (used by TUI) | **LOW** |

### Top-level modules

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `skills.py` | (none internal) | (loaded by agent) | **LOW** |
| `task_reaper.py` | `infrastructure.db` | (started by server) | **LOW** |

---

## 2. Data Flow Map

### 2.1 Interactive Chat Flow

```
User types message
       │
       ▼
┌──────────────────────────────────────────┐
│  NexusApp._input_queue (asyncio.Queue)   │  ← buffers if busy
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  _ws_loop → send_messages()              │
│  WebSocket: {"type":"user_input",        │
│              "content":"...",             │
│              "images":[...]}              │
└──────────────────┬───────────────────────┘
                   │ websockets (ws://127.0.0.1:8000/sessions/{id}/ws)
                   ▼
┌──────────────────────────────────────────┐
│  server.py: session_websocket()          │
│  1. Verify API key (query param)         │
│  2. Create Agent(role="full")            │
│  3. session_manager.get_or_create()      │
│  4. asyncio.gather(send_events,          │
│                     receive_messages)    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Session.send(user_message, images)      │
│  1. Fire session_init hooks              │
│  2. Process @file injection              │
│  3. Emit ThinkingEvent                   │
│  4. Store user msg in DB                 │
│  5. Build messages list:                 │
│     [System(prompt+context+memory),      │
│      ...,                                │
│      HumanMessage(text+images)]          │
│  6. Check compaction → CompactionPipeline│
│  7. agent({"messages": messages})        │
│  8. Extract response → ResponseEvent     │
│  9. Update conversation_history          │
│  10. Store assistant msg in DB           │
│  11. memory.remember()                   │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Agent.__call__() → deepagents          │
│  Uses _ROLE_TOOLS[role] as tool list     │
│  Policy enforced via thread-local ctx    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Tools execute (read_file, run_shell,    │
│  git_*, search_web, spawn_subagent...)   │
│  Each tool checks policy via             │
│  check_tool_access() or @require_policy  │
└──────────────────┬───────────────────────┘
                   │ events flow back via session._event_queue
                   ▼
┌──────────────────────────────────────────┐
│  TUI _handle_event() processes:          │
│  • thinking → italic dim text            │
│  • tool_call → ⚙ orange tool name        │
│  • tool_result → ✓/✗ green/red           │
│    (short=inline, long=collapsible)      │
│  • response_chunk → streaming widget     │
│  • response → final render + markdown    │
│  • error → red error message             │
│  • approval_request → modal dialog       │
└──────────────────────────────────────────┘
```

### 2.2 Asynchronous Task Flow (NATS)

```
SDK / CLI submits task
       │
       ▼
┌─────────────────────────────┐
│  sdk.submit_task()          │
│  Publish to NATS subject    │
│  "tasks.submit"             │
└──────────────┬──────────────┘
               │ NATS JetStream
               ▼
┌─────────────────────────────┐
│  NexusWorker.handle_task()  │
│  1. Parse TaskSchema         │
│  2. Create task in DB        │
│  3. Update → PROCESSING      │
│  4. Start heartbeat          │
│  5. _execute_agent_logic()   │
│     ├─ research → LangGraph  │
│     └─ code → deepagents     │
│  6. Save result → DB + KV    │
│  7. Update → COMPLETED       │
└─────────────────────────────┘
```

### 2.3 Session Lifecycle

```
Creation:
  TUI mounts → _ws_loop() connects → WebSocket handshake
  → Server creates Session(agent, working_dir, hybrid_memory)
  → DB row inserted (sessions table)

Message Loop:
  User input → Session.send() → agent invoke → events stream back
  → conversation_history accumulates (capped at max_conversation_history)

Compaction:
  CompactionPipeline.should_compact() checks token estimate
  → pre_compaction_flush() writes summary to hybrid memory
  → 4-level graduated compaction (clear → microcompact → summarize → truncate)
  → Rebuilt messages list passed to agent

Archival:
  On WebSocket disconnect → session_manager.mark_idle(session_id)
  → Status updated to "idle" in DB
  → Task reaper handles stale PROCESSING tasks

Fork/Rename/Delete:
  CLI session commands → session_repo.fork/rename/delete
```

### 2.4 Memory Flow

```
Write path:
  Session.send() → memory.remember(user_msg, {response})
    ↓
  HybridMemoryManager.remember(content, type, description)
    ↓
  FileMemory.write_entry() → bank/slug-timestamp.md
    ↓
  HybridMemoryIndex.async_index_file()
    ↓
  Chunk → Embed (Gemini → local → hash) → SQLite (chunks + chunks_fts + chunks_vec)

Recall path:
  Session.send() → hybrid_memory.get_memory_context(query)
    ↓
  HybridMemoryIndex.search_sync(query)
    ↓
  Parallel: FTS5 keyword search + sqlite-vec similarity search
    ↓
  Union merge (70% vector + 30% keyword weight)
    ↓
  Formatted as "## Relevant Memories\nSource: bank/file.md (score: 0.85)\n..."
    ↓
  Injected as SystemMessage into agent prompt

Compaction flush:
  CompactionPipeline.compact() triggers pre_compaction_flush()
    ↓
  HybridMemoryManager.flush(summary)
    ↓
  FileMemory.append_daily_log() → memory/YYYY-MM-DD.md
    ↓
  HybridMemoryIndex.async_index_file() re-indexes daily log
```

---

## 3. State Management

### NexusApp (TUI) — `interfaces/tui.py`

| State Variable | Type | Purpose |
|---|---|---|
| `_busy` | `bool` | Whether agent is currently processing |
| `_ws` | `WebSocketClientProtocol \| None` | Active WebSocket connection |
| `_collapsibles` | `list[Collapsible]` | Mounted Collapsible widgets for tool results |
| `_pending_inputs` | `list[str]` | Queued user messages while busy |
| `_streaming_response` | `str` | Accumulated streaming text |
| `_auto_approve` | `bool` | Auto-approve mode (Ctrl+_) |
| `_input_queue` | `asyncio.Queue[str\|None]` | Input buffer |
| `_current_task` | `asyncio.Task\|None` | For interrupt support |
| `_theme_index` | `int` | Current theme (cycles via /theme) |
| `_total_tokens_used` | `int` | Running token counter |
| `_request_count` | `int` | Number of agent requests |
| `_breakpoint` | `Breakpoint` | Responsive layout classification |
| `_resize_state` | `dict[str,float]` | Debounce state for SIGWINCH |
| `_auto_approve_task` | `asyncio.Task\|None` | Delayed auto-approval send |
| `_last_tool_name` | `str` | Last tool_call name (for result formatting) |

### Session — `core/session.py`

| State Variable | Type | Purpose |
|---|---|---|
| `session_id` | `str` | Unique session identifier |
| `working_dir` | `str` | File operation root |
| `agent` | `Agent` | The agent instance |
| `memory` | `Memory\|None` | Scoped SQLite memory instance |
| `hybrid_memory` | `HybridMemoryManager` | File + index memory |
| `db_repo` | `SessionRepository` | Session DB operations |
| `memory_dir` | `Path` | Session-specific memory directory |
| `status` | `str` | "active" / "idle" / "closed" |
| `_cancel_flag` | `bool` | Interruption signal |
| `_event_queue` | `asyncio.Queue[dict]` | Event stream for TUI |
| `_pending_approvals` | `dict[str, asyncio.Event]` | Approval waiters |
| `_approval_results` | `dict[str, bool]` | Approval outcomes |
| `_seen_tool_results` | `set[str]` | Dedup tool result events |
| `_seen_tool_calls` | `set[str]` | Dedup tool call events |
| `_conversation_history` | `list[Any]` | LangChain messages for continuity |
| `_cached_prompt` | `str` | Cached system prompt |

### SessionManager — `core/session.py` (module-level singleton)

| State Variable | Type | Purpose |
|---|---|---|
| `_sessions` | `dict[str, Session]` | Active sessions cache |
| `_current_session_id` | `str\|None` | Current focused session |

### WorkerPool — `core/worker.py`

| State Variable | Type | Purpose |
|---|---|---|
| `max_workers` | `int` | Concurrency limit (default 4) |
| `_active` | `dict[str, SubAgentHandle]` | Currently running workers |
| `_tasks` | `set[asyncio.Task]` | All spawned tasks |
| `_semaphore` | `asyncio.Semaphore` | Concurrency control |

### SubAgentHandle — `core/subagent.py`

| State Variable | Type | Purpose |
|---|---|---|
| `worker_id` | `str` | Unique worker ID |
| `contract` | `TaskContract` | Bounding contract |
| `depth` | `int` | Nesting depth (0 = top) |
| `_status` | `SubAgentStatus` | PENDING/RUNNING/COMPLETED/FAILED/CANCELLED |
| `_result` | `Any` | Full result |
| `_summary` | `str\|None` | Summary (if summary_only) |
| `_error` | `str\|None` | Error message |
| `_cancel_event` | `asyncio.Event` | Cancellation signal |
| `_done_event` | `asyncio.Event` | Completion signal |

### MemoryManager — `memory/memory.py`

| State Variable | Type | Purpose |
|---|---|---|
| `db_path` | `str` | SQLite file path |
| `_memories` | `dict[str, Memory]` | Active Memory instances |

### Memory (scoped SQLite) — `memory/memory.py`

| State Variable | Type | Purpose |
|---|---|---|
| `memory_id` | `str` | Memory scope identifier |
| `scope` | `MemoryScope` | SHARED/ISOLATED/SCOPED |
| `db_path` | `str` | SQLite file path |
| `parent_memory_id` | `str\|None` | Parent for scoped memories |
| `_conn` | `sqlite3.Connection\|None` | Database connection |

### HybridMemoryManager — `memory/memory.py`

| State Variable | Type | Purpose |
|---|---|---|
| `workspace_dir` | `str` | Root directory for memory files |
| `file_memory` | `FileMemory` | Canonical file-based memory |
| `index` | `HybridMemoryIndex` | Derived search index |

### CompactionPipeline — `memory/compaction.py`

| State Variable | Type | Purpose |
|---|---|---|
| `context_window_tokens` | `int` | Token threshold (default 200K) |
| `compaction_threshold` | `float` | Trigger at 75% of window |

### AgentBus — `infrastructure/bus.py`

| State Variable | Type | Purpose |
|---|---|---|
| `url` | `str` | NATS connection URL |
| `nc` | `NATSClient\|None` | NATS connection |
| `js` | `JetStream\|None` | JetStream context |
| `kv` | `KV\|None` | Key-value store |
| `_subscriptions` | `list[Subscription]` | Active subscriptions |

### LLMProvider — `llm/llm.py`

| State Variable | Type | Purpose |
|---|---|---|
| `gemini_key` | `str\|None` | Gemini API key |
| `openrouter_key` | `str\|None` | OpenRouter API key |
| `openrouter_client` | `AsyncOpenAI` | OpenRouter client instance |

---

## 4. Extension Points

### 4.1 New Tools
- **File**: `tools/register_all.py`
- **Pattern**: Import the function, wrap with `register_tool(name, description, parameters, example, category, returns)(func)`
- **Decoration style**: Can also use `@register_tool(name, ...)(func)` (see `spawn_subagent`)
- **Policy**: Add to appropriate role in `tools/registry/policy.py` → `ROLE_MANIFESTS`
- **Auto-correction**: `auto_correct()` in `tools/registry/core.py` handles fuzzy name matching

### 4.2 New Slash Commands
- **File**: `interfaces/tui.py` → `_handle_slash_command()` (line ~951)
- **Pattern**: Add `elif command == "/yourcmd":` block
- **Available**: `/help`, `/new`, `/clear`, `/expand`, `/collapse`, `/quit`, `/sessions`, `/status`, `/interrupt`, `/compact`, `/copy`, `/version`, `/auto`, `/tokens`, `/model`, `/threads`
- **TODO**: `/copy` is not implemented; `/sessions` and `/threads` are stubs

### 4.3 New Themes
- **File**: `interfaces/tui.py` → `NEXUS_THEMES` (line ~53)
- **Pattern**: Append dict: `{"name": "theme_name", "header_bg": "#hex", "accent": "#hex", "bg": "#hex"}`
- **Cycling**: Use `/theme` (not yet bound) or cycle via settings

### 4.4 New Widgets
- **File**: `interfaces/tui.py` → `NexusApp.compose()` (line ~452)
- **Pattern**: Add `yield` statements in compose(), then `query_one()` in `on_mount()`
- **Existing widgets**: Header, ScrollableContainer (RichLog), Static (streaming), SpinnerLabel, Static (auto-approve badge, queue status), Input, Footer
- **Messages**: `widgets/messages/` has user/assistant/tool/error/app/welcome renderers

### 4.5 New LLM Providers
- **File**: `llm/llm.py` → `LLMProvider`
- **Pattern**: Add `self.*_key` and `self.*_client` in `__init__()`, add branch in `get_active_model()`, add `_call_*()` method with `@retry_with_backoff`
- **Config**: Add fields to `AgentConfig` in `infrastructure/config.py`

### 4.6 New Hooks
- **File**: `hooks/__init__.py` → `HookEvent` enum + `register_hook()`
- **Pattern**: Append to `HookEvent` StrEnum, implement async callback, register via `register_hook(event, callback)`
- **Built-in hooks**: `hooks/builtins.py` has session_init_load_context, post_tool_use_telemetry, error_log_to_file, subagent_start_log, subagent_stop_log

### 4.7 New Memory Embedding Providers
- **File**: `memory/index/embeddings.py` → `EmbeddingProvider`
- **Pattern**: Add new `_embed_*()` method, insert into the fallback chain in `embed()`

### 4.8 New API Endpoints
- **File**: `server/server.py`
- **Pattern**: Add FastAPI route decorators (`@app.get`, `@app.post`, etc.)
- **Auth**: Use `dependencies=[Depends(verify_api_key)]` for protected endpoints

### 4.9 New CLI Commands
- **File**: `interfaces/cli.py`
- **Pattern**: Add `@main.command()` or `@main.group()` decorated functions
- **Existing groups**: `main`, `hooks` (with `hooks list`, `hooks enable`, `hooks disable`)

### 4.10 Skills
- **File**: `skills.py`
- **Pattern**: Add `Skill` subclass or extend `load_all_skills()` to scan additional directories
- **SKILL.md format**: YAML frontmatter with `name` and `description`, then markdown body

---

## 5. Known Technical Debt

### 5.1 Hardcoded Values That Should Be Configurable

| Location | Issue | Suggested Fix |
|---|---|---|
| `infrastructure/config.py:40` | `default_model = "gemini-3.1-flash-lite"` hardcoded | Make overridable via AGENT_MODEL env var (partially done in agent.py) |
| `tui.py:53-59` | `NEXUS_THEMES` hardcoded inline | Move to config file or `config/nexusagent.yaml` |
| `tui.py:131-133` | Breakpoint thresholds (120/80/60) hardcoded | Add to ClientConfig |
| `memory/memory.py:25-29` | Memory index limits (200 lines, 25KB) hardcoded | Add to config |
| `memory/compaction.py:37-38` | `context_window_tokens=200_000`, `compaction_threshold=0.75` hardcoded | Add to AgentConfig |
| `core/worker.py:211` | `WorkerPool.max_workers=4` hardcoded | Add to ServerConfig |
| `server/server.py:350` | `uvicorn.run(host="0.0.0.0", port=...)` host hardcoded | Add `server_host` to config |
| `bus.py:52` | NATS bucket name `"nexus_results"` hardcoded | Add to ServerConfig |
| `memory/index/embeddings.py:23-28` | EMBED_DIM, CHUNK_SIZE, CHUNK_OVERLAP, weights hardcoded | Add to config |
| `session.py:185` | Session memory dir path `~/.nexusagent/sessions/{id}/memory` hardcoded | Add to config |
| `tools/registry/policy.py:60-176` | `ROLE_MANIFESTS` entirely hardcoded | Externalize to YAML config |

### 5.2 Duplicated Code Between Modules

| Duplication | Modules | Notes |
|---|---|---|
| Memory system | `memory/memory.py` (SQLite+sqlite-vec) vs `memory/memory_files.py` + `memory/index/` (FTS5+sqlite-vec) | Two parallelMemory implementations coexist. Session uses the file-based hybrid; the SQLite `Memory` class exists but is less used |
| `list_tools()` | `tools/registry/core.py:47` (server-side) and `tools/registry/search.py:73` (discovery) | Both iterate `_REGISTRY` |
|| `register_tool` compat | `tools/registry.py` re-exports everything from `tools/registry/` subpackage | Unnecessary compat shim — migrate all imports to subpackage directly |
|| Tool output formatting | `_format_tool_output()` in `tui.py:880-936` duplicates logic from `register_all.py` examples | Formatter reconstructs display from raw tool output strings |
|| Frontend rendering | `tui.py` has inline Rich markup rendering; `widgets/messages/` has separate renderers | Two rendering approaches exist. TUI handles messages inline but widgets exist for modular rendering |
|| Config loading | `config.py` loads YAML; `cli.py` loads `pyproject.toml` via `tomllib` | Version info duplicated across config.yaml and pyproject.toml |
|| Embedding fallback | `_hash_embed()` in `memory/memory.py:32` and `_embed_hash()` in `memory/index/embeddings.py:112` are nearly identical | Both produce SHA256-based deterministic vectors |

### 5.3 Missing Error Handling

| Location | Issue |
|---|---|
| `core/worker.py:121-201` | `handle_task()` outer except block swallows errors during error reporting (lines 180-201) — if `task_repo.update_task_status` fails in the except block, the error is logged but the NATS message is lost |
| `server/server.py:239-343` | WebSocket endpoint has no rate limiting on message types — a malicious client could flood with `user_input` messages |
| `memory/index/index.py:463-498` | `_search_vector_brute()` OOM guard checks system memory but doesn't account for concurrent brute-force searches |
| `infrastructure/auth.py:38-44` | `_get_master_key()` reads secret file on every call if `master_secret_path` doesn't exist — no caching, repeated FileNotFoundError I/O |
| `core/session.py:303-443` | `send()` method has 7+ try/except blocks with independent failure modes — if memory recall fails, the agent still proceeds (correct) but the error context is lost |
| `tui.py:601-642` | `_ws_loop()` reconnect logic is absent — on disconnect, the TUI shows "Disconnected" with no auto-reconnect |

### 5.4 Test Coverage Gaps

| Area | Notes |
|---|---|
| **TUI** | No tests for `NexusApp` — 1433-line monolith is untested. Widget interaction, event handling, slash commands, SIGWINCH all need coverage |
| **WebSocket protocol** | No integration tests for the WebSocket session lifecycle (connect → message → compact → disconnect) |
| **CompactionPipeline** | `memory/compaction.py` has no tests — the 4-level graduated compaction is complex and error-prone |
| **Policy enforcement** | `tools/registry/policy.py` role manifests and `_is_tool_allowed()` have no parameterized tests across all role/policy combinations |
| **Memory dual-system** | Both `Memory` (SQLite) and `FileMemory`/`HybridMemoryIndex` (file-based) exist untested |
| **NATS bus** | `infrastructure/bus.py` has no unit tests — circuit breaker integration with NATS is untested |
| **Graph workflow** | `core/graph.py` LangGraph research workflow has no tests for node routing or checkpoint resume |
| **CLI** | `interfaces/cli.py` commands are no-test — click commands need CliRunner tests |
| **SDK** | `server/sdk.py` `submit_and_wait()` polling loop is untested, especially timeout behavior |
| **Hooks** | `hooks/__init__.py` event firing and error isolation (one hook failing shouldn't stop others) is untested |

### 5.5 Architectural Concerns

| Issue | Description |
|---|---|
| **Circular compat shims** | `tools/registry.py` and `memory/memory_index.py` are compat shims that re-export from subpackages. This creates confusing import paths and should be cleaned up |
| **Two memory systems** | `memory/memory.py` (old SQLite `Memory` class) vs `memory/memory_files.py` + `memory/index/` (new file-based hybrid). Session.py imports `HybridMemoryManager` from `memory/memory.py` which internally imports from `memory/memory_files.py` — the old `Memory`/`MemoryManager` classes are dead code |
| **TUI monolith** | `tui.py` at 1433 lines handles WebSocket, event dispatch, display formatting, slash commands, theming, responsive layout, and modal dialogs. Should be split into separate modules |
| **Missing `/theme` command** | `/theme` cycling is mentioned in docs but not implemented in `_handle_slash_command()` only `/version` shows theme |
| **No connection retry in TUI** | Unlike `AgentBus.subscribe()` which retries 3x, the TUI WebSocket gives up after one `ConnectionRefusedError` |
| **Global mutable singletons** | `settings`, `sdk`, `worker`, `worker_pool`, `llm`, `db_manager`, `task_repo`, `session_repo`, `auth_manager`, `_manager` (hooks), `_default_bus` are all module-level mutable singletons — makes testing and concurrent use difficult |
| **Gemma model prefix hack** | `core/agent.py:89-90` has special-case logic for Gemma/Gemini model name prefixing that's fragile and undocumented |
| **YAML frontmatter in memory files** | `memory/memory_files.py` uses custom YAML frontmatter parsing that doesn't handle all YAML edge cases |