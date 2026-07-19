# Current State — NexusAgent Architecture (pre-migration)

> **Date:** 2026-07-19  
> **Scope:** Full architectural inventory of the existing system  
> **Purpose:** Baseline documentation for the 12-phase migration to a distributed autonomous agent runtime platform

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Entry Points](#entry-points)
3. [Application Lifecycle](#application-lifecycle)
4. [Agent Creation & Lifecycle](#agent-creation--lifecycle)
5. [Session Management](#session-management)
6. [WebSocket Handling](#websocket-handling)
7. [Worker System](#worker-system)
8. [Tool Registration & Execution](#tool-registration--execution)
9. [LangGraph Integration](#langgraph-integration)
10. [Memory System](#memory-system)
11. [Persistence Layer](#persistence-layer)
12. [NATS Event Bus](#nats-event-bus)
13. [Configuration Management](#configuration-management)
14. [Hooks System](#hooks-system)
15. [LLM Bridge](#llm-bridge)
16. [CLI & SDK](#cli--sdk)
17. [Testing Infrastructure](#testing-infrastructure)
18. [Global State Registry](#global-state-registry)
19. [Known Limitations](#known-limitations)

---

## System Overview

NexusAgent is a **production-grade AI coding agent platform** that combines:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | `deepagents` + LangChain | Core LLM agent execution |
| State Machine | LangGraph + SqliteSaver | Checkpointed research workflows |
| API Server | FastAPI (uvicorn) | REST + WebSocket endpoints |
| TUI | Textual | Terminal user interface |
| CLI | Click | Command-line tooling |
| Message Bus | NATS JetStream | Async task distribution |
| Database | SQLAlchemy async + aiosqlite | Session & task persistence |
| Memory | Hybrid (file + vector) | Persistent organizational memory |
| Config | Pydantic + YAML + env | Three-tier configuration |

**Package:** `nexusagent` (src layout)  
**Language:** Python 3.13+  
**Tests:** ~680 passing / ~11 pre-existing fail (across 63+ test files)  
**Lines of code:** ~23,800 across ~108 source files

---

## Entry Points

The system has **three independent entry points** — there is no unified runtime that owns them:

### 1. Server — `nexusagent.server`

```
$ python3 -m nexusagent.server          # via __main__.py
$ nexus-server                           # via pyproject.toml scripts
```

Entry: `server/server.py:run()` → `uvicorn.run(app, ...)`

**Starts:**
- FastAPI app with WebSocket endpoint
- Lifespan: DB init → NATS connect → background NexusWorker

### 2. CLI — `nexusagent.interfaces.cli`

```
$ nexus <command>                        # via pyproject.toml scripts
```

Entry: `interfaces/cli.py:main()` → Click group

**Subcommands:**
- `submit <task>` — Submit task to server via REST
- `run <task>` — Run agent locally (no server needed)
- `session list|resume|fork|rename|delete` — Manage sessions
- `hook` — Manage hook lifecycle
- `completions` — Shell completions

### 3. TUI — `nexusagent.interfaces.tui`

```
$ nexus tui                              # via CLI subcommand
```

Entry: `interfaces/tui/app.py:NexusApp` → Textual App

**Architecture:**
- Async WebSocket client connects to server
- Streaming response rendering
- Message types: user, assistant, tool, error, welcome, app
- Modal switchers for threads and models

### 4. Web UI (separate) — `nexusagent.interfaces.web_ui`

Gradio-based web interface (secondary, less developed).

---

## Application Lifecycle

There is **no centralized lifecycle manager**. Startup is distributed:

### Server Startup (`server/server.py:lifespan`)

```
FastAPI lifespan context manager
    │
    ├── 1. Initialize DB manager (get_db_manager → init_db)
    ├── 2. Connect NATS bus (get_bus → connect)
    ├── 3. Start NexusWorker (NexusWorker → create_task → start)
    │       └── Subscribes to "tasks.submit" durable consumer
    │       └── Starts health monitoring loop
    ├── 4. Register routes (register_routes)
    │       └── Rate limiting middleware
    │       └── REST endpoints: /tasks, /health, /version
    │       └── WebSocket: /sessions/{session_id}/ws
    └── 5. Yield (server runs)
```

### CLI Local Startup (`interfaces/cli.py:run`)

```
CLI run command
    ├── 1. Load config (ensure_user_config_exists → load_config)
    ├── 2. Create WorkerPool
    ├── 3. Create TaskContract
    ├── 4. Spawn worker via WorkerPool.spawn()
    └── 5. Wait for result
```

### TUI Startup

```
NexusApp (Textual)
    ├── 1. Version preflight check
    ├── 2. Check server via /version endpoint
    ├── 3. Connect WebSocket
    └── 4. Mount UI components
```

**Shutdown is equally distributed** — no central shutdown sequence. Server lifespan finally block cancels worker task and closes NATS. Sessions close on disconnect.

---

## Agent Creation & Lifecycle

### The `Agent` Class (`core/agent.py`, 452 lines)

```
Agent
    │
    ├── async __init__(role, policy, model_override, provider_override, ...):
    │       ├── _ensure_tools_registered()   → module-level guard
    │       ├── set_policy_context(role, policy)
    │       ├── registry.freeze()             → snapshot tools
    │       ├── get_manifest(role)            → build role tool list
    │       ├── create_deep_agent(...)        → deepagents wrapper
    │       └── apply_provider_profile(...)   → provider config
    │
    ├── role → str
    ├── policy → str
    ├── __call__(*args, **kwargs)             → agent invocation
    ├── astream(*args, **kwargs)              → streaming invocation
    └── (no explicit destroy — garbage collected)
```

**Key observations:**
- `__init__` is async — returns after MCP tools are loaded
- Agent is created **per-session** (WebSocket handler creates `Agent()`)
- State lives in `deepagents` internal state + LangChain state
- No explicit lifecycle beyond construction → call → destruction
- Agent wraps `create_deep_agent()` from the `deepagents` library

### `run_agent_task()` (`core/agent.py`, free function)

```
run_agent_task(state: dict) → dict
    │
    ├── Extracts role, policy, model/provider overrides from state dict
    ├── Loads NEXUS.md prompt
    ├── Builds environment context
    ├── Creates Agent() on the fly
    ├── Builds message list (system + human)
    ├── Calls agent.astream()
    └── Returns result dict
```

This is the **primary entry point** for both the NATS worker and the CLI `run` command. It's a free function with no owning context.

### Agent Lifecycle Gaps

| Concern | Current State |
|---------|--------------|
| Creation | Ad-hoc — created whenever `run_agent_task()` or `Agent()` is called |
| Destruction | Implicit (GC) — no cleanup hook |
| State persistence | None — agent carries no state between invocations |
| Identity | None — no agent ID |
| Execution boundary | None — agent has raw tool access, filtered only by policy |
| Error isolation | Limited — circuit breaker wraps execution but no full isolation |

---

## Session Management

### `SessionBase` (`core/session/session_base.py`, 209 lines)

Shared base for both interactive sessions and workers:

```
SessionBase
    │
    ├── session_id: str
    ├── working_dir: str
    ├── _memory_dir: Path
    ├── _parent_memory_dir: Optional[Path]
    ├── hybrid_memory: HybridMemoryManager
    ├── _llm_extractor: Optional[LLMExtractor]
    ├── _compaction: CompactionPipeline
    ├── _turn_count: int
    │
    ├── get_memory_context(query) → str
    ├── remember(content, type, ...) → memory_id
    ├── extract_and_store(user_msg, response) → int
    ├── maybe_dream() → run dream cycle
    ├── pre_compaction_flush() → str
    ├── get_load_context() → NEXUS.md + env
    └── close() → cleanup
```

### `Session` (`core/session/session.py`, 707 lines)

Extends `SessionBase` with interactive features:

```
Session(SessionBase)
    │
    ├── __init__(session_id, working_dir, tool_env, hook_manager, ...):
    │       ├── self.agent = Agent(role, policy, ...)   ← creates agent eagerly
    │       ├── self._messages: list                     ← conversation history
    │       ├── self._pending_approvals: dict            ← approval gates
    │       ├── self._event_queue: asyncio.Queue          ← event streaming
    │       └── self._cached_memories: list              ← pre-fetched memory
    │
    ├── send(user_message) → None                        ← main message loop
    │       ├── Preprocess input
    │       ├── Build message list (cached memories + history)
    │       ├── Apply compaction if needed
    │       ├── _stream_agent_response() → stream tokens/events
    │       ├── Post-process: extract, dream cycle
    │       └── Enqueue events
    │
    ├── approve(call_id, approved) → None                ← approval gate
    ├── answer(call_id, answer_text) → None              ← user answer
    ├── interrupt() → None                               ← cancel streaming
    ├── close() → cleanup
    ├── event_stream() → async generator                 ← SSE events
    └── _handle_send_error(exc) → error handling
```

### `SessionManager` (`core/session/manager.py`, 286 lines)

Global singleton managing session lifecycle:

```
SessionManager
    │
    ├── _sessions: dict[str, Session]
    ├── _idle_timeout: float
    │
    ├── get(session_id) → Session | None
    ├── get_or_create(session_id, ...) → Session         ← creates Agent, SessionBase
    ├── mark_idle(session_id)
    ├── close(session_id)
    └── active_count() → int
```

**Pattern:** `get_session_manager()` / `set_session_manager()` — lazy-init singleton.

### Session Lifecycle

```
CLIENT → WebSocket Connect (or TUI start)
    │
    ├── SessionManager.get_or_create(session_id)
    │       ├── Creates new Session if not found
    │       │       ├── Creates HybridMemoryManager
    │       │       ├── Creates Agent (deepagents wrapper)
    │       │       ├── Loads NEXUS.md
    │       │       └── Pre-fetches cross-session memories
    │       └── Returns existing Session if found
    │
    ├── Session.send(message) loop
    │       ├── Processes user input
    │       ├── Streams agent response
    │       ├── Enqueues events to client
    │       └── Runs extraction + dream cycle
    │
    └── Session.close()
            ├── HybridMemoryManager.close()
            └── Removed from SessionManager
```

---

## WebSocket Handling

### `session_websocket()` (`server/websocket.py`)

```
WebSocket /sessions/{session_id}/ws
    │
    ├── Auth: X-API-Key, Bearer token, or ?token= query param
    ├── Accept WebSocket
    ├── SessionManager.get_or_create(session_id, ...)
    ├── Message loop:
    │       ├── Receive: {type: "message", content: str, images?: [...]}
    │       ├── Execute: session.send(content)
    │       ├── Stream: session.event_stream() → JSON events
    │       │       ├── token: streaming text chunks
    │       │       ├── error: error events
    │       │       ├── done: completion signal
    │       │       ├── approval_required: tool approval gate
    │       │       └── answer_required: user input needed
    │       └── Receive: {type: "approve"|"answer"|"interrupt"}
    │
    └── Disconnect: session.close()
```

**Key observations:**
- WebSocket handler creates Agent directly via SessionManager → Session
- SessionManager is a global singleton
- No rate limiting on WebSocket (REST endpoints have rate limiting)
- Workspace root is set via `set_workspace_root()` before session creation

---

## Worker System

There are **two worker abstractions** with different purposes:

### 1. `NexusWorker` (`core/worker/worker.py`, 349 lines)

```python
class NexusWorker:
    """Background worker subscribed to NATS for durable task processing."""

    def __init__(self, bus=None):
        self.bus = bus or get_bus()
        self._healthy = True
        self._degraded = False
        ...

    async def start(self):
        # Subscribe to "tasks.submit" durable consumer
        await self.bus.subscribe_durable("tasks.submit", "nexus-worker", self.handle_task)
        # Start health loop
        asyncio.create_task(self._health_loop())

    async def handle_task(self, msg):
        # Receive TaskSchema from NATS
        # Check budget guard
        # Execute agent logic
        # Publish result back via NATS
```

**Pattern:** `get_worker()` / `set_worker()` — global singleton.

**Lifecycle:**
```
NexusWorker.start()
    ├── Subscribe to "tasks.submit" (durable consumer)
    ├── Health monitoring loop (NATS ping every 10s)
    └── On message: handle_task → _execute_agent_logic → _run_agent_task
```

**Limitations:**
- Runs as background task inside server process (not separate process)
- No isolation — shares memory space with server
- No worker identity beyond the singleton
- Recovery is reactive (NATS auto-reconnect) not proactive

### 2. `WorkerPool` (`core/worker/pool.py`, 140 lines)

```python
class WorkerPool:
    """Local process pool for spawning sub-agents."""

    def __init__(self, max_workers: int = 4):
        self._workers: dict[str, asyncio.Task] = {}
        self._active: dict[str, SubAgentHandle] = {}
        self._max_workers = max_workers
        self._lock = asyncio.Lock()

    async def spawn(self, contract, depth=0) -> SubAgentHandle:
        # Create SubAgentHandle
        # Start _run_worker in background task
        # Track in _workers dict

    async def _run_worker(self, handle):
        # Run handler._run_agent_task with timeout
        # Handle failures, timeouts
        # Cancel on session end

    def list_active(self) -> list[SubAgentHandle]:
        return list(self._active.values())
```

**Pattern:** `get_worker_pool()` / `set_worker_pool()` — global singleton.

### 3. SubAgentHandle (`core/subagent.py`, 196 lines)

```python
class SubAgentHandle:
    """Control handle for a spawned sub-agent worker."""

    def __init__(self, worker_id, contract, depth=0):
        self.worker_id = worker_id
        self.contract = contract
        self.depth = depth
        self.status = SubAgentStatus.PENDING
        self.result: Optional[str] = None
        ...

    async def wait(self) -> str:        # Wait for completion
    def cancel(self) -> None:            # Cancel execution
    def is_done(self) -> bool:           # Check completion
```

**States:** PENDING → RUNNING → COMPLETED | FAILED | CANCELLED

### 4. Task Handler (`core/worker/handler.py`, 129 lines)

Shared execution entry point used by both NexusWorker and WorkerPool:

```
_run_agent_task(task: TaskSchema) → str
    │
    ├── Route: research → LangGraph workflow
    │            code → run_agent_task() (deepagents Agent)
    │
    ├── Research path:
    │       create_research_graph() → graph.ainvoke()
    │
    ├── Code path:
    │       Create SessionBase for memory
    │       run_agent_task(state) → Agent execution
    │       Post-turn: extract + dream + close
    │
    └── Protected by module-level CircuitBreaker
         (5 failures → 30s recovery)
```

---

## Tool Registration & Execution

### Tool Registration Flow

```
Module import chain (one-time at first Agent creation):
    import nexusagent.tools.register_all  # noqa: F401
        │
        ├── import nexusagent.tools.write_todos  → @register_tool decorator
        ├── _memory_rate_limiter = MemoryRateLimiter(...)
        │
        ├── register_all():
        │       ├── Iterate TOOL_SPECS (static tool definitions)
        │       ├── register_tool(name, ...)(func) for each
        │       └── registry.freeze()
        │
        └── MCP tools:
                register_mcp_tools()  (discovered from config)
```

### Tool Registry (`tools/registry/`)

```
tools/registry/
    ├── __init__.py          → exports: registry, ToolRegistry, ToolInfo, policy, search
    ├── core.py              → ToolRegistry class (singleton instance: `registry`)
    ├── types.py             → ToolInfo dataclass (frozen, trust/provenance)
    ├── policy.py            → Policy enforcement: ROLE_MANIFESTS, check_tool_access
    └── search.py            → tool_search() with auto-correction
```

```python
class ToolRegistry:
    """Thread-safe tool registry with frozen snapshot support."""

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._lock = threading.RLock()
        self._frozen: bool = False

    def register(self, name, tool_info) -> None:  # Thread-safe with RLock
    def freeze(self) -> None:                      # Snapshot for consistency
    def get_snapshot(self) -> dict:                 # Thread-safe read
    def prune(self, names: set) -> None:            # Remove tools

    # Export as read-only proxy:
    _REGISTRY: MappingProxyType[str, ToolInfo] = _registry_proxy()
```

### Tool Policy Levels

| Level | Discovery | Execution |
|-------|-----------|-----------|
| **permissive** (default) | Shows only in-scope tools | Auto-unlocks on first call |
| **restricted** (sub-agents) | Shows only in-scope tools | Enforces scope at call time |
| **strict** (sandboxed) | Same as restricted | Locked to initial manifest forever |

### Tool Execution Flow

```
Agent.astream()
    │
    ├── LLM requests tool call
    ├── Agent routes to registered tool function
    ├── check_tool_access(role, tool_name) → Permission check
    │       ├── permissive: auto-allow
    │       ├── restricted: check ROLE_MANIFESTS
    │       └── strict: deny if not in manifest
    └── Tool function executes (with workspace path jail)
```

### Dynamic Tools

Tools registered inline via `@register_tool` decorator:
- `spawn_subagent` — Sub-agent delegation
- `ask_user` — User interaction
- `approve` — Approval gating
- `memory_remember`, `memory_search`, etc. — Memory operations
- `write_todos`, `read_todos` — Todo management

---

## LangGraph Integration

### Research Graph (`core/graph.py`)

```python
ResearchGraphState(TypedDict):
    query: str
    template_type: str
    plan: dict
    current_index: int
    search_results: list
    gathered_data: list
    synthesis: str
    error: str | None

Nodes:
    plan_node      → Generate research plan
    refine_node    → Refine for blind spots
    execute_node   → Execute one research step
    synthesize_node → Synthesize into report

Edges:
    START → plan → refine → execute → (conditional)
        ├── more steps → execute (loop)
        └── done → synthesize → END

Checkpoint: SqliteSaver
```

### Usage

- Research tasks routed through this graph by `_run_agent_task()`
- Each node uses the `DeepResearchOrchestrator` from `orchestration.py`
- Not used for code/agent tasks — only research workflows

---

## Memory System

### Architecture

```
HybridMemoryManager
    │
    ├── FileMemory (canonical storage)
    │       ├── Markdown files with YAML frontmatter
    │       ├── Git-backed auto-commit (MemoryGitOps)
    │       ├── Bi-temporal: valid_from, valid_until
    │       └── TTL enforcement + sweep
    │
    ├── HybridMemoryIndex (search)
    │       ├── SQLite FTS5 (keyword)
    │       ├── sqlite-vec (vector embeddings)
    │       └── RRF fusion (k=60)
    │
    ├── Extraction
    │       ├── MemoryExtractor (regex-based)
    │       └── LLMExtractor (LLM-based)
    │
    ├── Compaction
    │       ├── CompactionPipeline (4 graduated strategies)
    │       └── SummaryDAG (hierarchical: specific → arc → narrative)
    │
    ├── DreamCycle (consolidation)
    │       ├── scan → patterns → consolidate → trim
    │       └── Configurable interval (default 20 turns)
    │
    └── RateLimiter
            ├── 30 writes/min, 60 searches/min
            └── Token-bucket algorithm
```

### Memory Types

| Type | Description | Duration |
|------|-------------|----------|
| observation | Direct observation | Session |
| decision | Explicit decision | Permanent |
| preference | User preference | Stable |
| error | Error/failure pattern | Historical |
| entity | Named entity/term | Stable |
| procedure | Reusable workflow | Permanent |
| concept | Abstract concept | Stable |

### Data Flow

```
User Message
    │
    ├── Session.send()
    │       ├── get_memory_context(query) → relevant memories
    │       │       └── HybridMemoryManager → FTS5 + vector → RRF
    │       ├── Inject as SystemMessage
    │       ├── Agent invocation
    │       └── _run_extraction() (fire-and-forget)
    │               └── extract_and_store() → store observations
    │
    └── Auto-extraction + dream cycle run after each turn
```

---

## Persistence Layer

### Database Manager (`infrastructure/db/`)

```
infrastructure/db/
    ├── __init__.py          → get_db_manager() singleton
    ├── base.py              → SQLAlchemy Base, engine, session factory
    ├── manager.py           → DBManager (init, close, health)
    ├── models.py            → SQLAlchemy models: SessionModel, TaskModel
    ├── session_repo.py      → SessionRepository CRUD
    └── task_repo.py         → TaskRepository CRUD
```

| Model | Fields | Purpose |
|-------|--------|---------|
| `SessionModel` | id, session_id, working_dir, memory_dir, parent_memory_dir, created_at, last_active_at | Persist session metadata |
| `TaskModel` | id, task_id, description, priority, status, metadata, created_at, updated_at | Persist task state |

### Auth (`infrastructure/auth.py`)

- `AuthManager` — Fernet keystore for API key management
- API key verification via `verify_api_key()` header check

---

## NATS Event Bus

### AgentBus (`infrastructure/bus.py`, 491 lines)

```python
class AgentBus:
    """NATS JetStream wrapper for async task distribution."""

    def __init__(self, url=None):
        self.nc: Optional[NATS] = None       # Connection handle
        self.js: Optional[JetStreamContext] = None
        self._subs: list[Subscription] = []
        self._url = url or settings.nats.url
        ...

    async def connect(self) → None
    async def close(self) → None
    async def subscribe(self, subject, callback) → None
    async def subscribe_durable(self, subject, durable, callback) → None
    async def publish(self, subject, message) → None
    async def put_result(self, task_id, result) → None
    async def get_result(self, task_id) → Any | None

    # Health:
    def is_connected(self) → bool
    def is_degraded(self) → bool
    def reconnect_count(self) → int
    async def check_health(self) → dict
```

**Pattern:** `get_bus()` / `set_bus()` — global singleton.

**Subjects:**
| Subject | Direction | Payload |
|---------|-----------|---------|
| `tasks.submit` | REST → Worker | TaskSchema |
| `tasks.cancel` | REST → Worker | `{task_id}` |
| `tasks.{id}.result` | Worker → REST | Task result |

**NATS is used only for task distribution** — not for general event backbone. There is no event schema, no typed event categories, and no subscriber beyond the worker.

---

## Configuration Management

### ConfigSchema (`infrastructure/config.py`, 602 lines)

```
ConfigSchema (Pydantic BaseModel)
    │
    ├── server: ServerConfig
    │       ├── api_port (default: 8000)
    │       ├── reload
    │       ├── tls_enabled, tls_certfile, tls_keyfile
    │       └── host
    │
    ├── agent: AgentConfig
    │       ├── gemini_api_key, openrouter_api_key, openai_api_key
    │       ├── gemini_model, openrouter_model, openai_model
    │       ├── gemini_provider, openrouter_provider, openai_provider
    │       ├── max_tokens, max_turns, max_tool_calls
    │       ├── context_limit, compression
    │       ├── trust_config: TrustConfig
    │       ├── dream_cycle_interval, extraction_enabled, ttl_days
    │       └── ... (50+ parameters)
    │
    ├── budget: BudgetConfig
    │       ├── monthly_spend_limit_dollars, daily_spend_limit_dollars
    │       ├── enabled, alert_thresholds
    │       └── cost_per_token dictionary
    │
    └── nats: NATSConfig
            ├── url (default: nats://localhost:4222)
            └── reconnect settings
```

**Loading priority:** `_deep_merge(base, override)`:
1. Default config (hardcoded)
2. Project config (`config/nexusagent.yaml`)
3. User config (`~/.nexusagent/config.yaml`)
4. Environment variable overrides (`NEXUS_*`)

**Pattern:** Module-level `settings` singleton — `from nexusagent.infrastructure.config import settings`

---

## Hooks System

### HookManager (`hooks/__init__.py`)

```python
class HookEvent(StrEnum):
    SESSION_INIT = "session_init"
    POST_TOOL_USE = "post_tool_use"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_STOP = "subagent_stop"
    ERROR = "error"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    BUDGET_ALERT = "budget_alert"

class HookManager:
    """Manages hook registration and execution."""
    _hooks: dict[HookEvent, list[HookRegistration]]
    _registry: dict[str, HookRegistration]

    def register_hook(event, callback, name?) → HookRegistration
    def run_hooks(event, context) → None           # sequential, error-isolated
    def enable/disable_hook(name) → None
    def clear() → None

# Singleton pattern:
get_hook_manager() → HookManager
```

**Key characteristics:**
- Simple event → callback mapping
- Context is a plain dict (stringly typed, no validation)
- Sequential execution (hooks run one at a time per event)
- Errors logged but do not cascade
- No hook priority, no filtering, no middleware

---

## LLM Bridge

### LLMProvider (`llm/llm.py`, 288 lines)

```python
class LLMProvider:
    """Multi-provider bridge with retry and circuit-breaker."""

    def __init__(self):
        # Gemini (Interactions API)
        self.gemini_client = genai.Client(api_key=...)
        # OpenRouter (OpenAI-compatible)
        self.openai_client = AsyncOpenAI(api_key=..., base_url=...)
        # AI Proxy (for workspace configurations)
        self.ai_proxy_client = AsyncOpenAI(...)

    async def generate(self, model, prompt, tools, ...) → LLMResponse
    async def generate_with_tools(self, ...) → LLMResponse
    # Each method wrapped with @retry_with_backoff
```

**Provider routing:**
- Gemini path → `google-genai` Interactions API (native tool support)
- OpenRouter path → OpenAI-compatible API
- AI Proxy → workspace-configured proxy

---

## CLI & SDK

### CLI (`interfaces/cli.py`, 670 lines)

| Command | Description |
|---------|-------------|
| `nexus submit <task>` | Submit task to server via REST API |
| `nexus run <task>` | Run agent locally (no server) |
| `nexus session list\|resume\|fork\|...` | Session lifecycle management |
| `nexus hook list\|enable\|disable\|...` | Hook management |
| `nexus tui` | Launch Textual TUI |
| `nexus completions` | Shell completions |

**Preflight:** Version compatibility check against server.

### SDK (`server/sdk.py`)

Client SDK for interacting with the NexusAgent server:
- `submit_task(task)` → POST /tasks
- `get_task_status(task_id)` → GET /tasks/{id}/status
- `get_result(task_id)` → GET /tasks/{id}/result
- Version: `SERVER_VERSION`, `MIN_CLIENT_VERSION`

---

## Testing Infrastructure

**Test runner:** pytest  
**Test files:** 63+ test files  
**Known baseline:** ~680 passing / ~11 failing

### Test Categories

| Category | Files | Description |
|----------|-------|-------------|
| **Core** | `test_session*.py`, `test_agent_events.py`, `test_subagent.py`, `test_skills.py` | Session lifecycle, agent execution |
| **Memory** | 11 files: `test_memory_*.py` | Hybrid memory, extraction, dream, compaction, TTL, cross-agent, linking |
| **Tools** | `test_new_tools.py`, `tools/` | Tool registration, execution |
| **Server** | `test_server*.py`, `test_sdk*.py`, `test_websocket.py` | API endpoints, version negotiation |
| **NATS** | `test_bus*.py`, `test_nats*.py` | Bus connectivity, durable consumers |
| **TUI** | `test_tui_*.py` (7 files) | Widget rendering, streaming, help input |
| **Config** | `test_config*.py` | Config loading, env overrides |
| **Worker** | `test_worker_*.py` | Worker pool, workspace scoping |
| **Graph** | `test_graph*.py`, `test_graph_nodes.py` | LangGraph research workflow |
| **Security** | `test_trust.py` | Trust levels, anomaly scoring |
| **E2E** | `test_e2e_*.py` | Production-path tests (may hit real APIs) |

### Conftest (`tests/conftest.py`)
- Loads `.env` for test API keys
- Creates temporary test auth keystore
- Patches global `auth_manager` with test instance

---

## Global State Registry

This is a **complete inventory of all module-level singletons and state** — the migration target for Phase 1.

| # | Symbol | Location | Type | Initialized |
|---|--------|----------|------|-------------|
| 1 | `_tools_registered` | `core/agent.py:18` | `bool` | Lazy at first Agent creation |
| 2 | `_tools_registered_lock` | `core/agent.py:19` | `threading.RLock` | At module import |
| 3 | `_current_session` | `core/agent.py:450` | `ContextVar` | At module import |
| 4 | `_ws_memory_dir` | `core/agent.py:446` | `ContextVar` | At module import |
| 5 | `_session_manager_instance` | `core/session/manager.py:268` | `SessionManager \| None` | Lazy on first `get_session_manager()` |
| 6 | `_manager` | `hooks/__init__.py:157` | `HookManager \| None` | Lazy on first `get_hook_manager()` |
| 7 | `registry` | `tools/registry/core.py:121` | `ToolRegistry` | At module import |
| 8 | `_MCP_REGISTRY` | `tools/register_all.py:60` | `dict` | At module import |
| 9 | `_MCP_REGISTERED_NAMES` | `tools/register_all.py:61` | `set` | At module import |
| 10 | `_bus` (via `get_bus/set_bus`) | `infrastructure/bus.py:480-488` | `AgentBus \| None` | Lazy |
| 11 | `_worker` (via `get_worker/set_worker`) | `core/worker/worker.py:334-342` | `NexusWorker \| None` | Lazy |
| 12 | `_worker_pool` (via `get_worker_pool/set_worker_pool`) | `core/worker/pool.py:132-140` | `WorkerPool \| None` | Lazy |
| 13 | `_auth_manager` (via `get_auth_manager/set_auth_manager`) | `infrastructure/auth.py` | `AuthManager \| None` | Lazy |
| 14 | `_db_manager` (via `get_db_manager`) | `infrastructure/db/manager.py` | `DBManager \| None` | Lazy |
| 15 | `_PID_FILE` lock | `server/server.py:20` | File descriptor | At `run()` |
| 16 | `_VERSION_START_TIME` | `server/routes.py:22` | `float` | At module import |
| 17 | `settings` | `infrastructure/config.py` | `ConfigSchema` | At first `import` |
| 18 | `_nats_breaker`, `_agent_breaker` | `core/worker/handler.py:22-29` | `CircuitBreaker` | At module import |
| 19 | `task_repo` | `core/worker/handler.py:17` | `TaskRepository` | At module import |
| 20 | `_memory_rate_limiter` | `tools/register_all.py` | `MemoryRateLimiter` | At tool registration import |

---

## Known Limitations

### Architecture

1. **No unified runtime** — Three independent entry points (server, CLI, TUI) with no shared lifecycle
2. **No session identity** — Sessions exist only via `_current_session` ContextVar, not as first-class runtime entities
3. **No worker identity** — `NexusWorker` is a singleton with no ID, no traceable lifecycle
4. **Global state epidemic** — 20+ module-level singletons with implicit initialization order
5. **Tight coupling** — `Agent` class couples deepagents, LangChain, tool registry, policy, and config
6. **Hidden global state** — `_tools_registered` guard is a module bool, not owned by any context
7. **No execution boundaries** — Agents get direct tool access (filtered only by policy level)
8. **ContextVar confusion** — `_current_session` and `_ws_memory_dir` are ContextVars that agents import from `core.agent` — crossing module boundaries and leaking abstraction
9. **No lifecycle model** — Components have no explicit states (CREATED → RUNNING → TERMINATED). They exist or they don't.
10. **No dependency injection** — Dependencies are imported at module level, passed down via singletons

### Operational

11. **Worker runs in-process** — `NexusWorker` is an asyncio task inside the server process, not isolated
12. **No crash isolation** — Worker crash takes down the server
13. **NATS is task-only** — No general event backbone, no typed event categories
14. **Memory system is per-session** — No global memory namespace (cross-session memory via parent dir hack)
15. **Database is local SQLite** — Single-file, no horizontal scaling
16. **No health monitoring** — Worker health is self-reported (NATS ping)
17. **No worker recovery** — Worker failure = lost tasks (NATS durable consumer survives, but in-flight tasks are lost)
18. **Tool policy is string-based** — `ROLE_MANIFESTS` is a dict of tool lists, not a capability system

### Documentation

19. **STATE.md is stale** — Module-by-module inventory out of sync
20. **No runtime architecture doc** — 12-phase migration docs exist but no "how it works today" doc (this document fills that gap)

---

## Component Dependency Graph

```
CLI (interfaces/cli.py)
    ├── core/worker/handler.py → core/agent.py → deepagents
    ├── core/worker/pool.py
    ├── llm/models.py → TaskContract, TaskSchema
    └── infrastructure/config.py → settings

TUI (interfaces/tui/app.py)
    ├── server/server.py → FastAPI WebSocket
    └── core/session/session.py → Session

Server (server/server.py)
    ├── server/routes.py → server/sdk.py, infrastructure/bus.py, infrastructure/db/
    ├── server/websocket.py → core/session/session.py, core/agent.py
    ├── core/worker/worker.py → core/worker/handler.py, infrastructure/bus.py
    ├── hooks/__init__.py → HookManager singleton
    └── infrastructure/config.py

Memory System (memory/)
    ├── memory/hybrid_memory.py → memory/memory_files.py, memory/index/
    ├── memory/extraction.py, memory/llm_extraction.py
    ├── memory/compaction.py, memory/dag.py
    ├── memory/dream.py
    └── memory/git_ops.py → git

Tool System (tools/)
    ├── tools/registry/ → ToolRegistry, ToolInfo, policy, search
    ├── tools/register_all.py → tools/tool_specs.py, tools/registry/
    └── tools/*.py → Individual tool implementations
```

---

**Document version:** 1.1  
**Last updated:** 2026-07-19 — Added runtime/ section reflecting Phase 1 delivery
**Next review:** After Phase 2 (Memory System Polish)
