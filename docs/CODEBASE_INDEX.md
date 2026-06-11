# NexusAgent Codebase Semantic Index

> **Generated**: 2026-06-11
> **Version**: 0.1.0
> **Python**: >=3.13

---

## Architecture Overview

NexusAgent is an LLM-powered autonomous coding agent with a rich terminal UI (TUI), multi-agent orchestration, and a plugin-based tool system. The architecture follows a layered design:

```
User Input (TUI / CLI / WebSocket / Gradio)
        │
        ▼
┌──────────────────┐
│   CLI / Server   │  click commands + FastAPI REST/WebSocket
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Session Manager  │  message flow, event streaming, compaction
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Agent (deepagents) │  LLM reasoning loop + policy-aware tool access
└────────┬─────────┘
         ▼
┌──────────────────────────────────┐
│  Tool Registry + Registered Tools  │  fs, shell, git, search, patch, tests, research, memory
└────────┬─────────────────────────┘
         ▼
┌──────────────────┐
│   LLM Provider   │  Gemini / OpenRouter (OpenAI-compatible)
└──────────────────┘
```

**Key subsystems:**
- **TUI** (`tui.py`): Textual-based terminal UI with streaming messages, status bar, theme system
- **Server** (`server.py`): FastAPI REST API + WebSocket for interactive sessions
- **SDK** (`sdk.py`): High-level client for task submission and orchestration
- **Bus** (`bus.py`): NATS messaging backbone for task distribution
- **Worker** (`worker.py`): Task execution engine with circuit breakers and worker pools
- **Sub-agents** (`subagent.py`): Nested agent spawning with depth-limited trees
- **Memory** (`memory_files.py` + `memory.py` + `memory_index.py`): Hybrid file+vector memory system
- **Hooks** (`hooks/`): Extensible lifecycle event system
- **Orchestration** (`orchestration.py` + `graph.py`): Deep research state machine via LangGraph

---

## Module Map

### `__init__.py` — `src/nexusagent/__init__.py`
- **Role**: Package marker (empty).
- **Dependencies**: None

### `main.py` — `/home/sysop/Workspaces/NexusAgent/main.py`
- **Role**: `python -m nexusagent` entrypoint. Delegates to `cli.main()`.
- **Dependencies**: `nexusagent.cli`

---

### `config` — `src/nexusagent/config.py`
- **Role**: Configuration loading from `config/nexusagent.yaml` with environment variable overrides. Defines the full configuration schema using Pydantic models.
- **Key Classes**:
  - `ServerConfig(BaseModel)` — NATS URL, DB path, API port, worker threads, reconnect settings
  - `ClientConfig(BaseModel)` — TUI theme, timeouts, retry limits, API key, responsive mode
  - `AuthConfig(BaseModel)` — Master secret path, keystore path, KDF settings
  - `AgentConfig(BaseModel)` — Default model, provider, tool output limits, compaction, image settings
  - `PromptConfig(BaseModel)` — Base prompt file, NEXUS.md loading, @file injection settings
  - `LoggingConfig(BaseModel)` — Log level and format
  - `HooksConfig(BaseModel)` — Hooks enable/disable, hooks directory
  - `ConfigSchema(BaseModel)` — Top-level config aggregating all sub-configs
- **Key Functions**:
  - `get_project_root() -> Path` — Resolves project root relative to source
  - `load_config(config_file: str) -> ConfigSchema` — Loads YAML + env overrides
- **Dependencies**: `yaml`, `pydantic`
- **Consumed By**: Almost every module (`settings` singleton)

### `models` — `src/nexusagent/models.py`
- **Role**: Core data models — Pydantic schemas for tasks, results, agent events, memory scopes, and image attachments.
- **Key Classes**:
  - `TaskStatus(StrEnum)` — `pending`, `processing`, `completed`, `failed`
  - `TaskSchema(BaseModel)` — id, description, priority, status, timestamps, metadata
  - `TaskContract(BaseModel)` — Full task configuration including model override, max_depth, summary_only, acceptance_criteria, memory_scope
  - `ResultSchema(BaseModel)` — task_id, success, data, error, duration
  - `MemoryScope(StrEnum)` — `shared`, `isolated`, `scoped`
  - `AgentEvent(BaseModel)` — Base event with `type` field
  - `ThinkingEvent(AgentEvent)` — Agent thinking stream
  - `ToolCallEvent(AgentEvent)` — Tool call with name, args, call_id
  - `ToolResultEvent(AgentEvent)` — Tool result with call_id, output, success
  - `ApprovalRequestEvent(AgentEvent)` — Human approval request
  - `ResponseEvent(AgentEvent)` — Final text response
  - `ErrorEvent(AgentEvent)` — Error message
  - `ImageAttachment(BaseModel)` — path, mime_type, base64_data + `encode()` method
- **Key Functions**:
  - `encode_image_to_content(path: str) -> dict` — LangChain-compatible image content block
- **Dependencies**: `pydantic`
- **Consumed By**: agent, worker, sdk, session, server, cli, db

---

### `agent` — `src/nexusagent/agent.py`
- **Role**: Creates and configures the deepagents-based LLM agent with policy-aware tool access. Supports three policy levels: permissive, restricted, strict.
- **Key Classes**:
  - `Agent` — LLM-powered agent; properties: `role`, `policy`
- **Key Functions**:
  - `run_agent_task(state: dict) -> dict` — Process a task through the agent using deepagents
- **Dependencies**: `deepagents`, `nexusagent.tools.register_all`, `nexusagent.config`, `nexusagent.tools.registry`
- **Consumed By**: `server.py`, `session.py` (indirectly via deepagents)

### `llm` — `src/nexusagent/llm.py`
- **Role**: Multi-provider LLM bridge. Routes between Gemini SDK and OpenRouter (OpenAI-compatible) with exponential backoff retry.
- **Key Classes**:
  - `LLMResponse(BaseModel)` — content, model_used, provider
  - `LLMProvider` — Singleton with `get_active_model() -> (provider, model_id)` and `generate(prompt, system_prompt, timeout) -> LLMResponse`
- **Singleton**: `llm = LLMProvider()`
- **Dependencies**: `google.generativeai`, `openai.AsyncOpenAI`, `nexusagent.config`, `nexusagent.utils.retry_with_backoff`
- **Consumed By**: `agent.py`, `orchestration.py`, `session.py`

---

### `tools/registry` — `src/nexusagent/tools/registry.py`
- **Role**: Global tool registry with policy enforcement, role-based manifests, tool search, and call validation. Thread-safe via thread-local storage for concurrent agent policies.
- **Key Classes**:
  - `ToolInfo` (dataclass) — name, description, parameters, example, category, returns, requires + `to_prompt_format()`, `to_compact()`
- **Key Functions**:
  - `register_tool(name, description, parameters, example, category, returns, requires) -> Callable` — Decorator to register tools
  - `get_tool_info(name) -> ToolInfo | None`
  - `list_all_tools() -> list[ToolInfo]`
  - `set_policy_context(role, policy)` / `get_policy_context()` / `clear_policy_context()` — Thread-local policy management
  - `get_manifest(role: str) -> set[str]` — Get allowed tools for a role
  - `require_policy(tool_name)` — Decorator to enforce policy before tool execution
  - `check_tool_access(tool_name) -> str | None` — Returns error string if denied
  - `tool_search(query, exact, category, max_results) -> str` — Search available tools
  - `auto_correct(tool_name, kwargs) -> str` — Validate and correct tool calls
- **Variables**: `ROLE_MANIFESTS` — Dict mapping role names to sets of allowed tool names
- **Consumed By**: All tool modules, `agent.py`, `server.py`, `sdk.py`

### `tools/register_all` — `src/nexusagent/tools/register_all.py`
- **Role**: Central registration hub. Imports and registers all built-in tools (fs, shell, git, code_search, research, patch, test_runner, code_review, write_todos) plus orchestration tools (spawn_subagent, ask_user) and memory tools (memory_search, memory_get, memory_write).
- **Key Functions**:
  - `spawn_subagent(task, working_dir, max_turns, acceptance_criteria, memory_mode) -> str` — Spawn isolated sub-agent worker
  - `ask_user(question, options) -> str` — Interactive user question
  - `memory_search(query, max_results) -> str` — Hybrid memory search
  - `memory_get(path, offset, limit) -> str` — Read memory file
  - `memory_write(content, type, description, confidence, entities) -> str` — Write memory entry
- **Dependencies**: All tool modules, `nexusagent.models`, `nexusagent.worker`, `nexusagent.memory`
- **Consumed By**: `agent.py`

### `tools/fs` — `src/nexusagent/tools/fs.py`
- **Role**: File system operations with path jail (workspace root), read-before-write safety, and session tracking.
- **Key Functions**:
  - `set_workspace_root(path)` — Set workspace root for path jail
  - `read_file(path, offset, limit) -> str` — Read with line-range selection
  - `read_multiple_files(paths) -> dict[str, str]`
  - `write_file(path, content) -> str` — Full file write (requires prior read if exists)
  - `edit_file(path, old_text, new_text, start_line, end_line) -> str` — Surgical edit
  - `list_directory(path, recursive, max_depth, pattern, exclude) -> dict` — Nested tree listing
  - `write_multiple_files(files: dict) -> str`
  - `get_read_files() -> list[str]` / `reset_read_tracking()`
- **Consumed By**: `register_all.py`, `server.py`

### `tools/shell` — `src/nexusagent/tools/shell.py`
- **Role**: Shell command execution with injection protection (shlex.split, shell=False), output truncation (1MB), and optional streaming.
- **Key Functions**:
  - `run_shell(command, workdir, env, timeout, capture) -> str` — Execute with structured output
  - `run_shell_streaming(command, workdir, env, timeout) -> str` — Line-by-line streaming
- **Consumed By**: `register_all.py`

### `tools/git` — `src/nexusagent/tools/git.py`
- **Role**: Git operations via subprocess. Read operations (status, diff, log, branch, show, stash_list) and write operations (stash_push, stash_pop, commit, checkout_branch).
- **Key Functions**: `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show`, `git_stash_list`, `git_stash_push`, `git_stash_pop`, `git_commit`, `git_checkout_branch`
- **Consumed By**: `register_all.py`

### `tools/code_search` — `src/nexusagent/tools/code_search.py`
- **Role**: Code search using ripgrep (grep fallback). Supports regex, file patterns, context lines, and symbol-level search across multiple languages.
- **Key Functions**:
  - `search_code(query, path, file_pattern, context_lines, max_results, case_sensitive) -> str`
  - `find_symbol(symbol, path, file_pattern) -> str` — Multi-language symbol definition search
  - `find_references(symbol, path, file_pattern, max_results) -> str`
- **Consumed By**: `register_all.py`

### `tools/research` — `src/nexusagent/tools/research.py`
- **Role**: Web search (Exa primary, Tavily fallback), local doc search (ctx7), and URL fetching with HTML-to-markdown conversion.
- **Key Functions**:
  - `search_web(query) -> str` — Web search with API key fallback chain
  - `search_local_docs(query) -> str` — Local documentation via ctx7
  - `fetch_url(url) -> str` — Fetch and convert HTML to markdown (5000 char limit)
- **Consumed By**: `register_all.py`, `orchestration.py`

### `tools/code_review` — `src/nexusagent/tools/code_review.py`
- **Role**: Static code analysis for bugs, style, security, and performance. Works offline using pattern matching + AST (Python). No LLM required.
- **Key Classes**: `Issue` (dataclass), `ReviewResult` (dataclass with `add()`, `sort_issues()`, `format_report()`)
- **Key Functions**: `review_code(code, language) -> str`
- **Consumed By**: `register_all.py`

### `tools/patch` — `src/nexusagent/tools/patch.py`
- **Role**: Unified diff patch application via `patch_ng` library.
- **Key Functions**: `apply_patch(path, diff) -> str`
- **Consumed By**: `register_all.py`

### `tools/test_runner` — `src/nexusagent/tools/test_runner.py`
- **Role**: Test execution with auto-detection of framework (pytest, jest, go test, etc.) and structured output.
- **Key Functions**:
  - `run_tests(workdir, test_path, framework, timeout, verbose) -> str`
  - `run_single_test(test_path, workdir, framework, timeout) -> str`
- **Consumed By**: `register_all.py`

### `tools/todo` — `src/nexusagent/tools/todo.py`
- **Role**: TODO.md file management (Markdown-based task lists).
- **Key Functions**:
  - `todowrite(todos, todo_path) -> str` — Write/update TODO.md
  - `todoread(todo_path) -> str` — Read TODO.md
- **Consumed By**: `register_all.py` (via `write_todos` import)

### `tools/write_todos` — `src/nexusagent/tools/write_todos.py`
- **Role**: JSON-based task list management with timestamps and metadata.
- **Key Functions**:
  - `write_todos(todos, path) -> str` — Write JSON task list
  - `read_todos(path) -> list[dict]` — Read JSON task list
- **Consumed By**: `register_all.py`

---

### `session` — `src/nexusagent/session.py`
- **Role**: Manages interactive sessions between user and agent. Handles message flow, event streaming, approval gates, image attachments, memory recall/injection, and context compaction.
- **Key Classes**:
  - `Session` — Single interactive session with `send(user_message, images)`, `approve(call_id, approved)`, `interrupt()`, `close()`, `event_stream()`, `pre_compaction_flush()`
  - `SessionManager` — Lifecycle manager with `get(session_id)`, `get_or_create(session_id, working_dir, agent, memory, db_repo)`, `mark_idle(session_id)`, `close(session_id)`, `active_count`
- **Singleton**: `session_manager = SessionManager()`
- **Dependencies**: `nexusagent.config`, `nexusagent.hooks`, `nexusagent.models`, `nexusagent.prompt_loader`, `nexusagent.tools.registry`, `nexusagent.memory`, `nexusagent.compaction`, `langchain_core.messages`
- **Consumed By**: `server.py`, `cli.py`

---

### `server` — `src/nexusagent/server.py`
- **Role**: FastAPI REST API + WebSocket server. Endpoints for task CRUD, worker status, tool listing, and real-time interactive sessions.
- **Key Classes**:
  - `SubmitTaskRequest(BaseModel)` — task description + optional config
- **Key Functions**:
  - `lifespan(app)` — Startup/shutdown (DB init, bus connect, worker start)
  - `create_task(request) -> dict` — POST /tasks
  - `get_task_status(task_id) -> dict` — GET /tasks/{id}/status
  - `get_task_result(task_id) -> dict` — GET /tasks/{id}/result
  - `health_check() -> dict` — GET /health
  - `list_tasks(status, limit, offset) -> list` — GET /tasks
  - `cancel_task(task_id) -> dict` — POST /tasks/{id}/cancel
  - `retry_task(task_id) -> dict` — POST /tasks/{id}/retry
  - `list_workers() -> dict` — GET /workers
  - `list_tools() -> dict` — GET /tools
  - `session_websocket(websocket, session_id, api_key)` — WS /sessions/{id}/ws
  - `run()` — Entry point (uvicorn)
- **Dependencies**: `fastapi`, `nexusagent.api_auth`, `nexusagent.bus`, `nexusagent.config`, `nexusagent.sdk`, `nexusagent.worker`, `nexusagent.db`, `nexusagent.agent`, `nexusagent.session`, `nexusagent.tools.fs`
- **Consumed By**: `pyproject.toml` entry point `nexus-server`

### `cli` — `src/nexusagent/cli.py`
- **Role**: Click-based CLI with commands: `submit`, `run`, `session` (list/resume/fork/rename/delete), `hooks` (list/enable/disable).
- **Key Functions**:
  - `main()` — Click group entry point
  - `submit(task)` — Submit task to agent service
  - `run(task, working_dir, max_turns, wall_time, memory_mode, acceptance, model, max_depth, summary_only)` — Spawn isolated worker
  - `session_cmd(action, session_id, ...)` — Session management
  - `hooks_list()` / `hooks_enable(name)` / `hooks_disable(name)` — Hook management
- **Dependencies**: `click`, `nexusagent.config`, `nexusagent.models`, `nexusagent.worker`, `nexusagent.db`, `nexusagent.hooks`, `nexusagent.sdk`
- **Consumed By**: `pyproject.toml` entry point `nexus-client`, `main.py`

### `sdk` — `src/nexusagent/sdk.py`
- **Role**: High-level SDK for programmatic interaction. Used by both FastAPI server and external clients. Supports context manager for connection lifecycle.
- **Key Classes**:
  - `NexusSDK` — `connect()`, `disconnect()`, `submit_task(task_data) -> str`, `get_task_status(task_id)`, `get_result(task_id)`, `list_tasks(status, limit, offset)`, `cancel_task(task_id)`, `retry_task(task_id)`, `wait_for_result(task_id, timeout)`, `submit_and_wait(task_data, timeout)`, `submit_batch(tasks)`, `health_check()`, `list_workers()`, `list_tools()`
- **Singleton**: `sdk = NexusSDK()`
- **Dependencies**: `nexusagent.bus`, `nexusagent.models`, `nexusagent.db`, `nexusagent.worker`, `nexusagent.tools.registry`
- **Consumed By**: `server.py`, `web_ui.py`

### `bus` — `src/nexusagent/bus.py`
- **Role**: NATS messaging client for task distribution and result storage via JetStream KV. Includes JSON encoder for datetime serialization.
- **Key Classes**:
  - `NATSJSONEncoder` — Custom JSON encoder for datetime/date
  - `AgentBus` — `connect()`, `subscribe(subject, callback)`, `publish(subject, message)`, `put_result(task_id, result)`, `get_result(task_id)`, `close()`
- **Key Functions**: `get_bus() -> AgentBus`, `set_bus(bus)`
- **Dependencies**: `nats`, `nexusagent.config`
- **Consumed By**: `server.py`, `sdk.py`, `worker.py`

### `worker` — `src/nexusagent/worker.py`
- **Role**: Task execution engine. NATS worker subscribes to task queue, processes tasks through agent, stores results. WorkerPool manages isolated sub-agent executions with circuit breakers.
- **Key Classes**:
  - `NexusWorker` — `start()` (NATS loop), `handle_task(msg)` (process incoming task)
  - `WorkerPool` — `spawn(contract, depth) -> SubAgentHandle`, `list_active() -> list[SubAgentHandle]`
- **Singletons**: `worker = NexusWorker()`, `worker_pool = WorkerPool()`
- **Dependencies**: `nexusagent.agent`, `nexusagent.bus`, `nexusagent.db`, `nexusagent.models`, `nexusagent.subagent`, `nexusagent.utils` (CircuitBreaker, retry_with_backoff), `nexusagent.graph`
- **Consumed By**: `server.py`, `sdk.py`, `cli.py`, `register_all.py`

### `subagent` — `src/nexusagent/subagent.py`
- **Role**: Sub-agent control handle for spawned workers. Provides status tracking, cancellation, synchronous/async waiting, and depth-limited nesting.
- **Key Classes**:
  - `SubAgentStatus(StrEnum)` — `pending`, `running`, `completed`, `failed`, `cancelled`
  - `SubAgentHandle` — Properties: `status`, `result`, `summary`, `error`, `model`, `is_done`, `is_cancelled`, `can_spawn_child`; Methods: `cancel() -> bool`, `wait(timeout) -> Any`
- **Dependencies**: `nexusagent.models`
- **Consumed By**: `worker.py`, `register_all.py`

### `orchestration` — `src/nexusagent/orchestration.py`
- **Role**: Deep Research workflow — Intent → Planning → Refinement → Approval → Execution → Synthesis. Uses LLM for plan generation and synthesis.
- **Key Classes**:
  - `SearchResult(BaseModel)` — url, title, content
  - `ResearchPlan(BaseModel)` — query, steps, expected_outputs
  - `ResearchState(BaseModel)` — Tracks research progress
  - `DeepResearchOrchestrator` — `run_deep_research(user_query, template_type) -> str`
- **Singleton**: `deep_research_orchestrator = DeepResearchOrchestrator()`
- **Dependencies**: `nexusagent.llm`, `nexusagent.tools.research`
- **Consumed By**: `graph.py`

### `graph` — `src/nexusagent/graph.py`
- **Role**: LangGraph-based research state machine. Nodes: plan → refine → execute (loop) → synthesize. Uses SQLite checkpointing for persistence.
- **Key Classes**:
  - `ResearchGraphState(TypedDict)` — query, plan, results, current_step, status, report
- **Key Functions**:
  - `plan_node(state) -> dict` — Generate research plan via LLM
  - `refine_node(state) -> dict` — Refine plan for blind spots
  - `execute_node(state) -> dict` — Execute one research step (search + fetch)
  - `synthesize_node(state) -> dict` — Synthesize evidence into final report
  - `route_after_execute(state) -> str` — Conditional edge: loop or synthesize
  - `create_research_graph(db_path) -> CompiledGraph` — Build and compile state machine
- **Dependencies**: `langgraph`, `nexusagent.orchestration`
- **Consumed By**: `worker.py`

---

### `memory_files` — `src/nexusagent/memory_files.py`
- **Role**: File-based memory — canonical source of truth. Stores entries as Markdown files with YAML frontmatter in `bank/` directory. Maintains `MEMORY.md` index.
- **Key Classes**:
  - `MemoryEntryType(StrEnum)` — `world`, `experience`, `opinion`, `observation`
  - `FileMemory` — `initialize()`, `write_entry(content, type, description, confidence, entities) -> path`, `append_daily_log(content)`, `get_index_entries()`, `read_topic_file(filename)`, `get_daily_logs(days)`, `list_all_files()`
- **Dependencies**: `yaml`
- **Consumed By**: `memory.py`, `memory_index.py`

### `memory_index` — `src/nexusagent/memory_index.py`
- **Role**: SQLite-based hybrid search index (FTS5 + sqlite-vec). Tiered embedding: Gemini → local SentenceTransformer → hash fallback. Chunk-based indexing with configurable size/overlap.
- **Key Classes**:
  - `EmbeddingProvider` — `embed(text) -> list[float]`, `embed_batch(texts) -> list[list[float]]`
  - `HybridMemoryIndex` — `index_file(relative_path)`, `async_index_file(relative_path)`, `search(query, max_results, min_score) -> list[dict]`, `search_sync(query, max_results)`, `rebuild()`
- **Constants**: `EMBED_DIM=3072`, `CHUNK_SIZE=400`, `CHUNK_OVERLAP=80`, `VECTOR_WEIGHT=0.7`, `KEYWORD_WEIGHT=0.3`
- **Dependencies**: `sqlite_vec`, `google.generativeai`, `sentence_transformers`, `nexusagent.config`
- **Consumed By**: `memory.py`

### `memory` — `src/nexusagent/memory.py`
- **Role**: Scoped memory bank (shared/isolated/scoped) with vector similarity search. HybridMemoryManager combines file-based memory with hybrid search index.
- **Key Classes**:
  - `MemoryItem(BaseModel)` — id, content, metadata, embedding, timestamp
  - `Memory` — `remember(content, metadata) -> id`, `recall(query, limit) -> list[MemoryItem]`, `reflect() -> str`, `fork(scope) -> Memory`, `merge(child, strategy) -> int`
  - `MemoryManager` — `create(memory_id, scope, parent_memory_id) -> Memory`, `get(memory_id)`, `close()`
  - `HybridMemoryManager` — `initialize()`, `remember(content, type, description, confidence, entities) -> path`, `recall(query, max_results) -> list[dict]`, `get_memory_context(query, max_results) -> str`, `flush(session_summary)`
- **Dependencies**: `sqlite_vec`, `pydantic`, `nexusagent.models`, `nexusagent.memory_files`, `nexusagent.memory_index`
- **Consumed By**: `register_all.py`, `session.py`

### `compaction` — `src/nexusagent/compaction.py`
- **Role**: Graduated context compaction pipeline. Four levels: clear tool results → microcompact → summarize old messages → emergency truncate.
- **Key Classes**:
  - `CompactionPipeline` — `estimate_tokens(messages) -> int`, `should_compact(messages) -> bool`, `compact(messages) -> list`
- **Key Functions**: `pre_compaction_flush(session, summary) -> str` — Flush to daily log before compaction
- **Consumed By**: `session.py`

---

### `tui` — `src/nexusagent/tui.py`
- **Role**: Textual-based terminal UI. Main application with streaming chat, status bar, theme system, responsive breakpoints, approval modals, and slash commands.
- **Key Classes**:
  - `SpinnerLabel(Horizontal)` — Animated spinner + label
  - `Breakpoint(Enum)` — Terminal width breakpoints (xs, sm, md, lg, xl)
  - `ApprovalModal(ModalScreen[bool])` — Tool approval dialog
  - `ErrorModal(ModalScreen[None])` — Error display dialog
  - `NexusApp(App)` — Main TUI application with `compose()`, `on_mount()`, `on_input_submitted()`, `action_clear/quit/interrupt/expand_all/collapse_all/toggle_auto_approve()`
- **Key Functions**:
  - `classify_breakpoint(width) -> Breakpoint`
  - `is_no_color() -> bool` — NO_COLOR spec compliance
  - `debounce_resize(state, current_time, debounce_seconds) -> bool`
  - `main(yolo: bool)` — TUI entry point
- **Variables**: `NEXUS_THEMES` — List of theme definitions
- **Dependencies**: `textual`, `websockets`, `nexusagent.config`, `nexusagent.skills`
- **Consumed By**: `pyproject.toml` entry point `nexus`

### `widgets/status` — `src/nexusagent/widgets/status.py`
- **Role**: Status bar and status-related widgets for the TUI.
- **Key Classes**:
  - `ModelLabel(Static)` — Model name with smart truncation
  - `StatusBar(Horizontal)` — Bottom status bar: [status_message] [CWD] [branch] [tokens] [model]
  - `GitStatus` — `detect() -> str | None`, `label(status) -> str`
  - `ContextWindowBar` — Context usage percentage with color coding (green/amber/red)
  - `BrailleSpinner` — Braille dot animation frames
- **Consumed By**: `tui.py`

### `widgets/messages` — `src/nexusagent/widgets/messages.py`
- **Role**: Message display widgets for the TUI chat interface.
- **Key Classes**:
  - `UserMessage(Static)` — User message with left-border accent and timestamp
  - `AssistantMessage(Static)` — Streaming assistant message with `append_token()`, `finalize()`, Content-based rendering
  - `ToolCallMessage(Static)` — Tool call with collapsible output, status indicators (⚙/✔/✘), `update_status()`, `update_output()`, `toggle_collapse()`
  - `AppMessage(Static)` — System/app message (dim italic)
  - `ErrorMessage(Static)` — Error message with $error color
  - `WelcomeBanner(Static)` — Session start banner (removed after first message)
- **Consumed By**: `tui.py`

### `widgets/theme` — `src/nexusagent/widgets/theme.py`
- **Role**: Theme system with 7 built-in themes (nexus-dark, tokyo-night, rose-pine, solarized-dark, catppuccin-mocha, gruvbox-dark, nord). Semantic color tokens.
- **Key Classes**: `ThemeColors` (frozen dataclass) — bg, bg_panel, bg_surface, bg_hover, text, text_secondary, text_muted, text_dim, accent, accent_hover, accent_light, success, warning, error, error_bg, border, border_subtle, border_focus
- **Key Functions**:
  - `get_theme_colors(theme_name) -> ThemeColors`
  - `get_theme_css(theme_name) -> dict[str, str]`
  - `get_css_variable_defaults() -> dict[str, str]`
  - `register_themes(app)` — Register all 7 themes with Textual
- **Consumed By**: `tui.py`

### `widgets/chat_input` — `src/nexusagent/widgets/chat_input.py`
- **Role**: Multiline chat input widget with key bindings, image path detection, slash command completion, and command history persistence.
- **Key Classes**:
  - `ChatInput(TextArea)` — `on_mount()`, `action_submit()`, `action_cancel()`, `on_input_changed()`, `action_autocomplete()`
- **Consumed By**: `tui.py`

---

### `hooks/__init__` — `src/nexusagent/hooks/__init__.py`
- **Role**: Hook system for lifecycle events. Register callbacks for events like session start, tool use, errors, sub-agent start/stop.
- **Key Classes**:
  - `HookEvent(StrEnum)` — `session_init`, `pre_tool_use`, `post_tool_use`, `session_end`, `subagent_start`, `subagent_stop`, `error`
  - `HookRegistration` — `enable()`, `disable()`
  - `HookManager` — `register_hook(event, callback, name)`, `get_hooks(event)`, `list_hooks()`, `disable_hook(name)`, `enable_hook(name)`, `clear()`, `run_hooks(event, context)`
- **Key Functions**: `get_hook_manager() -> HookManager`, `reset_hook_manager()`, `register_hook(event, callback, name)`, `run_hooks(event, context)`
- **Consumed By**: `session.py`, `cli.py`, `hooks/builtins.py`

### `hooks/builtins` — `src/nexusagent/hooks/builtins.py`
- **Role**: Built-in hook implementations for common use cases.
- **Key Functions**:
  - `session_init_load_context(context) -> dict` — Load NEXUS.md at session start
  - `post_tool_use_telemetry(context) -> dict` — Log tool usage to telemetry
  - `error_log_to_file(context) -> dict` — Log errors to dedicated file
  - `subagent_start_log(context) -> dict` — Log sub-agent start
  - `subagent_stop_log(context) -> dict` — Log sub-agent stop
- **Dependencies**: `nexusagent.hooks`
- **Consumed By**: Registered at runtime

---

### `web_ui` — `src/nexusagent/web_ui.py`
- **Role**: Gradio-based web interface. Simple chat UI that submits tasks via SDK.
- **Key Functions**:
  - `handle_submit(text, sdk) -> (log_message, status)`
  - `create_ui()` — Build Gradio Blocks interface
  - `run_ui()` — Entry point (launches Gradio server)
- **Dependencies**: `gradio`, `nexusagent.sdk`
- **Consumed By**: `pyproject.toml` entry point `nexus-web`

### `db` — `src/nexusagent/db.py`
- **Role**: Async SQLAlchemy database layer. Models for tasks, results, sessions, messages. Repositories for CRUD operations.
- **Key Classes**:
  - `Base(DeclarativeBase)` — SQLAlchemy base
  - `TaskModel` — id, description, status, priority, metadata, timestamps
  - `ResultModel` — task_id, success, data, error, duration
  - `SessionModel` — id, working_dir, memory_id, status, timestamps
  - `MessageModel` — session_id, role, content, tool_name, tool_args
  - `DatabaseManager` — `reinit(db_url)`, `init_db()`, `get_session()`, `execute(query, params)`
  - `TaskRepository` — `create_task()`, `update_task_status()`, `get_task_status()`, `save_result()`, `list_tasks()`, `cancel_task()`, `retry_task()`
  - `SessionRepository` — `create_session()`, `get_session()`, `update_status()`, `add_message()`, `get_messages()`, `list_sessions()`, `rename_session()`, `delete_session()`, `fork_session()`
- **Singletons**: `db_manager`, `task_repo`, `session_repo`
- **Dependencies**: `sqlalchemy`, `nexusagent.config`, `nexusagent.models`
- **Consumed By**: `server.py`, `sdk.py`, `worker.py`, `session.py`, `cli.py`

### `auth` — `src/nexusagent/auth.py`
- **Role**: API key management with Fernet encryption. Stores encrypted keys in `keystore.json`, derived from master secret via PBKDF2.
- **Key Classes**:
  - `AuthManager` — `initialize_wizard(force)`, `save_key(service, key)`, `get_key(service) -> str | None`
- **Singleton**: `auth_manager`
- **Dependencies**: `cryptography`, `nexusagent.config`
- **Consumed By**: `api_auth.py`

### `api_auth` — `src/nexusagent/api_auth.py`
- **Role**: FastAPI API key verification dependency. Reads `X-API-Key` header and validates against auth keystore.
- **Key Functions**: `verify_api_key(api_key: str) -> str`
- **Dependencies**: `fastapi`, `nexusagent.auth`
- **Consumed By**: `server.py`

### `skills` — `src/nexusagent/skills.py`
- **Role**: Skill loading system. Skills are directories with `SKILL.md` files containing YAML frontmatter and markdown content.
- **Key Classes**: `SkillLoadError(Exception)`, `Skill` (name, description, content, triggers)
- **Key Functions**:
  - `load_skill(skill_dir) -> Skill | None`
  - `load_all_skills(skills_dir) -> dict[str, Skill]`
  - `get_skills_summary(skills) -> str`
  - `get_skill_content(skills, name) -> str | None`
- **Consumed By**: `tui.py`

### `prompt_loader` — `src/nexusagent/prompt_loader.py`
- **Role**: NEXUS.md prompt loading with recursive `@file` chain resolution, circular reference detection, and chat-time file injection.
- **Key Classes**: `PromptLoadError(Exception)`, `CircularChainError(PromptLoadError)`
- **Key Functions**:
  - `resolve_path(path_str, relative_to) -> Path`
  - `load_prompt_content(content, current_dir, visited, depth, max_depth, label) -> str` — Recursive @file resolution
  - `load_nexus_prompt(package_root, cwd, max_depth) -> str` — Load complete NEXUS.md (base + project override)
  - `inject_file_at_reference(text, cwd, max_depth) -> str` — Process @file in chat input
  - `get_file_info_placeholder(file_path) -> str`
- **Consumed By**: `session.py`

### `telemetry` — `src/nexusagent/telemetry.py`
- **Role**: Structured logging and telemetry collection. Tracks tool calls, errors, messages, and token usage.
- **Key Classes**:
  - `TelemetryManager` — `log_tool_call(tool, args, result, error)`, `log_error(message, exc_info)`, `log_message(content, is_user)`, `log_tokens(count)`, `get_metrics() -> dict`, `get_recent_logs(lines) -> list[str]`
  - `LogViewer(Static)` — TUI widget for displaying recent logs
- **Key Functions**: `setup_telemetry(app) -> TelemetryManager`
- **Consumed By**: `tui.py`

### `utils` — `src/nexusagent/utils.py`
- **Role**: Utility decorators — exponential backoff retry and circuit breaker pattern.
- **Key Classes**:
  - `CircuitState` — CLOSED, OPEN, HALF_OPEN
  - `CircuitBreakerError(Exception)` — Raised when circuit is open
  - `CircuitBreaker` — Stateful circuit breaker usable as decorator or context manager. Properties: `state`, `failure_count`
- **Key Functions**:
  - `retry_with_backoff(max_attempts, base_delay, max_delay, exponential_base, jitter, exceptions, on_retry) -> Callable`
  - `retry_on_false(max_attempts, base_delay, max_delay, exponential_base, jitter, on_retry) -> Callable`
- **Consumed By**: `llm.py`, `worker.py`, `bus.py`

### `task_reaper` — `src/nexusagent/task_reaper.py`
- **Role**: Background task that reaps tasks stuck in PROCESSING state beyond a max age.
- **Key Classes**: `TaskReaper` — `start()`, `stop()`
- **Dependencies**: `nexusagent.db`
- **Consumed By**: Server startup (not directly imported, runs as background task)

### `worktree-worker` — `scripts/worktree-worker.py`
- **Role**: Standalone CLI for managing git worktrees for parallel task execution. Commands: create, list, collect, destroy, remote, status.
- **Dependencies**: stdlib only (argparse, subprocess, json, pathlib)
- **Consumed By**: Not imported; standalone script

---

## Data Flow

### Interactive Session (TUI)

```
User types message in ChatInput
        │
        ▼
NexusApp.on_input_submitted()
        │
        ▼
Session.send(user_message, images)
  ├─ Store user message in DB (session_repo.add_message)
  ├─ Recall memory context (HybridMemoryManager.get_memory_context)
  ├─ Inject memory + NEXUS.md into system prompt
  ├─ Call deepagents.astream() for real-time streaming
  │   ├─ ThinkingEvent → TUI displays thinking
  │   ├─ ToolCallEvent → TUI shows tool call widget
  │   │   └─ Tool execution via registry (policy check → execute → return result)
  │   ├─ ToolResultEvent → TUI updates tool widget
  │   ├─ ApprovalRequestEvent → TUI shows ApprovalModal
  │   └─ ResponseEvent → TUI streams tokens to AssistantMessage
  ├─ Store assistant message in DB
  └─ Run post_tool_use hooks
        │
        ▼
TUI renders final state (messages, status bar update)
```

### Task Submission (CLI/REST)

```
nexus run "task"  OR  POST /tasks {"description": "task"}
        │
        ▼
CLI: worker_pool.spawn(contract, depth=0)
  OR
Server: sdk.submit_task(task_data) → NATS publish
        │
        ▼
NexusWorker.handle_task(msg) [NATS callback]
  ├─ Parse TaskContract from message
  ├─ Update task status → PROCESSING
  ├─ Call run_agent_task(state) [deepagents sync]
  │   └─ Agent loop: LLM → tool calls → results → LLM → ... → final response
  ├─ Store result in DB (task_repo.save_result)
  ├─ Publish result to NATS KV store
  └─ Update task status → COMPLETED / FAILED
        │
        ▼
CLI: SubAgentHandle.wait() polls for result
  OR
Client: GET /tasks/{id}/result
```

### Sub-Agent Spawning

```
Agent calls spawn_subagent(task, working_dir, max_turns, ...)
        │
        ▼
WorkerPool.spawn(contract, depth)
  ├─ Create SubAgentHandle (pending → running)
  ├─ Create TaskContract with depth+1
  ├─ Submit to NATS task queue
  └─ Return SubAgentHandle to agent
        │
        ▼
Agent can: handle.wait(timeout), handle.cancel(), handle.result
```

### Memory Flow

```
Session.send() → memory recall
        │
        ▼
HybridMemoryManager.get_memory_context(query)
  ├─ HybridMemoryIndex.search(query) → keyword + vector hybrid
  │   ├─ FTS5 keyword search
  │   ├─ Vector similarity (sqlite-vec)
  │   └─ Union merge with weights (0.7 vector + 0.3 keyword)
  └─ Format results with source citations → inject into prompt

Agent calls memory_write(content, type, description, ...)
        │
        ▼
HybridMemoryManager.remember(content, type, description, ...)
  ├─ FileMemory.write_entry() → write to bank/*.md with YAML frontmatter
  └─ HybridMemoryIndex.async_index_file() → chunk, embed, store in SQLite
```

---

## Public API

### Agent
- `Agent` — LLM agent with policy-aware tool access
  - `role` (property) → str
  - `policy` (property) → str
- `run_agent_task(state: dict) -> dict`

### LLM
- `LLMResponse(BaseModel)` — content: str, model_used: str, provider: str
- `LLMProvider`
  - `get_active_model() -> tuple[str, str]`
  - `generate(prompt: str, system_prompt: str | None, timeout: float, **kwargs) -> LLMResponse`
- `llm: LLMProvider` (singleton)

### Tools (all registered via `@register_tool`)
- `read_file(path, offset=1, limit=None) -> str`
- `write_file(path, content) -> str`
- `edit_file(path, old_text, new_text, start_line=None, end_line=None) -> str`
- `list_directory(path, recursive=False, max_depth=2, pattern=None, exclude=None) -> dict`
- `read_multiple_files(paths) -> dict[str, str]`
- `write_multiple_files(files: dict) -> str`
- `run_shell(command, workdir=None, env=None, timeout=300, capture=True) -> str`
- `run_shell_streaming(command, workdir=None, env=None, timeout=300) -> str`
- `git_status(workdir=None) -> str`
- `git_diff(file_path=None, cached=False, workdir=None) -> str`
- `git_log(count=10, file_path=None, oneline=True, workdir=None) -> str`
- `git_branch(workdir=None) -> str`
- `git_show(commit="HEAD", workdir=None) -> str`
- `git_stash_list/push/pop(workdir=None) -> str`
- `git_commit(message, files=None, workdir=None) -> str`
- `git_checkout_branch(branch, create=False, workdir=None) -> str`
- `search_code(query, path=".", file_pattern=None, context_lines=2, max_results=50, case_sensitive=False) -> str`
- `find_symbol(symbol, path=".", file_pattern=None) -> str`
- `find_references(symbol, path=".", file_pattern=None, max_results=50) -> str`
- `search_web(query) -> str`
- `search_local_docs(query) -> str`
- `fetch_url(url) -> str`
- `review_code(code, language="python") -> str`
- `apply_patch(path, diff) -> str`
- `run_tests(workdir, test_path=None, framework=None, timeout=300, verbose=False) -> str`
- `run_single_test(test_path, workdir, framework=None, timeout=300) -> str`
- `write_todos(todos, path="./todos.json") -> str`
- `read_todos(path="./todos.json") -> list[dict]`
- `todowrite(todos, todo_path=None) -> str`
- `todoread(todo_path=None) -> str`
- `spawn_subagent(task, working_dir=".", max_turns=15, acceptance_criteria=None, memory_mode="isolated") -> str`
- `ask_user(question, options=None) -> str`
- `memory_search(query, max_results=6) -> str`
- `memory_get(path, offset=1, limit=50) -> str`
- `memory_write(content, type="world", description="", confidence=None, entities=None) -> str`
- `tool_search(query="", exact=False, category=None, max_results=10) -> str`
- `auto_correct(tool_name, kwargs=None) -> str`

### Tool Registry
- `register_tool(name, description, parameters, example, category, returns, requires) -> Callable`
- `get_tool_info(name) -> ToolInfo | None`
- `list_all_tools() -> list[ToolInfo]`
- `set_policy_context(role, policy)` / `get_policy_context()` / `clear_policy_context()`
- `get_manifest(role: str) -> set[str]`
- `require_policy(tool_name)` (decorator)
- `check_tool_access(tool_name) -> str | None`

### Session
- `Session`
  - `send(user_message: str, images: list[str] | None) -> None`
  - `approve(call_id: str, approved: bool) -> None`
  - `interrupt() -> None`
  - `close() -> None`
  - `event_stream() -> AsyncGenerator[dict[str, Any], None]`
  - `pre_compaction_flush() -> str`
- `SessionManager`
  - `get(session_id: str) -> Session | None`
  - `get_or_create(session_id, working_dir, agent, memory, db_repo) -> Session`
  - `mark_idle(session_id: str) -> None`
  - `close(session_id: str) -> None`
  - `active_count` (property) → int
- `session_manager: SessionManager` (singleton)

### Server (FastAPI routes)
- `POST /tasks` — Submit task
- `GET /tasks/{task_id}/status` — Task status
- `GET /tasks/{task_id}/result` — Task result
- `GET /health` — Health check
- `GET /tasks` — List tasks (status, limit, offset)
- `POST /tasks/{task_id}/cancel` — Cancel task
- `POST /tasks/{task_id}/retry` — Retry failed task
- `GET /workers` — Worker status
- `GET /tools` — List tools by category
- `WS /sessions/{session_id}/ws` — Interactive session WebSocket

### SDK
- `NexusSDK`
  - `connect()` / `disconnect()`
  - `submit_task(task_data: dict) -> str`
  - `get_task_status(task_id: str) -> TaskStatus | None`
  - `get_result(task_id: str) -> ResultSchema | None`
  - `list_tasks(status, limit, offset) -> list[dict]`
  - `cancel_task(task_id: str) -> bool`
  - `retry_task(task_id: str) -> str | None`
  - `wait_for_result(task_id, timeout, poll_interval) -> ResultSchema | None`
  - `submit_and_wait(task_data, timeout, poll_interval) -> ResultSchema | None`
  - `submit_batch(tasks: list[dict]) -> list[str]`
  - `health_check() -> dict`
  - `list_workers() -> dict`
  - `list_tools() -> dict`

### Sub-Agent
- `SubAgentStatus(StrEnum)` — pending, running, completed, failed, cancelled
- `SubAgentHandle`
  - `status` (property) → SubAgentStatus
  - `result` (property) → Any
  - `summary` (property) → str | None
  - `error` (property) → str | None
  - `model` (property) → str
  - `is_done() -> bool`
  - `is_cancelled() -> bool`
  - `can_spawn_child() -> bool`
  - `cancel() -> bool`
  - `wait(timeout: float | None) -> Any`

### Memory
- `MemoryScope(StrEnum)` — shared, isolated, scoped
- `MemoryItem(BaseModel)` — id, content, metadata, embedding, timestamp
- `Memory`
  - `remember(content, metadata) -> str`
  - `recall(query, limit) -> list[MemoryItem]`
  - `reflect() -> str`
  - `fork(scope) -> Memory`
  - `merge(child, strategy) -> int`
- `MemoryManager`
  - `create(memory_id, scope, parent_memory_id) -> Memory`
  - `get(memory_id) -> Memory | None`
  - `close()`
- `HybridMemoryManager`
  - `initialize()`
  - `remember(content, type, description, confidence, entities) -> str`
  - `recall(query, max_results) -> list[dict]`
  - `get_memory_context(query, max_results) -> str`
  - `flush(session_summary)`

### Hooks
- `HookEvent(StrEnum)` — session_init, pre_tool_use, post_tool_use, session_end, subagent_start, subagent_stop, error
- `HookRegistration` — `enable()`, `disable()`
- `HookManager`
  - `register_hook(event, callback, name) -> HookRegistration`
  - `get_hooks(event) -> list[HookRegistration]`
  - `list_hooks() -> list[HookRegistration]`
  - `disable_hook(name)` / `enable_hook(name)`
  - `clear()`
  - `run_hooks(event, context)`
- `get_hook_manager() -> HookManager`
- `reset_hook_manager()`

### Config
- `ConfigSchema(BaseModel)` — server, client, auth, agent, prompt, logging, hooks, log_level
- `settings: ConfigSchema` (singleton)

### Models
- `TaskStatus(StrEnum)` — pending, processing, completed, failed
- `TaskSchema(BaseModel)` — id, description, priority, status, created_at, updated_at, metadata
- `TaskContract(BaseModel)` — task_id, title, working_dir, allowed_tools, denied_tools, max_turns, max_wall_time, max_tokens, acceptance_criteria, memory_scope, parent_memory_id, human_in_the_loop, on_failure, expected_outputs, description, priority, metadata, model, max_depth, summary_only
- `ResultSchema(BaseModel)` — task_id, success, data, error, completed_at, duration
- `AgentEvent(BaseModel)` — type: str
- `ThinkingEvent`, `ToolCallEvent`, `ToolResultEvent`, `ApprovalRequestEvent`, `ResponseEvent`, `ErrorEvent`
- `ImageAttachment(BaseModel)` — path, mime_type, base64_data, `encode() -> str`
- `encode_image_to_content(path: str) -> dict`

### DB
- `TaskModel`, `ResultModel`, `SessionModel`, `MessageModel`
- `DatabaseManager` — `reinit(db_url)`, `init_db()`, `get_session()`, `execute(query, params)`
- `TaskRepository` — `create_task()`, `update_task_status()`, `get_task_status()`, `save_result()`, `list_tasks()`, `cancel_task()`, `retry_task()`
- `SessionRepository` — `create_session()`, `get_session()`, `update_status()`, `add_message()`, `get_messages()`, `list_sessions()`, `rename_session()`, `delete_session()`, `fork_session()`
- `db_manager`, `task_repo`, `session_repo` (singletons)

### Utils
- `CircuitBreaker` — `state` (property), `failure_count` (property), usable as decorator/context manager
- `CircuitBreakerError(Exception)`
- `retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=True, exceptions=(Exception,), on_retry=None) -> Callable`
- `retry_on_false(max_attempts=3, base_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=True, on_retry=None) -> Callable`

---

## Test Coverage

| Source File | Test File(s) | Coverage Level |
|---|---|---|
| `config.py` | `test_config.py` | **Good** — config loading, env overrides |
| `models.py` | `test_models.py` | **Good** — all model classes |
| `agent.py` | `test_agent_events.py` | **Partial** — event types tested |
| `llm.py` | — | **Untested** |
| `tools/registry.py` | `test_new_tools.py` | **Partial** — tool registration |
| `tools/fs.py` | `test_fs.py`, `test_fs_enhanced.py` | **Good** — read/write/edit/list |
| `tools/shell.py` | `test_shell.py` | **Good** — shell execution |
| `tools/git.py` | — | **Untested** |
| `tools/code_search.py` | — | **Untested** |
| `tools/research.py` | `test_research.py` | **Partial** — search/fetch |
| `tools/code_review.py` | — | **Untested** |
| `tools/patch.py` | `test_patch.py` | **Good** |
| `tools/test_runner.py` | — | **Untested** |
| `tools/todo.py` | `test_tools/test_todo.py` | **Good** |
| `tools/write_todos.py` | — | **Untested** (covered by todo tests) |
| `session.py` | `test_session.py`, `test_session_memory.py` | **Good** |
| `server.py` | `test_server.py`, `test_websocket.py` | **Good** — REST + WS endpoints |
| `cli.py` | `test_cli_run.py` | **Partial** — run command |
| `sdk.py` | `test_sdk.py` | **Good** |
| `bus.py` | `test_bus.py` | **Good** |
| `worker.py` | `test_worker_pool.py` | **Partial** — pool management |
| `subagent.py` | `test_subagent.py`, `test_spawn_subagent.py` | **Good** |
| `orchestration.py` | `test_orchestration.py` | **Partial** |
| `graph.py` | `test_graph.py`, `test_graph_nodes.py` | **Good** |
| `memory.py` | `test_memory.py` | **Good** |
| `memory_index.py` | `test_memory_index.py` | **Good** |
| `memory_files.py` | `test_memory_files.py` | **Good** |
| `compaction.py` | `test_compaction.py` | **Good** |
| `tui.py` | `test_tui_theme.py`, `test_tui_widgets.py`, `test_tui_help_input.py`, `test_tui_responsive.py`, `test_tui_streaming.py` | **Good** — widgets, themes, responsive |
| `widgets/status.py` | `test_tui_widgets.py` | **Partial** |
| `widgets/messages.py` | `test_tui_widgets.py`, `test_tui_streaming.py` | **Partial** |
| `widgets/theme.py` | `test_tui_theme.py` | **Good** |
| `widgets/chat_input.py` | `test_tui_help_input.py` | **Partial** |
| `hooks/__init__.py` | `test_hooks.py` | **Good** |
| `hooks/builtins.py` | — | **Untested** |
| `web_ui.py` | `verify_web_ui.py` (contract) | **Minimal** |
| `db.py` | `test_db_sessions.py` | **Partial** — sessions |
| `auth.py` | — | **Untested** |
| `api_auth.py` | — | **Untested** (covered by server tests) |
| `skills.py` | `test_skills.py` | **Good** |
| `prompt_loader.py` | — | **Untested** |
| `telemetry.py` | — | **Untested** |
| `utils.py` | — | **Untested** |
| `task_reaper.py` | `test_task_reaper.py` | **Good** |
| `register_all.py` | `test_new_tools.py` | **Partial** |
| `conftest.py` | — | Test infrastructure |
| `test_e2e_production.py` | — | E2E integration |
| `contract_verification/` | — | Contract/chaos tests |

### Untested Source Files
- `llm.py` — LLM provider (Gemini/OpenRouter calls)
- `tools/git.py` — Git operations
- `tools/code_search.py` — Code search
- `tools/code_review.py` — Static analysis
- `tools/test_runner.py` — Test execution
- `tools/write_todos.py` — JSON todos
- `hooks/builtins.py` — Built-in hook functions
- `auth.py` — Encryption/key management
- `prompt_loader.py` — NEXUS.md loading
- `telemetry.py` — Telemetry logging
- `utils.py` — Circuit breaker, retry decorators

---

## Configuration Surface

### Config File: `config/nexusagent.yaml`

| Field | Default | Description |
|---|---|---|
| `server.nats_url` | `nats://localhost:4222` | NATS server URL |
| `server.db_path` | `nexus.db` | SQLite database path |
| `server.api_port` | `8000` | FastAPI server port |
| `server.worker_threads` | `4` | Worker thread count |
| `server.nats_reconnect_wait` | `2` | NATS reconnect wait (seconds) |
| `server.nats_max_reconnects` | `60` | Max NATS reconnection attempts |
| `client.tui_theme` | `textual-dark` | TUI color theme |
| `client.timeout` | `30` | Request timeout (seconds) |
| `client.retry_limit` | `3` | Retry limit for API calls |
| `client.result_timeout` | `300` | Result polling timeout (seconds) |
| `client.api_key` | `""` | API key for TUI WebSocket |
| `client.tui_responsive_enabled` | `true` | Enable responsive TUI layout |
| `auth.master_secret_path` | `.master.secret` | Master encryption secret file |
| `auth.keystore_path` | `keystore.json` | Encrypted API key store |
| `auth.salt_path` | `.master.salt` | KDF salt file |
| `auth.kdf_iterations` | `100000` | PBKDF2 iteration count |
| `agent.default_model` | `gemini-3.1-flash-lite` | Default LLM model |
| `agent.primary_provider` | `gemini` | Primary LLM provider (gemini/openrouter) |
| `agent.gemini_model` | `gemini-3.1-flash-lite` | Gemini model ID |
| `agent.openrouter_default_model` | `openrouter/auto` | OpenRouter default model |
| `agent.openrouter_override_model` | `None` | Override OpenRouter model |
| `agent.enabled_tools` | `[read_file, write_file, run_shell]` | Default enabled tools |
| `agent.max_tool_output_chars` | `400` | Max tool output characters |
| `agent.max_conversation_history` | `40` | Max messages in conversation history |
| `agent.compaction_enabled` | `true` | Enable context compaction |
| `agent.max_image_size_mb` | `10` | Max image attachment size |
| `agent.supported_image_types` | `[.png, .jpg, .jpeg, .webp, .gif, .bmp]` | Supported image formats |
| `prompt.base_prompt_file` | `config/NEXUS.md` | Base system prompt file |
| `prompt.load_cwd_prompt` | `true` | Load project NEXUS.md from CWD |
| `prompt.max_chain_depth` | `8` | Max @file chain depth |
| `prompt.max_inject_file_size` | `262144` (256KB) | Max file injection size |
| `prompt.chat_file_injection` | `true` | Enable @file in chat |
| `prompt.session_history_count` | `5` | Recent sessions for context |
| `prompt.session_summary_max_chars` | `2000` | Max chars per session summary |
| `logging.level` | `INFO` | Log level |
| `logging.format` | `%(asctime)s [%(levelname)s] %(name)s: %(message)s` | Log format |
| `hooks.hooks_enabled` | `true` | Enable hooks system |
| `hooks.hooks_dir` | `.nexusagent/hooks` | Hooks directory |

### Environment Variables

All config fields can be overridden via environment variables using the pattern `NEXUS_{SECTION}__{FIELD}` (double underscore for nesting):

| Environment Variable | Overrides | Example |
|---|---|---|
| `NEXUS_SERVER__NATS_URL` | `server.nats_url` | `nats://remote:4222` |
| `NEXUS_SERVER__API_PORT` | `server.api_port` | `9000` |
| `NEXUS_SERVER__DB_PATH` | `server.db_path` | `/tmp/test.db` |
| `NEXEX_CLIENT__TUI_THEME` | `client.tui_theme` | `tokyo-night` |
| `NEXUS_CLIENT__API_KEY` | `client.api_key` | `sk-...` |
| `NEXUS_AGENT__DEFAULT_MODEL` | `agent.default_model` | `gemini-3.1-flash` |
| `NEXUS_AGENT__PRIMARY_PROVIDER` | `agent.primary_provider` | `openrouter` |
| `NEXUS_AGENT__GEMINI_MODEL` | `agent.gemini_model` | `gemini-3.1-flash` |
| `NEXUS_AGENT__OPENROUTER_DEFAULT_MODEL` | `agent.openrouter_default_model` | `anthropic/claude-sonnet-4` |
| `NEXUS_AGENT__OPENROUTER_OVERRIDE_MODEL` | `agent.openrouter_override_model` | `openai/gpt-4o` |
| `NEXUS_AGENT__COMPACTION_ENABLED` | `agent.compaction_enabled` | `false` |
| `NEXUS_AGENT__MAX_CONVERSATION_HISTORY` | `agent.max_conversation_history` | `80` |
| `NEXUS_AGENT__MAX_TOOL_OUTPUT_CHARS` | `agent.max_tool_output_chars` | `1000` |
| `NEXUS_AGENT__MAX_IMAGE_SIZE_MB` | `agent.max_image_size_mb` | `20` |
| `NEXUS_PROMPT__BASE_PROMPT_FILE` | `prompt.base_prompt_file` | `custom_prompt.md` |
| `NEXUS_PROMPT__LOAD_CWD_PROMPT` | `prompt.load_cwd_prompt` | `false` |
| `NEXUS_PROMPT__MAX_CHAIN_DEPTH` | `prompt.max_chain_depth` | `16` |
| `NEXUS_PROMPT__CHAT_FILE_INJECTION` | `prompt.chat_file_injection` | `false` |
| `NEXUS_LOGGING__LEVEL` | `logging.level` | `DEBUG` |
| `NEXUS_LOG_LEVEL` | `logging.level` (back-compat) | `WARNING` |
| `NEXUS_HOOKS__HOOKS_ENABLED` | `hooks.hooks_enabled` | `false` |
| `NEXUS_HOOKS__HOOKS_DIR` | `hooks.hooks_dir` | `/custom/hooks` |

### LLM API Keys (Environment)

| Variable | Provider | Description |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini | Required for Gemini provider |
| `OPENROUTER_API_KEY` | OpenRouter | Required for OpenRouter provider |
| `OPENROUTER_BASE_URL` | OpenRouter | API base URL (default: `https://openrouter.ai/api/v1`) |

### External Service Keys (Environment)

| Variable | Service | Used By |
|---|---|---|
| `EXA_API_KEY` | Exa.ai | `search_web()` primary |
| `TAVILY_API_KEY` | Tavily | `search_web()` fallback |

### CLI Entry Points (from `pyproject.toml`)

| Command | Module | Function |
|---|---|---|
| `nexus-server` | `nexusagent.server` | `run()` |
| `nexus-client` | `nexusagent.cli` | `main()` |
| `nexus` | `nexusagent.tui` | `main()` |
| `nexus-web` | `nexusagent.web_ui` | `run_ui()` |

### TUI Key Bindings

| Key | Action |
|---|---|
| `Enter` | Submit message |
| `Escape` | Cancel input / Quit |
| `Ctrl+C` | Interrupt agent |
| `Ctrl+L` | Clear chat |
| `Ctrl+A` | Expand all tool outputs |
| `Ctrl+O` | Collapse all tool outputs |
| `Ctrl+Y` | Toggle auto-approve mode |
| `Tab` | Slash command autocomplete |
| `Up/Down` | Command history |

### TUI Themes

| Theme Name | Description |
|---|---|
| `nexus-dark` | Default dark theme (indigo accent) |
| `tokyo-night` | Tokyo Night (blue accent) |
| `rose-pine` | Rose Pine (purple accent) |
| `solarized-dark` | Solarized Dark (blue accent) |
| `catppuccin-mocha` | Catppuccin Mocha |
| `gruvbox-dark` | Gruvbox Dark |
| `nord` | Nord |

### Tool Categories

| Category | Tools |
|---|---|
| `fs` | read_file, write_file, edit_file, list_directory, read_multiple_files, write_multiple_files |
| `shell` | run_shell, run_shell_streaming |
| `git` | git_status, git_diff, git_log, git_branch, git_show, git_stash_list/push/pop, git_commit, git_checkout_branch |
| `search` | search_code, find_symbol, find_references |
| `web` | search_web, search_local_docs, fetch_url |
| `test` | run_tests, run_single_test |
| `core` | tool_search, auto_correct |
| `orchestration` | spawn_subagent |
| `interaction` | ask_user |
| `memory` | memory_search, memory_get, memory_write |

### Role-Based Tool Manifests

| Role | Tools |
|---|---|
| `minimal` | read_file, list_directory |
| `reader` | read_file, list_directory, search_code, find_symbol, find_references |
| `writer` | reader tools + write_file, edit_file, run_shell |
| `full` | All tools |

---

*This index is auto-generated from source code analysis. For the authoritative reference, consult the source files directly.*
