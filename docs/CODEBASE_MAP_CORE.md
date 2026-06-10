# NexusAgent Core Architecture Map

> Auto-generated codebase analysis of the 9 core modules.
> Covers: purpose, classes, methods, dependencies, and issues for each file.

---

## Table of Contents

1. [config.py](#1-configpy)
2. [models.py](#2-modelspy)
3. [prompt_loader.py](#3-prompt_loaderpy)
4. [agent.py](#4-agentpy)
5. [session.py](#5-sessionpy)
6. [subagent.py](#6-subagentpy)
7. [worker.py](#7-workerpy)
8. [orchestration.py](#8-orchestrationpy)
9. [graph.py](#9-graphpy)
10. [ASCII Data Flow Diagram](#10-ascii-data-flow-diagram)
11. [Cross-Module Dependency Map](#11-cross-module-dependency-map)
12. [Issues Summary](#12-issues-summary)

---

## 1. config.py

**Purpose:** Central configuration system. Loads settings from YAML + environment variables, validates with Pydantic, and exposes a singleton `settings` object used across the entire application.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `ServerConfig` | 12 | NATS URL, DB path, API port, worker threads, reconnect settings |
| `ClientConfig` | 21 | TUI theme, timeouts, retry limit, API key |
| `AuthConfig` | 30 | Master secret path, keystore, KDF iterations |
| `AgentConfig` | 37 | Default model, provider, tool output limits, compaction toggle |
| `PromptConfig` | 51 | NEXUS.md paths, chain depth, file injection, session history |
| `LoggingConfig` | 69 | Log level and format string |
| `ConfigSchema` | 76 | Root model composing all sub-configs |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `get_project_root()` | 87 | Resolves project root relative to `src/nexusagent/config.py` |
| `load_config()` | 92 | Loads YAML, applies env overrides (`NEXUS_*__*`), validates, resolves relative paths |
| `settings` (singleton) | 164 | Module-level `ConfigSchema` instance |

### Internal Dependencies
- `pydantic` (BaseModel, Field, ValidationError)
- `yaml` (safe_load)
- `os`, `pathlib.Path`

### Issues Found
- **Line 129:** Global `NEXUS_` override loop runs *after* section-specific overrides, meaning a bare `NEXUS_API_PORT` would write into the top-level dict (not into `server`), potentially shadowing section keys. The section-specific loop at line 119 only processes keys with `__` separators, so flat keys land in `raw_data` root and may be silently ignored by `ConfigSchema`.
- **Line 136-155:** Relative path resolution is manual and repetitive. A helper function would reduce boilerplate.
- **Line 164:** Singleton is loaded at import time, making it impossible to test with alternate configs without monkeypatching.

---

## 2. models.py

**Purpose:** Pydantic data models for the task lifecycle, agent event streaming protocol, and task contracts. Defines the shared type vocabulary for the entire system.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `TaskStatus` (StrEnum) | 9 | `pending`, `processing`, `completed`, `failed` |
| `TaskSchema` | 16 | Task with id, description, priority, status, timestamps, metadata |
| `MemoryScope` (StrEnum) | 26 | `shared`, `isolated`, `scoped` |
| `TaskContract` | 32 | Full sub-agent contract: tools, turns, wall time, memory, model override, depth, summary mode |
| `ResultSchema` | 56 | Task result with success, data, error, duration |
| `AgentEvent` | 68 | Base event with `type` field |
| `ThinkingEvent` | 72 | `type="thinking"` — busy indicator |
| `ToolCallEvent` | 77 | `type="tool_call"` — tool invocation announcement |
| `ToolResultEvent` | 84 | `type="tool_result"` — tool output |
| `ApprovalRequestEvent` | 91 | `type="approval_request"` — human-in-the-loop gate |
| `ResponseEvent` | 99 | `type="response"` — final agent response |
| `ErrorEvent` | 104 | `type="error"` — error notification |

### Internal Dependencies
- `pydantic` (BaseModel, Field)
- `enum.StrEnum`
- `datetime`

### Issues Found
- **Line 51-53:** `TaskContract.model` and `max_depth` are documented as "P5: Sub-agent improvements" — suggests these are newer additions that may not be fully integrated with the rest of the system.
- **Line 68:** `AgentEvent` uses `type: str` without `Literal`, so subclass type fields are class-level defaults, not enforced at the Pydantic level. A `type="thinking"` field on `ThinkingEvent` is a class attribute, not a Pydantic field — it won't appear in `model_dump()` unless explicitly set.

---

## 3. prompt_loader.py

**Purpose:** Loads and resolves NEXUS.md prompt files with recursive `@file` chain injection. Handles both session initialization (base + project prompts) and chat-time `@file` references.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `PromptLoadError` | 24 | Base exception for prompt loading failures |
| `CircularChainError` | 29 | Raised when a circular `@file` reference is detected |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `resolve_path()` | 34 | Resolves a path string to absolute `Path` |
| `load_prompt_content()` | 43 | Recursively resolves `@file` chains in text, with depth limiting and circular detection |
| `load_nexus_prompt()` | 134 | Loads base `config/NEXUS.md` + project `CWD/NEXUS.md`, resolves chains |
| `inject_file_at_reference()` | 204 | Processes `@file` refs in user chat input |
| `get_file_info_placeholder()` | 234 | Returns a placeholder string for an injected file |

### Internal Dependencies
- `pathlib.Path`
- `logging`

### Issues Found
- **Line 21:** `MAX_FILE_SIZE` is a module-level constant (256KB), but `PromptConfig.max_inject_file_size` (line 60 of config.py) is never used here — the hardcoded value takes precedence, making the config setting dead code.
- **Line 72:** The `@` detection logic (`stripped[1] != " "`) means `@ something` is kept as-is, but `@something` on a non-own-line (indented) is still treated as a file reference. This could cause false positives in indented code blocks.
- **Line 124:** Injected file header includes the full absolute path, which may leak internal directory structure to the LLM.

---

## 4. agent.py

**Purpose:** Core agent factory. Wraps `deepagents.create_deep_agent` with role-based tool filtering and policy-aware access control (permissive/restricted/strict).

### Key Classes

| Class | Line | Description |
|---|---|---|
| `Agent` | 47 | Main agent class with role-based tool access and policy enforcement |

### Key Methods

| Method | Line | Description |
|---|---|---|
| `Agent.__init__()` | 70 | Resolves model name, sets policy context (thread-local), builds tool list, creates inner deep agent |
| `Agent.role` (property) | 106 | Returns the agent's role |
| `Agent.policy` (property) | 110 | Returns the agent's policy |
| `Agent.__call__()` | 113 | Delegates to `self._inner.invoke()` |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `_build_role_tools()` | 24 | Builds tool function list for a given role from the registry |
| `run_agent_task()` | 117 | State-dict entry point: creates Agent from state, invokes, returns result or error |

### Internal Dependencies
- `deepagents.create_deep_agent`
- `nexusagent.config.settings`
- `nexusagent.tools.registry` (`_REGISTRY`, `ROLE_MANIFESTS`, `get_manifest`, `set_policy_context`)
- `nexusagent.tools.register_all` (side-effect import)

### Issues Found
- **Line 89-90:** Google model auto-prefix logic (`google_genai:`) is a brittle heuristic. It checks for `gemini` or `gemma` prefixes but doesn't handle model names like `google/gemini-*` or custom model names that happen to start with those strings.
- **Line 38-41:** `_ROLE_TOOLS` is built at import time for all roles in `ROLE_MANIFESTS`. If a tool is registered *after* this module is imported, it won't appear in any role's tool list.
- **Line 117-134:** `run_agent_task` catches all exceptions and returns them as `{"error": ...}` dicts, which means callers must check for the `error` key — easy to miss. The `logger` variable is used at line 132 but only defined inside the `except` block, which works but is inconsistent with the module-level pattern used elsewhere.
- **Line 98-101:** `create_deep_agent` is called with only `model` and `tools` — no custom middleware, no system prompt injection (that's handled by `Session` instead).

---

## 5. session.py

**Purpose:** Interactive session management. Handles the full lifecycle of a user↔agent conversation: message routing, streaming, event emission, approval gates, cancellation, compaction, and memory.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `Session` | 161 | Single interactive conversation session |
| `SessionManager` | 555 | Lifecycle cache for Session instances (create, get, idle, close) |

### Key Methods — Session

| Method | Line | Description |
|---|---|---|
| `__init__()` | 167 | Initializes session with ID, working dir, agent, memory, DB repo, hybrid memory |
| `_load_system_prompt()` | 205 | Loads and caches the NEXUS.md system prompt |
| `_build_context_injection()` | 225 | Builds environment + session history context block |
| `_process_chat_input()` | 238 | Handles `@file` injection in user messages |
| `send()` | 266 | **Main entry point**: processes user message, builds context, streams agent, emits events |
| `_handle_message_token()` | 412 | Processes streaming tokens: tool calls, tool results, text chunks |
| `_handle_update()` | 467 | Processes node-level update chunks for status tracking |
| `pre_compaction_flush()` | 493 | Flushes session state to daily log before context compaction |
| `approve()` | 507 | Records approval decision for a pending tool call |
| `interrupt()` | 522 | Requests cancellation of current agent invocation |
| `close()` | 528 | Closes session, updates DB, signals end of stream |
| `event_stream()` | 540 | Async generator yielding events from internal queue |

### Key Methods — SessionManager

| Method | Line | Description |
|---|---|---|
| `get()` | 565 | Returns cached session by ID |
| `get_or_create()` | 572 | Thread-safe session creation with double-checked locking |
| `mark_idle()` | 608 | Transitions session to idle status |
| `close()` | 619 | Closes and removes session from cache |
| `active_count` (property) | 626 | Number of cached sessions |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `_extract_agent_response()` | 29 | Extracts last assistant message from various result formats |
| `_get_git_info()` | 73 | Gets git branch and status summary |
| `_build_environment_context()` | 99 | Builds environment context block (dir, user, OS, time, git, tools) |
| `_build_session_history_context()` | 145 | **Stub** — returns empty string (not yet implemented) |

### Internal Dependencies
- `langchain_core.messages` (SystemMessage, HumanMessage, AIMessage)
- `nexusagent.config.settings`
- `nexusagent.models` (ErrorEvent, ResponseEvent, ThinkingEvent)
- `nexusagent.prompt_loader` (inject_file_at_reference, load_nexus_prompt)
- `nexusagent.memory.HybridMemoryManager`
- `nexusagent.compaction` (CompactionPipeline, pre_compaction_flush)

### Issues Found
- **Line 145-158:** `_build_session_history_context()` is a stub that always returns `""`. The comment says "in production you'd query the session DB" — this means session continuity across conversations is not actually implemented.
- **Line 29-70:** `_extract_agent_response()` is a complex, nested extraction function that handles str, list, dict, and BaseMessage types. It's fragile and could silently return unexpected formats.
- **Line 349-353:** `astream()` is called with `subgraphs=True` and `version="v2"` — these are deepagents-specific options that may change across versions.
- **Line 380:** Fallback message `"Tool execution completed."` is hardcoded — if the agent genuinely produces no text, this could be confusing.
- **Line 500:** `pre_compaction_flush()` uses `asyncio.get_event_loop().time()` which is wall-clock time, not a meaningful timestamp for a summary.
- **Line 201:** `_conversation_history` is a plain list that grows unbounded until trimmed at line 389-390. If `max_conversation_history` is large, memory usage could be significant.

---

## 6. subagent.py

**Purpose:** Control interface for spawned worker agents. Provides lifecycle management (pending → running → completed/failed/cancelled), cancellation signaling, and synchronous/async waiting.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `SubAgentStatus` (StrEnum) | 15 | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `SubAgentHandle` | 25 | Control handle for a spawned sub-agent worker |

### Key Methods

| Method | Line | Description |
|---|---|---|
| `__init__()` | 33 | Initializes handle with worker ID, contract, depth, and async events |
| `status` (property) | 52 | Current lifecycle state |
| `result` (property) | 56 | Returns full result or summary depending on `contract.summary_only` |
| `is_done()` | 78 | True if in terminal state |
| `can_spawn_child()` | 90 | True if depth < max_depth |
| `cancel()` | 96 | Signals cancellation |
| `wait()` | 113 | Async wait with timeout, raises on failure/cancellation |
| `_mark_running()` | 130 | State transition: PENDING → RUNNING |
| `_mark_completed()` | 137 | State transition: → COMPLETED |
| `_mark_failed()` | 147 | State transition: → FAILED |
| `_generate_summary()` | 154 | Truncates result to 500 chars for summary-only mode |

### Internal Dependencies
- `nexusagent.models.TaskContract`
- `asyncio`

### Issues Found
- **Line 154-161:** `_generate_summary()` is a naive truncation at 500 characters. It doesn't attempt any intelligent summarization — just cuts off mid-sentence. For complex results, this loses critical information.
- **Line 74:** `model` property falls back to `os.getenv("AGENT_MODEL", ...)` but doesn't check `settings.agent.default_model`, creating an inconsistency with how the main `Agent` class resolves its model (line 85 of agent.py).
- **Line 132-134:** `_markRunning()` raises `RuntimeError` if not in PENDING state, but `_mark_completed` and `_mark_failed` have no such guard — inconsistent state machine enforcement.

---

## 7. worker.py

**Purpose:** NATS-backed task worker and worker pool. Receives tasks from the message bus, routes them to the agent or research workflow, and manages execution with circuit breakers, heartbeats, and bounded retries.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `NexusWorker` | 79 | NATS message bus worker that receives and processes tasks |
| `WorkerPool` | 207 | Manages a pool of isolated sub-agent workers with semaphore-based concurrency |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `_run_agent_task()` | 26 | Shared agent execution entry point — routes research tasks to LangGraph, coding tasks to deepagents |
| `_run_research_workflow()` | 56 | Executes a research task through the LangGraph state machine |

### Key Methods — NexusWorker

| Method | Line | Description |
|---|---|---|
| `start()` | 83 | Connects to NATS, subscribes to `tasks.submit` |
| `_execute_agent_logic()` | 96 | Wraps agent call with retry + circuit breaker |
| `_heartbeat()` | 105 | Periodically bumps task `updated_at` to prevent reaper cleanup |
| `handle_task()` | 120 | Main NATS callback: parses task, executes, persists result |

### Key Methods — WorkerPool

| Method | Line | Description |
|---|---|---|
| `spawn()` | 216 | Spawns an isolated worker, returns `SubAgentHandle` |
| `_run_worker()` | 236 | Runs a worker to completion within contract bounds |
| `_execute_bounded()` | 258 | Executes with turn counting, wall time, and cancellation checks |
| `list_active()` | 299 | Returns list of active worker handles |

### Internal Dependencies
- `nexusagent.agent.run_agent_task`
- `nexusagent.bus.AgentBus`, `get_bus`
- `nexusagent.db.TaskModel`, `task_repo`
- `nexusagent.models` (ResultSchema, TaskContract, TaskSchema, TaskStatus)
- `nexusagent.subagent.SubAgentHandle`
- `nexusagent.utils.CircuitBreaker`, `retry_with_backoff`
- `nexusagent.graph.create_research_graph`

### Issues Found
- **Line 26-53:** `_run_agent_task` is a module-level function that duplicates routing logic. Both `NexusWorker._execute_agent_logic` and `WorkerPool._execute_bounded` call it, but `WorkerPool` also has its own turn-counting loop — this means tasks routed through `WorkerPool` get double-wrapped in retry/circuit-breaker logic.
- **Line 41-44:** Research task detection uses a hardcoded keyword list (`"research"`, `"investigate"`, etc.) — fragile and not configurable.
- **Line 105-118:** Heartbeat runs every 30 seconds but silently swallows all exceptions. If the DB connection is permanently lost, the heartbeat will keep failing silently until the task completes.
- **Line 223-227:** `spawn()` checks `depth >= contract.max_depth` but the error message says "Cannot spawn worker" — it should say "Cannot spawn *child* worker" for clarity.
- **Line 288:** The turn loop checks `result.get("status") == "complete"` but `run_agent_task` returns `{"result": ...}` — there's no `"status"` key, so this condition is never true and the loop always runs to `max_turns`.

---

## 8. orchestration.py

**Purpose:** Deep Research orchestrator implementing a multi-phase research workflow (Intent → Planning → Refinement → Execution → Synthesis). Provides the research logic that the LangGraph nodes call into.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `SearchResult` | 19 | A single search result with URL, title, snippet, optional content |
| `ResearchPlan` | 28 | Research plan with thesis, objective, steps, expected outcomes |
| `ResearchState` | 35 | Mutable research state: query, plan, gathered data, synthesis |
| `DeepResearchOrchestrator` | 47 | Main orchestrator implementing the deep research workflow |

### Key Methods

| Method | Line | Description |
|---|---|---|
| `run_deep_research()` | 53 | Full pipeline: plan → refine → execute loop → synthesize |
| `_search()` | 89 | Web search via `search_web` tool |
| `_fetch()` | 98 | **Stub** — always returns `None` |
| `_generate_plan()` | 103 | LLM generates a research plan from query |
| `_refine_plan()` | 125 | LLM reviews and refines the plan |
| `_parse_plan_response()` | 141 | Parses LLM JSON response into `ResearchPlan` |
| `_default_plan()` | 147 | Fallback plan when LLM parsing fails |
| `_synthesize_report()` | 160 | LLM synthesizes final report from gathered evidence |

### Internal Dependencies
- `nexusagent.llm.llm`
- `nexusagent.tools.research.search_web`

### Issues Found
- **Line 98-101:** `_fetch()` is a stub that always returns `None`. The research workflow relies entirely on search snippets — no actual page content is fetched. The `execute_node` in graph.py calls `_fetch` for top results, but the content is always discarded.
- **Line 66:** User approval is commented as "Simulated/Triggered" and always proceeds. There's no actual pause mechanism — the plan is always auto-approved.
- **Line 93-96:** `_search()` wraps the entire `search_web` result in a single `SearchResult` with `url="search"` — losing all individual result URLs and structure.
- **Line 143:** `_parse_plan_response()` uses `re.search(r"\{.*\}", content, re.DOTALL)` which is greedy and will match from the first `{` to the last `}` in the response, potentially capturing extra text if the LLM includes multiple JSON blocks.
- **Line 164:** Template loading uses a hardcoded path relative to `orchestration.py` — if templates are missing, a generic fallback is used with no warning.

---

## 9. graph.py

**Purpose:** LangGraph state machine for durable, checkpointed research workflows. Defines the graph topology (plan → refine → execute loop → synthesize) with SQLite-based checkpointing for crash recovery.

### Key Classes

| Class | Line | Description |
|---|---|---|
| `ResearchGraphState` (TypedDict) | 38 | State flowing through graph nodes: query, plan, step index, gathered data, synthesis, error |

### Key Functions

| Function | Line | Description |
|---|---|---|
| `plan_node()` | 61 | Async node: generates research plan via `DeepResearchOrchestrator._generate_plan()` |
| `refine_node()` | 82 | Async node: refines plan via `DeepResearchOrchestrator._refine_plan()` |
| `execute_node()` | 106 | Async node: executes one research step (search + fetch), increments counter |
| `synthesize_node()` | 160 | Async node: synthesizes final report via `DeepResearchOrchestrator._synthesize_report()` |
| `route_after_execute()` | 193 | Conditional edge: loops back to execute or proceeds to synthesize |
| `create_research_graph()` | 208 | Builds and compiles the research state machine with SQLite checkpointing |

### Internal Dependencies
- `langgraph.checkpoint.sqlite.SqliteSaver`
- `langgraph.graph` (END, START, StateGraph)
- `nexusagent.orchestration.DeepResearchOrchestrator`

### Issues Found
- **Line 242-245:** Checkpoint DB uses `:memory:` by default, which means checkpoints are lost when the process restarts. The `db_path` parameter exists but is never passed from `worker.py` (line 60-61 of worker.py calls `create_research_graph()` with no arguments).
- **Line 218:** The workflow uses `StateGraph(dict)` instead of `StateGraph(ResearchGraphState)` — the TypedDict is defined but not used for type checking in the graph.
- **Line 103:** If `refine_node` fails, it returns `{"plan_approved": True, "error": None}` — silently proceeding with the original plan. This is resilient but means refinement failures are invisible.
- **Line 193-205:** `route_after_execute` doesn't check for errors — if a step fails, it still loops. Only step exhaustion triggers synthesis.

---

## 10. ASCII Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NEXUSAGENT DATA FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

                              USER MESSAGE
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       SessionManager         │
                    │  (get_or_create / cache)     │
                    │  session.py:555              │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │          Session             │
                    │  session.py:161              │
                    │                              │
                    │  1. Process @file injection  │
                    │  2. Load system prompt       │
                    │  3. Build context block      │
                    │  4. Recall memory            │
                    │  5. Check compaction         │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │        Agent                 │
                    │  agent.py:47                 │
                    │                              │
                    │  • Role-based tool filtering │
                    │  • Policy enforcement        │
                    │  • Model resolution          │
                    │  • Wraps deepagents          │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     deepagents (inner)       │
                    │                              │
                    │  astream() → token stream    │
                    │  ┌────────────────────────┐  │
                    │  │  LLM (Gemini/etc.)    │  │
                    │  │  ┌──────────────────┐  │  │
                    │  │  │  Tool Calls      │──┼──┼──► Tool Execution
                    │  │  │  Text Tokens     │  │  │    (file, shell, etc.)
                    │  │  │  Thinking        │  │  │         │
                    │  │  └──────────────────┘  │  │         │
                    │  └────────────────────────┘  │         │
                    └──────────────────────────────┘         │
                                   │                         │
                                   ▼                         │
                    ┌──────────────────────────────┐         │
                    │   Event Stream (Session)     │◄────────┘
                    │                              │
                    │  • thinking                  │
                    │  • tool_call                 │
                    │  • tool_result               │
                    │  • response_chunk            │
                    │  • response (final)          │
                    │  • error                     │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   Persistence & Memory       │
                    │                              │
                    │  • DB (task_repo)            │
                    │  • HybridMemoryManager       │
                    │  • Conversation history      │
                    └──────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                     TASK / WORKER PATH (NATS)                              │
└─────────────────────────────────────────────────────────────────────────────┘

                    NATS Message Bus
                    (tasks.submit subject)
                           │
                           ▼
                    ┌──────────────────┐
                    │  NexusWorker     │
                    │  worker.py:79    │
                    │                  │
                    │  Circuit breaker │
                    │  Heartbeat       │
                    │  Retry logic     │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │ Research?  │  │  Coding?   │  │  Worker    │
     │            │  │            │  │  Pool      │
     │  graph.py  │  │  agent.py  │  │  worker.py │
     │  LangGraph │  │  run_agent │  │  :207      │
     │  workflow  │  │  _task()   │  │            │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           ▼               │               ▼
     ┌────────────┐        │        ┌────────────┐
     │orchestratn │        │        │SubAgent    │
     │.py         │        │        │Handle      │
     │            │        │        │subagent.py │
     │ • plan     │        │        │            │
     │ • refine   │        │        │ • cancel   │
     │ • execute  │        │        │ • wait     │
     │ • synthesize│       │        │ • status   │
     └────────────┘        │        └────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │  ResultSchema    │
                    │  models.py:56    │
                    │                  │
                    │  • DB persist    │
                    │  • NATS KV store │
                    └──────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONFIG & PROMPT LOADING                                │
└─────────────────────────────────────────────────────────────────────────────┘

     config/nexusagent.yaml          NEXUS.md files
            │                              │
            ▼                              ▼
     ┌──────────────┐              ┌──────────────┐
     │  config.py   │              │prompt_loader │
     │  load_config │              │.py           │
     │              │              │              │
     │  + env vars  │              │  + @ chains  │
     │  + validate  │              │  + circular  │
     │  = settings  │              │    detection │
     └──────────────┘              └──────────────┘
            │                              │
            └──────────┬───────────────────┘
                       │
                       ▼
              Session._load_system_prompt()
              Session._build_context_injection()
```

---

## 11. Cross-Module Dependency Map

```
config.py ◄──── settings singleton ────► agent.py, session.py, worker.py
    │                                        │
    │                                        │
models.py ◄──── TaskSchema, TaskContract ──► worker.py, subagent.py
    │                                        │
    │           ┌────────────────────────────┘
    │           │
    │           ▼
    │    session.py ◄──── Session, SessionManager
    │           │
    │           │ uses
    │           ▼
    │    prompt_loader.py ◄──── load_nexus_prompt, inject_file_at_reference
    │           │
    │           │ uses
    │           ▼
    │    agent.py ◄──── Agent, run_agent_task
    │           │
    │           │ wraps
    │           ▼
    │    deepagents (external library)
    │
    ├──────────────────────────────────────────┐
    │                                          │
    ▼                                          ▼
orchestration.py ◄──── DeepResearchOrchestrator
    │                      │
    │                      │ uses
    │                      ▼
    │              nexusagent.llm.llm
    │              nexusagent.tools.research
    │
    │ called by
    ▼
graph.py ◄──── ResearchGraphState, create_research_graph
    │
    │ called by
    ▼
worker.py ◄──── NexusWorker, WorkerPool
    │
    │ uses
    ▼
subagent.py ◄──── SubAgentHandle
```

---

## 12. Issues Summary

### Critical Issues

| # | File | Line | Issue |
|---|---|---|---|
| 1 | `worker.py` | 288 | Turn loop checks `result.get("status") == "complete"` but `run_agent_task` never returns a `"status"` key — loop always runs to `max_turns` |
| 2 | `graph.py` | 242-245 | Default checkpoint DB is `:memory:` — crash recovery is never active because `worker.py` never passes `db_path` |
| 3 | `orchestration.py` | 98-101 | `_fetch()` is a stub — research workflow has no actual page content, only snippets |

### Design Issues

| # | File | Line | Issue |
|---|---|---|---|
| 4 | `config.py` | 129 | Global `NEXUS_` env override can write to wrong nesting level |
| 5 | `config.py` | 164 | Singleton loaded at import time — untestable without monkeypatching |
| 6 | `agent.py` | 38-41 | `_ROLE_TOOLS` built at import time — late-registered tools are invisible |
| 7 | `agent.py` | 89-90 | Google model auto-prefix is a brittle string heuristic |
| 8 | `session.py` | 145-158 | `_build_session_history_context()` is a stub — no cross-session continuity |
| 9 | `subagent.py` | 154-161 | `_generate_summary()` is naive truncation, not real summarization |
| 10 | `subagent.py` | 74 | Model fallback doesn't use `settings.agent.default_model` |
| 11 | `worker.py` | 26-53 | Double-wrapped retry/circuit-breaker when `WorkerPool` calls `_run_agent_task` |
| 12 | `worker.py` | 41-44 | Research task detection uses hardcoded keywords |
| 13 | `prompt_loader.py` | 21 | `MAX_FILE_SIZE` hardcoded, config setting `max_inject_file_size` is dead code |
| 14 | `orchestration.py` | 93-96 | `_search()` wraps all results in a single `SearchResult` with fake URL |
| 15 | `orchestration.py` | 143 | Greedy regex for JSON parsing can capture extra text |

### Minor Issues

| # | File | Line | Issue |
|---|---|---|---|
| 16 | `models.py` | 68 | `AgentEvent.type` not enforced as `Literal` — subclass type fields are class attrs, not Pydantic fields |
| 17 | `session.py` | 29-70 | `_extract_agent_response()` is fragile nested extraction |
| 18 | `session.py` | 380 | Hardcoded fallback message `"Tool execution completed."` |
| 19 | `session.py` | 500 | `pre_compaction_flush` uses `asyncio.get_event_loop().time()` — not a meaningful timestamp |
| 20 | `subagent.py` | 132-134 | Inconsistent state machine guards (`_mark_running` checks, `_mark_completed`/`_mark_failed` don't) |
| 21 | `graph.py` | 218 | `StateGraph(dict)` instead of `StateGraph(ResearchGraphState)` — TypedDict unused |
| 22 | `prompt_loader.py` | 124 | Injected file header leaks absolute paths to LLM |
| 23 | `config.py` | 136-155 | Repetitive relative-path resolution boilerplate |
