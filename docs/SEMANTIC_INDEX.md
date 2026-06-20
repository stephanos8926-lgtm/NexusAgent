# NexusAgent Semantic Codebase Index

> Generated: 2026-07-22
> Source files: 106 Python modules (excluding `__pycache__`)
> Total lines: ~18,500 (src), ~9,500 (tests)
> Test baseline: 680 pass / 11 pre-existing fail

---

## 1. Module Dependency Graph

### Package: `core/` — Agent, Session, Worker, Sub-Agent

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `core/agent.py` | `infrastructure.config`, `tools.register_all`, `tools.registry` | `core/worker/worker.py`, `core/orchestration.py` | **LOW** |
| `core/orchestration.py` | `llm.llm` | `core/graph.py` | **LOW** |
| `core/graph.py` | `core.orchestration` | `core/worker/handler.py` | **LOW** |
| `core/subagent.py` | `llm.models` | `core/worker/pool.py` | **LOW** |
| `core/session/session.py` | `infrastructure.config`, `hooks`, `llm.models`, `infrastructure.prompt_loader`, `memory.hybrid_memory`, `memory.compaction` | `server/websocket.py` | **MED** |
| `core/session/manager.py` | `core/session/session.py`, `infrastructure.db` | `server/websocket.py` | **MED** |
| `core/session/helpers.py` | `llm.models` | `core/session/session.py` | **LOW** |
| `core/worker/worker.py` | `core/agent`, `infrastructure.bus`, `infrastructure.db`, `llm.models`, `core/subagent`, `infrastructure.utils.circuit`, `infrastructure.utils.retry` | (entry point) | **HIGH** |
| `core/worker/pool.py` | `core/worker/worker.py`, `core/subagent` | `interfaces/cli.py` | **MED** |
| `core/worker/handler.py` | `core/agent`, `core/graph` | `core/worker/worker.py` | **MED** |

### Package: `tools/` — Tool Registration & Implementations

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `tools/register_all.py` | `tools.registry`, all tool modules | `core/agent.py` | **HIGH** |
| `tools/registry/core.py` | `types`, `policy` (delayed) | `registry/__init__.py` | **LOW** |
| `tools/registry/policy.py` | `types`, `core` | `registry/__init__.py`, `core.py`, `search.py` | **MED** |
| `tools/registry/search.py` | `types`, `policy`, `core` | `registry/__init__.py` | **LOW** |
| `tools/fs.py` | `fs_base` | `register_all.py` | **MED** |
| `tools/fs_base.py` | `infrastructure.config` | `fs.py` | **LOW** |
| `tools/editor.py` | `fs_base` | `register_all.py` | **LOW** |
| `tools/git.py` | `fs_base` | `register_all.py` | **LOW** |
| `tools/shell.py` | `infrastructure.config` | `register_all.py` | **LOW** |
| `tools/research.py` | — | `register_all.py`, `orchestration.py` | **LOW** |
| `tools/code_search.py` | — | `register_all.py` | **LOW** |
| `tools/code_review/` | — | `register_all.py` | **LOW** |
| `tools/test_runner.py` | — | `register_all.py` | **LOW** |
| `tools/patch.py` | — | `register_all.py` | **LOW** |
| `tools/write_todos.py` | — | `register_all.py` | **LOW** |

### Package: `memory/` — Hybrid Memory System v2

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `memory/hybrid_memory.py` | `memory.memory_files`, `memory.index`, `memory.extraction`, `memory.rate_limiter` | `core/session/session.py` | **HIGH** |
| `memory/memory_files.py` | `memory.git_ops` | `memory/hybrid_memory.py` | **MED** |
| `memory/index/index.py` | `memory/index/embeddings.py` | `memory/hybrid_memory.py` | **MED** |
| `memory/index/embeddings.py` | `infrastructure.config` | `memory/index/index.py` | **MED** |
| `memory/compaction.py` | `memory.dag` | `core/session/session.py` | **LOW** |
| `memory/dag.py` | — | `memory/compaction.py` | **LOW** |
| `memory/dream.py` | `memory.git_ops`, `memory.refinement` | (triggered by session turns) | **LOW** |
| `memory/extraction.py` | — | `memory/hybrid_memory.py` | **LOW** |
| `memory/git_ops.py` | — | `memory/memory_files.py`, `memory/dream.py` | **LOW** |
| `memory/rate_limiter.py` | — | `memory/hybrid_memory.py` | **LOW** |
| `memory/consolidation.py` | — | (standalone daemon) | **LOW** |
| `memory/refinement.py` | `llm.llm` | `memory/dream.py` | **LOW** |

### Package: `infrastructure/` — Config, DB, Bus, Auth, Utilities

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `infrastructure/config.py` | (none internal) | **14 modules** — nearly everything | **HIGH** |
| `infrastructure/bus.py` | `infrastructure.config` | `core/worker/worker.py`, `server/sdk.py` | **HIGH** |
| `infrastructure/db/manager.py` | `infrastructure.config`, `base` | `session_repo.py`, `task_repo.py` | **MED** |
| `infrastructure/db/session_repo.py` | `models` | `db/__init__.py` | **LOW** |
| `infrastructure/db/task_repo.py` | `models` | `db/__init__.py` | **LOW** |
| `infrastructure/db/models.py` | `base` | `session_repo.py`, `task_repo.py` | **MED** |
| `infrastructure/api_auth.py` | `infrastructure.auth` | `server/server.py` | **LOW** |
| `infrastructure/auth.py` | `infrastructure.config` | `api_auth.py` | **LOW** |
| `infrastructure/prompt_loader.py` | `infrastructure.template_includes` | `core/session/session.py` | **LOW** |
| `infrastructure/template_includes.py` | — | `infrastructure/prompt_loader.py` | **LOW** |
| `infrastructure/rate_limit.py` | `infrastructure.config` | `server/server.py` | **LOW** |
| `infrastructure/utils/circuit.py` | (none internal) | `core/worker/worker.py` | **LOW** |
| `infrastructure/utils/retry.py` | (none internal) | `core/worker/worker.py`, `llm/llm.py` | **MED** |

### Package: `server/` — API, SDK, WebSocket, Version

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `server/server.py` | `infrastructure.config`, `infrastructure.bus`, `infrastructure.api_auth`, `server.sdk`, `server.version`, `core/worker`, `infrastructure.db`, `tools.registry`, `infrastructure.rate_limit`, `infrastructure.prompt_loader` | (entry point) | **HIGH** |
| `server/sdk.py` | `infrastructure.bus`, `llm.models`, `core/worker`, `tools.registry`, `server.version` | `server/server.py`, `interfaces/cli.py` | **HIGH** |
| `server/websocket.py` | `core/session`, `core/agent`, `infrastructure.db`, `server.version` | `server/server.py` | **HIGH** |
| `server/routes.py` | `infrastructure.db`, `core/worker`, `tools.registry`, `server.version` | `server/server.py` | **MED** |
| `server/version.py` | (none internal) | `server/server.py`, `server/sdk.py`, `interfaces/cli.py`, `interfaces/tui/websocket.py` | **HIGH** |

### Package: `llm/` — LLM Provider

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `llm/llm.py` | `infrastructure.config`, `infrastructure.utils.retry` | `core/orchestration.py`, `memory/refinement.py` | **LOW** |
| `llm/models.py` | (none internal) | `core/session`, `core/worker`, `core/subagent`, `server/sdk.py` | **HIGH** |

### Package: `interfaces/` — TUI subpackage, CLI, Web UI

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `interfaces/tui/app.py` | `interfaces/tui/streaming.py`, `interfaces/tui/websocket.py`, `interfaces/tui/input.py`, `interfaces/tui/formatters.py`, `widgets/*` | (entry point) | **MED** |
| `interfaces/tui/websocket.py` | `server/version.py` | `interfaces/tui/app.py` | **MED** |
| `interfaces/tui/streaming.py` | `widgets/messages/*`, `widgets/status` | `interfaces/tui/app.py` | **MED** |
| `interfaces/cli.py` | `server.sdk`, `llm.models`, `core/worker/pool`, `server/version` | (entry point) | **MED** |
| `interfaces/web_ui.py` | — | — | **LOW** |

### Package: `hooks/` — Event Hooks

| Module | Imports From (fan-in) | Imported By (fan-out) | Risk |
|---|---|---|---|
| `hooks/__init__.py` | — | `core/session/session.py` | **LOW** |
| `hooks/builtins.py` | — | `hooks/__init__.py` (loaded dynamically) | **LOW** |

---

## 2. Data Flow Map

### 2.1 Interactive Chat Flow (TUI → WebSocket → Session)

```
User types message
       │
       ▼
┌──────────────────────────────────────────┐
│  ChatInput.action_submit()               │  [interfaces/tui/input.py]
│  → NexusApp.on_chat_input_submitted()    │  [interfaces/tui/streaming.py]
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ws_loop → WebSocket send                │  [interfaces/tui/websocket.py]
│  {"type":"user_input", "content":"..."}  │
└──────────────────┬───────────────────────┘
                   │ ws://127.0.0.1:8000/sessions/{id}/ws
                   ▼
┌──────────────────────────────────────────┐
│  websocket.py: session_websocket()       │
│  1. Verify API key (header)              │
│  2. get_or_create session                │
│  3. asyncio.gather(send_events,          │
│                     receive_messages)    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Session.send(user_message, images)      │  [core/session/session.py]
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
│  11. hybrid_memory.remember()            │
│  12. Schedule _run_extraction()          │
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
│  stream back via session._event_queue    │
│  TUI _handle_event() processes:          │
│  • thinking → italic dim text            │
│  • tool_call → ⚙ orange tool name        │
│  • tool_result → ✓/✗ green/red           │
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

### 2.3 Memory System v2 Flow

```
Write path (after each turn):
  Session.send() → memory.remember(user_msg, {response})
    ↓
  HybridMemoryManager.remember(content, type, description)
    ↓
  MemoryRateLimiter.acquire(write=True)  # token-bucket
    ↓
  FileMemory.write_entry() → bank/slug-timestamp.md
    ↓
  MemoryGitOps.auto_commit() → git add + git commit (rate-limited)
    ↓
  HybridMemoryIndex.async_index_file()
    ↓
  Chunk → Embed (Gemini → local → hash) → SQLite (chunks + chunks_fts + chunks_vec)

  Fire-and-forget:
  MemoryExtractor.extract() → regex patterns → observation entries

Recall path (before agent call):
  Session.send() → hybrid_memory.get_memory_context(query)
    ↓
  HybridMemoryIndex.search(query)
    ↓
  Parallel: FTS5 keyword + sqlite-vec similarity → RRF fusion
    ↓
  Formatted as "## Relevant Memories\n..." → SystemMessage

Background (DreamCycle):
  Every N turns → DreamCycle.run()
    ↓
  Phase 1 Scan: Read all memory files, compute hashes
    ↓
  Phase 2 Patterns: LLMRefinement.synthesize() → insight entries
    ↓
  Phase 3 Consolidate: Dedup, prune stale, resolve contradictions
    ↓
  Phase 4 Trim: Rebuild index, trim MEMORY.md to ≤200 lines

Background (ConsolidationEngine):
  Periodic scan → duplicate detection, contradiction resolution, stale pruning
    ↓
  FileMemory.merge_entries() + index rebuild

Compaction flush:
  CompactionPipeline.compact() → pre_compaction_flush()
    ↓
  HybridMemoryManager.flush(summary)
    ↓
  FileMemory.append_daily_log() → memory/YYYY-MM-DD.md
    ↓
  Bi-temporal fields: valid_from, valid_until for time-based queries
    ↓
  TTL enforcement: check-on-read + periodic sweep_expired()
```

### 2.4 Session Lifecycle

```
Creation:
  TUI mounts → ws_loop() connects → WebSocket handshake
  → Server creates Session(agent, working_dir, hybrid_memory)
  → DB row inserted (sessions table, memory_dir column)

Message Loop:
  User input → Session.send() → agent invoke → events stream back
  → conversation_history accumulates (capped at max_conversation_history)

Compaction:
  CompactionPipeline.should_compact() checks token estimate
  → SummaryDAG compresses old messages (depth-0 → depth-1 → depth-2)
  → pre_compaction_flush() writes summary to hybrid memory
  → 4-level graduated compaction

Archival:
  On WebSocket disconnect → session_manager.mark_idle(session_id)
  → hybrid_memory.close() → release DB connections
  → Task reaper handles stale PROCESSING tasks

Workspace Scoping:
  _setup_workspace_context(working_dir)
  → Path jail for fs/shell tools
  → thread-local _ws_memory_dir
  → Loads NEXUS.md from workspace
  → Injects workspace context into env
```

### 2.5 Version Check Flows

```
CLI Preflight:
  cli.py → HTTP GET /version → parse_version()
  → Major mismatch = warn; --skip-version-check to bypass

TUI Preflight:
  NexusApp.on_mount() → httpx GET /version
  → Mismatch → warning banner (non-blocking)

SDK:
  NexusSDK.health_check() → returns SERVER_VERSION + MIN_CLIENT_VERSION
```

---

## 3. State Management

### NexusApp (TUI) — `interfaces/tui/app.py`

| State Variable | Type | Purpose |
|---|---|---|
| `_busy` | `bool` | Whether agent is currently processing |
| `_ws` | `WebSocketClientProtocol \| None` | Active WebSocket connection |
| `_collapsibles` | `list[Collapsible]` | Mounted Collapsible widgets for tool results |
| `_pending_inputs` | `list[str]` | Queued user messages while busy |
| `_streaming_response` | `str` | Accumulated streaming text |
| `_auto_approve` | `bool` | Auto-approve mode |
| `_input_queue` | `asyncio.Queue[str\|None]` | Input buffer |
| `_current_task` | `asyncio.Task\|None` | For interrupt support |
| `_theme_index` | `int` | Current theme (cycles via /theme) |
| `_total_tokens_used` | `int` | Running token counter |
| `_request_count` | `int` | Number of agent requests |
| `_breakpoint` | `Breakpoint` | Responsive layout classification |
| `_resize_state` | `dict[str,float]` | Debounce state for SIGWINCH |
| `_last_tool_name` | `str` | Last tool_call name (for result formatting) |

### Session — `core/session/session.py`

| State Variable | Type | Purpose |
|---|---|---|
| `session_id` | `str` | Unique session identifier |
| `working_dir` | `str` | File operation root |
| `memory_dir` | `Path` | Session-specific memory directory |
| `agent` | `Agent` | The agent instance |
| `hybrid_memory` | `HybridMemoryManager` | File + index memory |
| `db_repo` | `SessionRepository` | Session DB operations |
| `status` | `str` | "active" / "idle" / "closed" |
| `_cancel_flag` | `bool` | Interruption signal |
| `_event_queue` | `asyncio.Queue[dict]` | Event stream for TUI |
| `_pending_approvals` | `dict[str, asyncio.Event]` | Approval waiters |
| `_conversation_history` | `list[Any]` | LangChain messages for continuity |
| `_cached_prompt` | `str` | Cached system prompt |
| `_ws_context` | `_WorkspaceContext` | Thread-local workspace scope |

### WorkerPool — `core/worker/pool.py`

| State Variable | Type | Purpose |
|---|---|---|
| `max_workers` | `int` | Concurrency limit (default 4) |
| `_active` | `dict[str, SubAgentHandle]` | Currently running workers |
| `_semaphore` | `asyncio.Semaphore` | Concurrency control |

### HybridMemoryManager — `memory/hybrid_memory.py`

| State Variable | Type | Purpose |
|---|---|---|
| `workspace_dir` | `str` | Root directory for memory files |
| `file_memory` | `FileMemory` | Canonical file-based memory |
| `index` | `HybridMemoryIndex` | Derived search index |
| `_extractor` | `MemoryExtractor` | Regex-based auto-extraction |
| `_rate_limiter` | `MemoryRateLimiter` | Token-bucket rate limiting |
| `_last_dream_turn` | `int` | Turn counter for dream cycle trigger |

### CompactionPipeline — `memory/compaction.py`

| State Variable | Type | Purpose |
|---|---|---|
| `context_window_tokens` | `int` | Token threshold (default 200K) |
| `compaction_threshold` | `float` | Trigger at 75% of window |
| `dag` | `SummaryDAG` | Hierarchical compression DAG |

### DreamCycle — `memory/dream.py`

| State Variable | Type | Purpose |
|---|---|---|
| `workspace_dir` | `str` | Memory workspace root |
| `llm_refinement` | `LLMRefinement` | Optional LLM synthesis layer |
| `git_ops` | `MemoryGitOps` | Auto-commit after consolidation |
| `_file_lock` | `asyncio.FileLock` | Prevents concurrent consolidation |

### LLMProvider — `llm/llm.py`

| State Variable | Type | Purpose |
|---|---|---|
| `gemini_key` | `str\|None` | Gemini API key |
| `openrouter_key` | `str\|None` | OpenRouter API key |
| `openrouter_client` | `AsyncOpenAI` | OpenRouter client instance |

### AgentBus — `infrastructure/bus.py`

| State Variable | Type | Purpose |
|---|---|---|
| `url` | `str` | NATS connection URL |
| `nc` | `NATSClient\|None` | NATS connection |
| `js` | `JetStream\|None` | JetStream context |
| `kv` | `KV\|None` | Key-value store |
| `_subscriptions` | `list[Subscription]` | Active subscriptions |

---

## 4. Extension Points

### 4.1 New Tools
- **File**: `tools/register_all.py`
- **Pattern**: Import the function, wrap with `register_tool(name, description, parameters, example, category, returns)(func)`
- **Policy**: Add to appropriate role in `tools/registry/policy.py` → `ROLE_MANIFESTS`

### 4.2 New Slash Commands
- **File**: `interfaces/tui/streaming.py` → `handle_slash_command()`
- **Pattern**: Add `elif command == "/yourcmd":` block
- **Available**: `/help`, `/new`, `/clear`, `/expand`, `/collapse`, `/quit`, `/sessions`, `/status`, `/interrupt`, `/compact`, `/copy`, `/version`, `/auto`, `/tokens`, `/model`, `/threads`

### 4.3 New Themes
- **File**: `widgets/theme/colors.py`
- **Pattern**: Add `ThemeColors` instance to `register_themes()` in `widgets/theme/registry.py`
- **Available**: 7 themes — nexus-dark, catppuccin-mocha, gruvbox-dark, nord, solarized, dracula, monokai

### 4.4 New LLM Providers
- **File**: `llm/llm.py` → `LLMProvider`
- **Pattern**: Add branch in `generate()`, add `_call_*()` method with `@retry_with_backoff`
- **Config**: Add fields to `AgentConfig` in `infrastructure/config.py`

### 4.5 New Hooks
- **File**: `hooks/__init__.py` → `HookEvent` enum + `register_hook()`
- **Pattern**: Append to `HookEvent` StrEnum, implement async callback

### 4.6 New Memory Embedding Providers
- **File**: `memory/index/embeddings.py` → `EmbeddingProvider`
- **Pattern**: Add new `_embed_*()` method, insert into the fallback chain

### 4.7 New API Endpoints
- **File**: `server/routes.py`
- **Pattern**: Add FastAPI route decorators with `dependencies=[Depends(verify_api_key)]`

### 4.8 New CLI Commands
- **File**: `interfaces/cli.py`
- **Pattern**: Add `@main.command()` or `@main.group()` decorated functions

### 4.9 Version Management
- **File**: `version.py` — single source of truth via `importlib.metadata`
- **Functions**: `get_version()`, `parse_version()`, `is_compatible()`

### 4.10 Memory System Extensions
- **Dream cycle hooks**: Register callbacks on `DreamCycle` for custom consolidation logic
- **Custom extraction patterns**: Extend `MemoryExtractor.patterns` with new regex
- **Embedding providers**: Implement new `EmbeddingProvider` subclass

---

## 5. Known Technical Debt

### 5.1 Hardcoded Values That Should Be Configurable

| Location | Issue | Suggested Fix |
|---|---|---|
| `config.py:40` | `default_model` hardcoded | Make overridable via AGENT_MODEL env var |
| `tui/app.py` | Theme list hardcoded inline | Move to config file |
| `memory/compaction.py` | Context window thresholds hardcoded | Add to AgentConfig |
| `core/worker/pool.py` | `max_workers=4` hardcoded | Add to ServerConfig |
| `bus.py` | NATS bucket name hardcoded | Add to ServerConfig |
| `memory/index/embeddings.py` | EMBED_DIM, CHUNK_SIZE hardcoded | Add to config |
| `tools/registry/policy.py` | ROLE_MANIFESTS hardcoded | Externalize to YAML config |

### 5.2 Duplicated Code Between Modules

| Duplication | Modules | Notes |
|---|---|---|
| Embedding fallback | `memory/memory.py` `_hash_embed()` and `memory/index/embeddings.py` `_embed_hash()` | Both produce SHA256-based deterministic vectors |
| Tool output formatting | `tui/streaming.py` and `tools/register_all.py` examples | Formatter reconstructs display from raw tool output |

### 5.3 Missing Error Handling

| Location | Issue |
|---|---|
| `core/worker/handler.py` | Outer except block swallows errors during error reporting |
| `server/server.py` | WebSocket endpoint has no rate limiting on message types |
| `core/session/session.py` | `send()` method has 7+ try/except blocks with independent failure modes |

### 5.4 Test Coverage Gaps

| Area | Notes |
|---|---|
| **CompactionPipeline** | Complex 4-level graduated compaction needs more edge-case tests |
| **DreamCycle** | 4-phase consolidation daemon — only basic tests |
| **ConsolidationEngine** | Duplicate/contradiction detection untested |
| **LLMRefinement** | LLM synthesis layer untested |
| **Memory dual-system** | Both `Memory` (SQLite) and `FileMemory`/`HybridMemoryIndex` exist — old `Memory` class is dead code |
| **NATS bus** | Circuit breaker integration with NATS is untested |
| **CLI** | Click commands need CliRunner tests |
| **SDK** | `submit_and_wait()` polling loop untested for timeout |

### 5.5 Architectural Concerns

| Issue | Description |
|---|---|
| **Two memory systems** | `memory/memory.py` (old SQLite `Memory` class) is dead code — only `HybridMemoryManager` (file+index) is used by sessions |
| **Circular compat shims** | `tools/registry.py`, `memory/memory_index.py`, `memory/memory.py` are compat shims that re-export from subpackages |
| **Global mutable singletons** | `settings`, `sdk`, `worker_pool`, `llm`, `db_manager`, etc. at module level — makes testing difficult |
| **No connection retry in TUI** | WebSocket gives up after one `ConnectionRefusedError` |
