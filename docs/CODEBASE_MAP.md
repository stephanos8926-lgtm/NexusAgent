# NexusAgent Codebase Map

> Generated: 2026-07-18
> Total source files: 107 (tests: 30)
> Total lines: ~7,200 (src), ~2,100 (tests)
> Last refactoring: Phase 5 — registry.py extracted into registry/ subpackage
> Structure pattern: Domain-based subpackages with compat shims

---

## Project Root

```
NexusAgent/
├── .hermes/               # Hermes Agent config
├── .env                   # API keys (GEMINI_API_KEY, OPENROUTER_API_KEY)
├── config/NEXUS.md        # Base system prompt
├── docs/                   # MkDocs documentation + research reports
│   ├── CODEBASE_MAP.md    # This file
│   ├── SEMANTIC_INDEX.md  # TUI semantic architecture index (917L)
│   └── research/          # Research reports
├── deployment/            # Deployment scripts
├── scripts/               # CLI tools (worktree-worker.py)
├── src/nexusagent/        # Main source package
└── tests/                 # 30 test files, 453 pass / 20 fail baseline
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  CLI (click)                         │
│            nexus-client / nexus run                  │
├─────────────────────────────────────────────────────┤
│                Web UI (Gradio)                       │
├─────────────────────────────────────────────────────┤
│               FastAPI Server                         │
│        REST endpoints + WebSocket /ws               │
├──────────────┬──────────────┬───────────────────────┤
│   TUI        │   SDK        │   Worker Pool         │
│  (Textual)   │  (NexusSDK)  │  (NexusWorker)        │
├──────────────┴──────────────┴───────────────────────┤
│              Agent (deepagents wrapper)              │
│    Role-based tool access + policy enforcement       │
├──────────────────────────────────────────────────────┤
│              Tools Registry (35+ tools)              │
│  fs, git, shell, research, code_search, memory,      │
│  spawn_subagent, patch, test_runner, code_review    │
├──────────────────────────────────────────────────────┤
│   LLM Provider (Gemini + OpenRouter + Extensible)   │
│   NATS Bus · SQLite DB · Hybrid Memory              │
│   Auth (Fernet) · Session Manager · Compaction       │
└──────────────────────────────────────────────────────┘
```

---

## Source Package (`src/nexusagent/`)

### Directory Structure

```
nexusagent/
├── skills.py                    # Tool skill dispatch (127L)
├── task_reaper.py               # Stale task cleanup (59L)
│
├── core/                        # Agent core (session, agent, orchestration, graph)
│   ├── session.py (677L)        # Session + SessionManager ← MONOLITH
│   ├── agent.py (134L)          # Agent wrapper (role-based, policy)
│   ├── worker.py (304L)         # NexusWorker + WorkerPool ← LARGE
│   ├── orchestration.py (193L)  # DeepResearchOrchestrator
│   ├── graph.py (250L)          # LangGraph research graph
│   └── subagent.py (161L)       # SubAgentHandle tracking
│
├── tools/                       # Tool implementations
│   ├── registry.py (623L)       # ToolInfo + @register + policy ← MONOLITH
│   ├── register_all.py (728L)   # Registration calls ← MONOLITH
│   ├── fs.py (343L)             # Filesystem tools
│   ├── git.py (169L)            # Git tools
│   ├── shell.py (167L)          # Shell execution tools
│   ├── code_review.py (367L)    # Code review tools
│   ├── code_search.py (158L)    # Code search (ast-grep)
│   ├── research.py (204L)       # Web research
│   ├── test_runner.py (216L)    # Test execution
│   ├── patch.py (17L)           # File patching
│   └── write_todos.py (118L)    # Todo write tool
│
├── memory/                      # Hybrid memory system
│   ├── memory.py (440L)        # HybridMemoryManager ← MONOLITH
│   ├── memory_index.py (717L)   # FTS5 + sqlite-vec index ← MONOLITH
│   ├── memory_files.py (264L)   # File-based canonical memory
│   └── compaction.py (233L)     # Context compaction pipeline
│
├── widgets/                     # UI widgets
│   ├── messages/                  # Messages subpackage ✅ EXTRACTED Phase 4
│   │   ├── user.py (42L)          # UserMessage
│   │   ├── assistant.py (128L)      # AssistantMessage (streaming, markdown)
│   │   ├── tool.py (171L)         # ToolCallMessage (collapsible, status)
│   │   ├── app.py (33L)           # AppMessage (system messages)
│   │   ├── error.py (33L)         # ErrorMessage
│   │   └── welcome.py (52L)       # WelcomeBanner
│   ├── chat_input.py (215L)     # ChatInput widget
│   ├── status.py (367L)         # StatusBar + helpers ← POSSIBLY DEAD CODE
│   └── theme/                   # Theme subpackage ✅ EXTRACTED Phase 2
│       ├── colors.py (273L)     # 7 themes, ThemeColors
│       └── registry.py (68L)   # CSS vars, register_themes
│
├── interfaces/                  # External interfaces
│   ├── tui.py (1433L)           # Textual TUI — NexusApp ← BIGGEST MONOLITH
│   ├── cli.py (248L)            # Click CLI
│   └── web_ui.py (90L)          # Gradio web UI
│
├── server/                      # Server layer
│   ├── server.py (354L)         # FastAPI + WebSocket ← LARGE
│   └── sdk.py (210L)          # NexusSDK
│
├── infrastructure/              # Infrastructure
│   ├── db/                        # Database subpackage ✅ EXTRACTED Phase 3
│   │   ├── base.py (25L)          # DeclarativeBase
│   │   ├── models.py (73L)        # TaskModel, ResultModel, SessionModel, MessageModel
│   │   ├── manager.py (134L)      # DatabaseManager (engine + session factory)
│   │   ├── task_repo.py (128L)    # TaskRepository (task/result CRUD)
│   │   └── session_repo.py (171L) # SessionRepository (session/message CRUD)
│   ├── config.py (184L)         # Settings (3-tier loading)
│   ├── prompt_loader.py (240L)  # NEXUS.md + @file injection
│   ├── bus.py (172L)            # NATS event bus
│   ├── auth.py (129L)           # Fernet keystore
│   ├── telemetry.py (160L)      # Telemetry
│   ├── api_auth.py (53L)        # FastAPI security
│   └── utils/                   # Utils subpackage ✅ EXTRACTED Phase 1
│       ├── retry.py (231L)      # retry_with_backoff, retry_on_false
│       └── circuit.py (140L)    # Circuit breaker
│
├── llm/                         # LLM abstraction
│   ├── llm.py (129L)            # LLMProvider (Gemini + OpenRouter)
│   └── models.py (175L)         # LLM request/response models
│
└── hooks/                       # Pre/post execution hooks
    ├── __init__.py (176L)       # Hook registry
    └── builtins.py (224L)       # Built-in hook functions
```

---

## Coupling Analysis

### Fan-In (imported by N files) — Higher = Riskier to Refactor

| Module | Fan-In | Notes |
|--------|--------|-------|
| `infrastructure` | 14 | Root package — imported by everyone |
| `llm` | 6 | Core dependency |
| `core` | 3 | Core domain |
| `widgets` | 3 | UI layer |
| `tools` | 2 | Tool system |
| `server` | 2 | Server layer |

### Extraction Candidates (large + low fan-in = safe)

| File | Lines | Fan-In | Fan-Out | Risk | Contains |
|------|-------|--------|---------|------|----------|
| `interfaces/tui` | 1433 | 0 | 1 | **LOW** | NexusApp, Modals, SpinnerLabel, formatters, commands |
| `tools/register_all` | 728 | 0 | 1 | **LOW** | Tool registration calls |
| `memory/memory_index` | 717 | 0 | 1 | **LOW** | FTS5+sqlite-vec index |
| `tools/registry` | 623 | 0 | 0 | **LOW** | ToolInfo, @register, policy |
| `widgets/messages` | 472 | 0 | 0 | **LOW** | 6 message widget classes |
| `memory/memory` | 440 | 0 | 1 | **LOW** | HybridMemoryManager |
| `infrastructure/db` | 416 | 0 | 1 | **LOW** | Models + repositories |
| `tools/code_review` | 367 | 0 | 0 | **LOW** | Code review tools |
| `widgets/status` | 367 | 0 | 0 | **LOW** | StatusBar (verify dead code) |
| `tools/fs` | 343 | 0 | 0 | **LOW** | Filesystem tools |
| `memory/memory_files` | 264 | 0 | 0 | **LOW** | FileMemory |
| `core/graph` | 250 | 0 | 0 | **LOW** | LangGraph state machine |
| `infrastructure/prompt_loader` | 240 | 0 | 0 | **LOW** | Prompt loading |
| `memory/compaction` | 233 | 0 | 0 | **LOW** | Compaction pipeline |
| `core/worker` | 304 | 0 | 3 | **MED** | NexusWorker + WorkerPool |
| `core/session` | 677 | 0 | 3 | **MED** | Session + SessionManager |
| `server/server` | 354 | 0 | 3 | **MED** | FastAPI + WebSocket |
| `tools/research` | 204 | 0 | 0 | **LOW** | Research tools |
| `tools/test_runner` | 216 | 0 | 0 | **LOW** | Test runner |
| `widgets/chat_input` | 215 | 0 | 0 | **LOW** | ChatInput widget |
| `server/sdk` | 210 | 0 | 2 | **LOW** | NexusSDK |

### Higher Risk (fan-out > 3 — many modules depend on these)

| File | Lines | Fan-In | Fan-Out | Risk |
|------|-------|--------|---------|------|
| core/session | 677 | 0 | 3 | Session is core to TUI + Server + Worker |
| core/worker | 304 | 0 | 3 | Worker is used by multiple consumers |
| server/server | 354 | 0 | 3 | Server is tightly coupled |
| core/agent | 134 | 0 | 2 | Agent is used by Worker + Orchestration |

---

## Completed Refactoring

### Phase 1: `infrastructure/utils.py` → `infrastructure/utils/` ✅
- Extracted: `retry.py` (231L), `circuit.py` (140L)
- Old file: Compat shim
- Commit: `f260eee`

### Phase 2: `widgets/theme.py` → `widgets/theme/` ✅
- Extracted: `colors.py` (273L), `registry.py` (68L)
- Old file: Compat shim
- Commit: `bfe2723`

### Phase 3: `infrastructure/db.py` → `infrastructure/db/` ✅
- Extracted: `base.py` (25L), `models.py` (73L), `manager.py` (134L), `task_repo.py` (128L), `session_repo.py` (171L)
- Old file: Compat shim
- Commit: `83aef0f`
- Fixes: `reinit()` now recreates engine + session (was silently using old engine)

### Phase 4: `widgets/messages.py` → `widgets/messages/` ✅
- Extracted: `user.py` (42L), `assistant.py` (128L), `tool.py` (171L), `app.py` (33L), `error.py` (33L), `welcome.py` (52L)
- Old file: Compat shim
- Commit: `10e76dc`
- Cleaned: Removed 3 dead regex constants, dead Vertical import, redundant datetime import

---

## Refactoring Refactoring Pattern (Established)

For each extraction:
1. Read target file completely (all lines)
2. Create `subpackage/` directory with `__init__.py`
3. Split into focused modules by concern (max 500L per module)
4. Old file becomes compat shim: `from nexusagent.X import *`
5. No behavior changes — all existing imports preserved
6. Test gate: 453+ pass / 20 fail baseline unchanged
7. Commit: `refactor: extract X into Y/ subpackage`
8. Update CODEBASE_MAP.md
