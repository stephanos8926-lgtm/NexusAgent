# AGENTS.md — NexusAgent Project Knowledge Base

> Last updated: 2026-07-25
> Maintained by: OWL (Lucien)
> Purpose: Critical project knowledge for any agent working on this codebase

---

## Project Overview

NexusAgent is a production-grade AI coding agent platform. It combines an LLM-powered agent (via `deepagents` / LangGraph) with a NATS-backed task orchestration system, a Textual TUI, a FastAPI WebSocket server, and a hybrid file+vector memory system.

**Language:** Python 3.13+ | **Package:** `nexusagent` (src layout) | **Codebase:** 150 Python files, 27,201 LOC | **Tests:** pytest (182 collected, 173 core passing baseline, 1,000 total tests across 88 files)

---

## Critical Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| **Codebase Map** | `docs/CODEBASE_MAP.md` | Module structure, fan-in/fan-out, extraction candidates |
| **Semantic Index** | `docs/SEMANTIC_INDEX.md` | Data flows, state management, extension points, tech debt |
| **Refactoring Plan** | `docs/REFACTORING_PLAN.md` | 14-item prioritized refactoring roadmap |
| **State** | `docs/STATE.md` | Module-by-module inventory (⚠️ partially outdated) |
| **Compliance** | `docs/DOC_COMPLIANCE.md` | Documentation audit and gap analysis |
| **Code Review** | `docs/CODE_REVIEW_COMPREHENSIVE.md` | Comprehensive multi-audit (45+ issues, prioritized) |
| **Assessment** | `docs/assessment/2026-07-18-independent-codebase-assessment.md` | Independent architecture assessment |
| **Version** | `src/nexusagent/version.py` | Single source of truth (importlib.metadata) |
| **ADRs** | `docs/adrs/` | Architecture decision records (0001-0008) |
| **Specs** | `docs/specs/` | Implementation specs (SPEC-001 to SPEC-006: memory system) |
| **Plans** | `docs/plans/` | Implementation plans (memory overhaul, security, TUI, version) |
| **Config** | `config/nexusagent.yaml` | Runtime configuration |

---

## Repository Structure

```
NexusAgent/
├── src/nexusagent/          # Main source (src layout)
│   ├── core/                # Agent core
│   │   ├── session/         # Session + SessionManager (extracted)
│   │   ├── worker/          # NexusWorker + WorkerPool (extracted)
│   │   ├── agent.py         # Agent wrapper
│   │   ├── graph.py         # LangGraph research graph
│   │   └── subagent.py      # SubAgentHandle tracking
│   ├── tools/               # 25+ tools + registry subpackage
│   │   └── registry/        # types, core, policy, search (extracted Phase 5)
│   ├── memory/              # Hybrid memory system
│   │   ├── __init__.py
│   │   ├── memory.py        # Compat shim → submodules
│   │   ├── memory_item.py   # MemoryItem model + _hash_embed
│   │   ├── hybrid_memory.py # HybridMemoryManager (file + index)
│   │   ├── memory_files.py  # FileMemory (canonical, git-backed)
│   │   ├── memory_index.py  # Compat shim → index/ subpackage
│   │   ├── index/           # embeddings.py, index.py (extracted Phase 6)
│   │   ├── compaction.py    # CompactionPipeline (graduated + DAG)
│   │   ├── dag.py           # SummaryDAG (hierarchical compression)
│   │   ├── dream.py         # DreamCycle (4-phase consolidation)
│   │   ├── extraction.py    # MemoryExtractor (regex-based auto-extraction)
│   │   ├── git_ops.py       # MemoryGitOps (auto-commit after writes)
│   │   └── rate_limiter.py  # MemoryRateLimiter (token-bucket)
│   ├── widgets/             # TUI widgets
│   │   ├── messages/        # 6 message widget classes (extracted Phase 4)
│   │   ├── theme/           # colors.py, registry.py (extracted Phase 2)
│   │   ├── chat_input.py    # ChatInput widget
│   │   └── status.py        # StatusBar, ModelLabel
│   ├── interfaces/          # External interfaces
│   │   ├── tui.py           # NexusApp (787L, widget-based arch, version preflight)
│   │   ├── tui_widgets.py   # SpinnerLabel, modals, SIGWINCH (extracted)
│   │   ├── tui_formatters.py # render_markdown, all formatters (extracted)
│   │   ├── cli.py           # Click CLI (--check-server, --skip-version-check)
│   │   └── web_ui.py        # Gradio web UI
│   ├── infrastructure/      # Config, DB, bus, auth, utilities
│   │   ├── config.py        # ConfigSchema (Pydantic settings)
│   │   ├── db/              # SQLAlchemy async DB (extracted Phase 3)
│   │   ├── utils/           # retry.py, circuit.py (extracted Phase 1)
│   │   ├── bus.py           # NATS JetStream
│   │   ├── auth.py          # Fernet keystore
│   │   └── prompt_loader.py # NEXUS.md loader
│   ├── server/              # FastAPI + WebSocket + SDK + Version
│   │   ├── __init__.py
│   │   ├── __main__.py       # Entry point for `python3 -m nexusagent.server`
│   │   ├── server.py        # App factory (create_app) + lifespan + run()
│   │   ├── routes.py        # REST endpoints (register_routes pattern)
│   │   ├── websocket.py     # session_websocket handler
│   │   ├── sdk.py           # NexusSDK (SERVER_VERSION, MIN_CLIENT_VERSION)
│   │   └── version.py       # Single source of truth via importlib.metadata
│   ├── llm/                 # Multi-provider LLM bridge
│   └── hooks/               # Pre/post execution hooks
├── tests/                   # 38 test files
├── docs/                    # Documentation (see reference docs above)
├── scripts/                 # CLI tools (worktree-worker.py)
├── config/
│   └── NEXUS.md             # Base system prompt
└── pyproject.toml           # Project metadata + dependencies
```

---

## Runtime Foundation Layer

The `src/nexusagent/runtime/` package is the **foundation layer** for all NexusAgent component lifecycle:

| Module | Purpose |
|--------|---------|
| `lifecycle.py` | Lifecycle state machine: `CREATED → INITIALIZING → RUNNING → STOPPING → TERMINATED` |
| `context.py` | `RuntimeContext` — dependency injection container with `current_context()` / `set_current_context()` |
| `runtime.py` | Runtime kernel — `initialize()`/`shutdown()` orchestration |
| `session.py` | `RuntimeSessionManager` + `ManagedSession` — session lifecycle managed by runtime |
| `worker.py` | `RuntimeWorkerManager` + `ManagedWorker` — worker lifecycle managed by runtime |
| `tools.py` | `ToolManager` — tool registration and lifecycle |
| `__init__.py` | Exports all above with lazy submodule loading |

**Key pattern**: The runtime manages a **context stack** — when a new component starts, its context is pushed (`set_current_context`). Components access their context via `current_context()`. This replaces the prior singleton/module-level state pattern.

**Fan-in**: `infrastructure` (76 references) and `runtime` (19 references) are the two most-imported subsystems — they form the backbone everything else depends on.

---

## Infrastructure Topology — 3 Incus VMs

NexusAgent runs across 3 Incus VMs over Tailscale mesh:

| VM | Tailscale IP | SSH Host | Role | Services |
|----|-------------|----------|------|----------|
| `infra` | 100.122.246.112 | `ssh infra` | Infrastructure | NATS JetStream (port 4222), PostgreSQL 16, Caddy, Honcho API |
| `enterprise` | 100.81.49.91 | `ssh enterprise` | Enterprise apps | — |
| `dev` | 100.109.15.31 | `ssh dev` | Development | Phase worktrees, test execution, dev builds |

- **NATS runs on `infra` VM** (NOT `dev` — do not expect it there)
- **Dev VM worktrees** at `/home/sysop/Workspaces/NexusAgent/.hermes/worktrees/<name>/` with own venv
- **Workstation RAM ceiling: 4GB** (~300MB free during heavy work) — offload to dev VM or Jules
- **Jules** runs on Google Cloud sandbox (Pro Gemini, 15 PRs/day limit)

---

## Codebase Scale & Coupling

### Module Fan-In (most imported-from subsystems)

| Module | Import References | Role |
|--------|-------------------|------|
| `infrastructure` | 76 | Config, DB, bus, auth — spine of the codebase |
| `tools` | 55 | Tool registration, MCP discovery, policy |
| `core` | 51 | Session, worker, agent, task, events |
| `memory` | 40 | FileMemory + HybridMemoryIndex + DreamCycle |
| `runtime` | 19 | Lifecycle + DI container (growing) |
| `widgets` | 17 | TUI widgets |
| `interfaces` | 14 | CLI, TUI, WebUI |
| `llm` | 13 | LLM provider bridge, models |
| `server` | 12 | FastAPI + WebSocket + SDK |

### Biggest Files (Extraction Candidates)

| File | LOC | Why Large |
|------|-----|-----------|
| `tools/register_all.py` | 1,308 | Tool registration + MCP discovery + wrapping — should be split |
| `memory/index/index.py` | 836 | Single file with sync/async search, embeddings, RRF fusion |
| `memory/dream.py` | 794 | 4-phase dream cycle — consolidation engine |
| `core/session/session.py` | 713 | Session lifecycle + streaming + extraction + compact |
| `memory/memory_files.py` | 680 | FileMemory + MemoryGitOps + TTL sweep |
| `interfaces/cli.py` | 670 | Click CLI — 15+ commands |
| `infrastructure/utils/budget.py` | 541 | Budget guard + pricing tables + alerting |

### Async Architecture

- **273 `async def` functions** across the codebase — heavily async throughout
- **441 async tests** out of 1,000 total
- **473 mock usages** in tests — strong isolation culture
- **Edge case**: `asyncio.run()` inside async methods (found in session.py) creates silent failures — never call `asyncio.run()` inside `async def`
- **Edge case**: `ContextVar` is invisible across `create_task()` boundaries — LangGraph runs tools in separate tasks

---

## Jules Environment Setup

For Jules sessions working on this repo, configure in Jules UI (repo sidebar → Configuration → Initial Setup):

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
```

Key reference files for Jules onboarding: `docs/.jules/MEMORIES.md` (10 high-value permanent memories), `docs/.jules/SESSION_START.md` (mandatory read-first), `docs/.jules/FILE_CHANGE_VERIFICATION.md` (empty commit prevention), `docs/.jules/BUDGET_SAFETY.md` (budget guard + circuit breaker rules). Read these before starting.

---

## Memory System Architecture

The memory system is a hybrid file+vector architecture with 4 layers:

### Layer 1: FileMemory (Canonical Storage)
- `memory_files.py` — File-based canonical source of truth
- Markdown files in `bank/` directory with YAML frontmatter (type, description, confidence, entities, ttl_hours, valid_from, valid_until)
- Git-backed: auto-commits after every write via `MemoryGitOps`
- Bi-temporal fields: `valid_from`/`valid_until` for time-based queries
- TTL enforcement: check-on-read (expired entries excluded from index) + `sweep_expired()` for physical removal

### Layer 2: HybridMemoryIndex (Search)
- `memory/index/index.py` — SQLite-based hybrid search (FTS5 + sqlite-vec)
- `memory/index/embeddings.py` — Embedding provider (Gemini API → local sentence-transformers → SHA256 hash fallback)
- Reciprocal Rank Fusion (RRF, k=60) for vector + keyword fusion
- Chunk size: 256 tokens with 15% overlap

### Layer 3: HybridMemoryManager (Orchestration)
- `hybrid_memory.py` — Top-level interface combining FileMemory + HybridMemoryIndex
- `remember()` — Write + index
- `get_memory_context()` — Search + format for prompt injection
- `flush()` — Pre-compaction save
- `close()` — Resource cleanup

### Layer 4: Background Processes
- `extraction.py` — `MemoryExtractor`: Regex-based auto-extraction (decisions, preferences, errors, entities)
- `compaction.py` — `CompactionPipeline`: 4 graduated strategies + DAG-based hierarchical compression
- `dag.py` — `SummaryDAG`: Depth-0 (specifics) → Depth-1 (arc) → Depth-2 (narrative)
- `dream.py` — `DreamCycle`: 4-phase consolidation (scan → patterns → consolidate → trim)
- `rate_limiter.py` — `MemoryRateLimiter`: Token-bucket rate limiting (30 writes/min, 60 searches/min)

### Session Integration
- Session creates `HybridMemoryManager` on init, calls `close()` on session end
- `send()` calls `get_memory_context()` to inject relevant memories as SystemMessage
- `send()` schedules `_run_extraction()` as fire-and-forget after each turn
- Dream cycle auto-triggers every N turns (configurable, default 20)
- Pre-compaction flush calls `hybrid_memory.flush()` to preserve context

### Data Flow
```
User Message → Memory Recall → Context Assembly → Agent Invocation → Memory Store
     ↓              ↓                                                    ↓
  get_memory_context()                                        _run_extraction()
     ↓                                                              ↓
  SystemMessage injection                              observation-type memory
```

---

## Refactoring History

### Phases 1-7 (2026-07-18) — Initial structural refactoring
See CODEBASE_MAP.md for details. Established pattern: extract to subpackage → old file becomes compat shim → test → commit.

### Phases 8-10 (2026-07-19) — Streaming + TUI + Tools
| Phase | What | Result |
|-------|------|--------|
| 8 | Session streaming | `invoke()` → `astream()`, real token-by-token streaming, 4 new tests |
| 9 | TUI split (810L) | `tui/` subpackage: app, websocket, streaming, input, formatters |
| 10 | Tool registration (997L) | `tool_specs.py` (30 static tool tuples) + `register_all.py` (494L) |

### Phases 11-13 (2026-07-19) — Quick wins
| Phase | What | Result |
|-------|------|--------|
| 11 | Code review (390L) | `code_review/` subpackage: models, checks/security, bugs, style, performance, ast |
| 12 | Editor extraction | `editor.py` (edit_file), `fs_base.py` (shared utilities), fs.py reduced to 188L |
| 13 | Template includes | `template_includes.py` (@-chain logic), prompt_loader.py reduced to 139L |

### Phases 14-15 (2026-07-19) — Core modules
| Phase | What | Result |
|-------|------|--------|
| 14 | Worker split (539L) | `worker/` subpackage: worker (NexusWorker), pool (WorkerPool), handler (agent execution) |
| 15 | Session split (764L) | `session/` subpackage: session (Session), manager (SessionManager), helpers (context building) |

### Phases 16-17 (2026-07-19) — Server + Memory
| Phase | What | Result |
|-------|------|--------|
| 16 | Server split (508L) | `server/` subpackage: server.py (app factory), routes.py (REST), websocket.py (WS handler), __main__.py |
|| 17 | Memory split (474L) | `memory/` subpackage: memory_item.py, hybrid_memory.py, memory_files.py, memory_index.py + index/ subpackage; memory.py = compat shim. NOTE: memory_bank.py and memory_manager.py were later removed as dead code (Phases 25). |

### Phases 18-24 (2026-07-22) — Memory System Overhaul (Recovered from prior session)
| Phase | What | Result |
|-------|------|--------|
| 18 | Foundation fixes | `config.py` db_path fix, `memory_dir` DB column + migration, `find_sessions_by_working_dir` query, compaction/git/extraction config fields, `HybridMemoryManager.close()` |
| 19 | Cross-session memory discovery | `SessionManager._discover_cross_session_memories()` — parallel search of previous sessions by `working_dir`, 5-min cache TTL |
| 20 | Regex-based auto extraction | `MemoryExtractor.extract()` — regex patterns for code paths, errors, decisions, todos; schedules on every response |
| 21 | Git-backed memory | `FileMemory.write_entry()` auto-commits via `MemoryGitOps`; `FileMemory.initialize()` calls `git init` |
| 22 | Two-tier compaction | `CompactionPipeline` with 4 graduated strategies + `compress_with_dag()` using `SummaryDAG` |
| 23 | Summary DAG compression | `memory/dag.py` — `SummaryDAG` class with node/edge management, DAG-based hierarchical compression |
| 24 | Dream cycle consolidation | `memory/dream.py` — `DreamCycle` engine with 4 phases (orient, gather, consolidate, prune), file locking, provenance |

---

## Known Quirks & Gotchas

### Import System
- **Src layout**: Package is in `src/nexusagent/`. Always use `PYTHONPATH=src` or run from repo root.
- **Compat shims**: Old files still exist as re-export shims: utils.py, theme.py, db.py, messages.py, registry.py, memory_index.py, tui.py, tui_widgets.py, tui_formatters.py, code_review.py, fs.py, prompt_loader.py, worker.py, session.py, server.py, memory.py. New code should import from subpackages directly.
- **Circular imports**: `tools/registry/core.py` imports `policy.py` with delayed import to avoid circular dependency. Don't restructure without understanding the import order.

### Config
- **Three-tier loading**: `config/nexusagent.yaml` → `NEXUS_*` env vars → Pydantic defaults
- **Env var format**: `NEXUS_AGENT__DEFAULT_MODEL=...` (double underscore = nested key)
- **`yolo` field**: Added 2026-07-18. `settings.agent.yolo` controls auto-approve default in TUI.

### Version
- **Single source of truth**: `version.py` reads from `importlib.metadata` (pyproject.toml at install time)
- **Centralized**: `VERSION` and `MIN_CLIENT_VERSION` constants in `version.py`
- **Server endpoint**: `GET /version` returns `{"version": "...", "min_client": "..."}`
- **SDK**: `NexusSDK.health_check()` returns `SERVER_VERSION` and `MIN_CLIENT_VERSION`
- **CLI**: Use `--check-server` to verify compatibility; `--skip-version-check` to bypass
- **TUI**: Performs async version preflight via httpx before WebSocket connect (non-blocking on mismatch)
- **Version changes**: Always update `pyproject.toml` first, run version-sync test
- **Dev mode strict checking**: Set `NEXUS_STRICT_VERSION=1` to FAIL on version mismatch
  - Default: Shows warning notification but continues (production-safe)
  - Strict mode: Aborts TUI with clear error message and server restart instructions
  - Added to `~/.zshrc` for development: `export NEXUS_STRICT_VERSION=1`
  - Prevents running with stale server code (common dev pitfall)

### TUI
- **Textual framework**: Uses Textual (not Rich directly). Widgets extend `Static`, `Horizontal`, etc.
- **CSS variables**: Theme colors use `$surface`, `$text`, `$primary` etc. defined by `register_themes()`.
- **NO_COLOR**: Respects https://no-color.org. Check `NO_COLOR` env var before adding color.
- **SIGWINCH**: Resize handler installed in `on_mount()`. Uses debounce (0.2s) to avoid excessive re-renders.
- **Streaming**: `_write_response_chunk()` accumulates tokens in `_streaming_response` string. `_finalize_response()` writes to log and clears widget.
- **⚠️ Known broken**: Streaming is fake (accumulates then dumps as single event), search providers not wired, word wrapping broken, tool calls show raw JSON, welcome message may not render. See `docs/CODE_REVIEW_COMPREHENSIVE.md` for full TUI audit.

### Memory System
- **Single active system**: `HybridMemoryManager` (file + SQLite index). Session and tools use this exclusively.
- **Legacy code removed**: Old `Memory` bank and `MemoryManager` classes were deleted (dead code, never wired to tools).
- **Embedding fallback chain**: Gemini API → local sentence-transformers → SHA256 hash (deterministic, low quality)
- **sqlite-vec**: Virtual table for vector search. Requires `sqlite_vec.load(conn)` at startup.
- **3-tier architecture**: Core (session-scoped, in-memory) + Recall (file-backed, `FileMemory`) + Archival (consolidated, `DreamCycle`)
- **Cross-session discovery**: `SessionManager.get_or_create()` calls `_discover_cross_session_memories()` — searches all previous sessions with same `working_dir` via `SessionRepository.find_sessions_by_working_dir()`, merges memories with session_id prefix
- **Auto-extraction**: `MemoryExtractor.extract()` runs regex patterns on every assistant response (code paths, file:line refs, errors, decisions, todos). Configurable via `memory_model` (empty = use current model)
- **Git-backed memory**: `FileMemory.initialize()` calls `git init` if `memory_git_enabled=True`. `FileMemory.write_entry()` auto-commits via `MemoryGitOps` if `memory_git_auto_commit=True`
- **Two-tier compaction**: `CompactionPipeline.compact()` applies graduated strategies (summarization, sliding window, emergency truncation). Optional Level 5: `compress_with_dag()` builds `SummaryDAG` for hierarchical context compression
- **Dream cycle**: `DreamCycle.run()` executes 4 phases: orient (scan), gather (collect), consolidate (cluster + synthesize), prune (expire low-quality). Uses file locking (`fcntl.flock`) to prevent corruption during concurrent writes
- **Provenance**: `MemoryItem` has `extraction_method` (regex|llm|manual), `source_message_id`, `extraction_confidence` (0.0-1.0)

### Testing
- **Baseline**: 1,000 tests (182 collected core, 173 passing baseline). Zero regressions allowed.
- **Core tests**: `PYTHONPATH=src python3 -m pytest tests/core/ -q --tb=no --asyncio-mode=auto`
- **Full suite**: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short` — takes ~100s, use `timeout 120`
- **Pre-existing failures**: `test_orchestration.py` (module path issues), `test_tui_responsive.py` (wrong mock paths), `test_e2e_production.py` (WebSocket dependency)
- **New tests**: `test_version.py` (8), `test_server_version.py` (5), `test_memory_extraction.py` (8) — version system + memory extraction coverage
- **Memory system tests**: All new memory tests pass (extraction, git ops, cross-session, compaction, dream cycle)

---

## Configuration System Philosophy

**Purpose**: Make NexusAgent easy to configure, easy to understand what's configured, and how it's configured. Clean separation of interests.

### Configuration Loading Order (later overrides earlier)

1. **Pydantic Model Defaults** — Baseline minimums to get the application RUNNING. Conservative defaults suitable for NEW USERS (e.g., daily_budget_usd=10.0 ≈ 1M tokens on gemini-2.5-flash). These are NOT production recommendations — they're safety floors.

2. **Project Config** (`config/nexusagent.yaml`) — **Deployment defaults ONLY**. Committed to repo. Used as TEMPLATE to build user's home config on first run. This is what gets deployed. DO NOT put user preferences here.

3. **User Config** (`~/.nexusagent/config/nexusagent.yaml`) — User overrides. NOT committed. This is where users customize behavior for their environment.

4. **Environment Variables** (`NEXUS_*`) — Highest priority. **Best used ONLY for**: secrets (API keys, encryption keys), machine-specific paths, CI/CD injected values. AVOID for user preferences — easily forgotten, hard to audit, cause "works on my machine" bugs.

### Configuration File Structure

**Single unified config file** (`config/nexusagent.yaml` / `~/.nexusagent/config/nexusagent.yaml`) with **logical sections** (NOT separate files):

| Section | Domain | Examples |
|---------|--------|----------|
| `server` | Server runtime | nats_url, db_path, api_port, tls, worker_threads |
| `client` | TUI/CLI/Web-UI | tui_theme, timeout, retry_limit, responsive_enabled |
| `agent` | LLM agent behavior | default_model, primary_provider, enabled_tools, compaction |
| `budget` | LLM spend guard | daily_budget_usd, monthly_budget_usd, alert_thresholds, quota_cooldown_seconds, enabled |
| `test_mode` | Test safety | block_real_api |
| `prompt` | NEXUS.md system | base_prompt_file, load_cwd_prompt, max_chain_depth |
| `logging` | Log config | level, format |
| `hooks` | Hook system | hooks_enabled, hooks_dir |
| `auth` | Auth/security | master_secret_path, keystore_path, kdf_iterations |

**Ordering within files**: Most commonly configured options at TOP. Obscure/rare options at BOTTOM. Comments explain WHY, not just WHAT.

### What MUST Be Configurable

**Rule**: If a variable answers YES to ANY of these → it belongs in config:
- "Should the user be allowed to configure this?"
- "Is this something the user should already have access to configuring?"
- "Without access to this variable in the configuration pipeline, what will this negatively impact?"
- Is this a magic number? (timeout, threshold, limit, retry count, batch size)
- Is this security-related? (key paths, iterations, encryption settings)
- Is this UI/UX related? (theme, colors, streaming, notifications)
- Is this a feature flag? (enable/disable budget guard, test mode, dream cycle)
- Is this a limit? (max tokens, max history, max file size, max retries)

**Examples of extracted magic numbers now in config:**
- `budget.daily_budget_usd`, `budget.monthly_budget_usd`, `budget.alert_thresholds`, `budget.quota_cooldown_seconds`
- `agent.llm_request_timeout`, `agent.llm_max_retries`
- `agent.compaction_tier2_threshold`, `agent.compaction_tier2_fresh_tail`
- `agent.dream_cycle_interval`
- `client.timeout`, `client.retry_limit`
- `server.nats_max_reconnects`, `server.nats_reconnect_wait`

### Env Var Naming Convention

```
NEXUS_<SECTION>__<NESTED_KEY> = value
# Examples:
NEXUS_BUDGET__DAILY_BUDGET_USD=50.0
NEXUS_AGENT__DEFAULT_MODEL=gemini-2.5-pro
NEXUS_SERVER__API_PORT=8080
```

**NOT for**: user preferences (theme, timeout, retry_limit) — those go in user config file.

### Implementation Pattern

```python
# In config.py - add to ConfigSchema
class MyFeatureConfig(BaseModel):
    my_setting: int = Field(default=100, ge=0, description="...")
    my_flag: bool = Field(default=True, description="...")

class ConfigSchema(BaseModel):
    my_feature: MyFeatureConfig = Field(default_factory=MyFeatureConfig)

# In code - access via settings
from nexusagent.infrastructure.config import settings
value = settings.my_feature.my_setting
```

**NEVER** hardcode values that should be configurable. ALWAYS add to config schema first, then reference via `settings`.

### Documentation Requirements

Every config addition MUST include:
1. Field in appropriate Pydantic config class with `Field(description="...")`
2. Entry in `config/nexusagent.yaml` (project defaults)
3. Documentation in AGENTS.md "Configuration" section
4. If env var needed → add to `override_from_env` section list

---

## Critical Lessons Learned (2026-07-22)

1. **Never trust session summaries over `git log`** — The prior session (June 18-19) claimed 80% of the memory system was committed, but `git log` showed zero commits for those files. The subagent work was lost during context compaction. Always verify with `git log --oneline -- <file>` before claiming completion.

2. **Subagents timeout at 600s for complex multi-file work** — The `delegate_task` tool consistently times out at 600s for implementation tasks touching >3 files. Use subagents only for:
   - Research/analysis tasks (1-2 tool calls)
   - Single-file edits
   - Code review/verification
   - Never for complex multi-file implementation — do those inline

3. **Audit workers can miss implementations using unexpected patterns** — The forward/reverse/adversarial audits searched for specific patterns (tool names, class names) but the actual implementation used different patterns (inline methods, different naming). Always read the actual code, not just grep for expected patterns.

4. **Kanban dependency links can become stale** — Tasks were marked `todo` because of dependencies on already-completed work. The prior session completed the work but the Kanban links weren't updated. Always verify dependency status before blocking.

5. **The `patch` tool requires `path=` not `file=`** — Caused 7 consecutive failures. `read_file` and `write_file` also use `path=`. Always use `patch(path="...", old_string="...", new_string="...")`.

6. **I001 import sorting — use ruff, not manual** — Manual import rearrangement often can't satisfy ruff's grouping. Use `ruff check --select I001 --fix`. If auto-fix can't resolve, add `# noqa: I001`.

7. **Code audit pattern: Read → Impact → Search → Edit → Verify** — For any code change:
   - `ast_read` before modifying
   - `impact_analysis` before public API changes
   - `ast_grep` for structural patterns
   - `ast_edit` with `dry_run=true` first
   - `find_references` after renaming/removing

8. **Session compaction loses uncommitted work** — The prior session's subagents created files but the session compacted before commits. The files existed on disk but were never committed. Always commit after subagent work completes, or run subagents in worktrees with auto-collect.

9. **Always check `git status` before starting** — Other agents may have stashed changes or modified files. Several times this session I started editing files that had uncommitted changes from prior work.

10. **The memory system was already 80% done** — The biggest discovery: the prior session implemented cross-session discovery, regex extraction, git-backed memory, DAG compaction, and dream cycle — all working code, just never committed. This means the "10-15 day plan" was actually 1-2 days of wiring and testing.

### Build & Deploy
- **No pyproject.toml build config**: Uses setuptools with `src/` layout.
- **Dependencies**: See `pyproject.toml`. Key: `textual`, `fastapi`, `sqlalchemy[asyncio]`, `sqlite-vec`, `nats-py`, `deepagents`, `langgraph`.
- **Console scripts**: `nexus-server` (FastAPI+WebSocket), `nexus-client` (CLI), `nexus` (TUI), `nexus-web` (Gradio UI)
- **Dev server**: `uvicorn nexusagent.server.server:app --reload --port 8000` (auto-reload on code changes)
- **Docker production**: `docker-compose -f docker-compose.yml up -d` — builds image with all deps
- **Dockerfile**: Multi-stage build (builder → runtime). Uses Python 3.13 slim. Copies `src/` and installs with `pip install -e .`
- **Dockerfile.dev**: Same but installs deps first for layer caching, adds `CMD ["--reload"]` for hot reload
- **docker-compose.yml**: Service: `nexus` (port 8000, host network, volume `nexus-data:/data`). Env from `.env`. Healthcheck on `/health` (checks NATS + JetStream)
- **docker-compose.dev.yml**: Same + mounts `./src:/app/src:delegated` and `./config:/app/config:delegated` for hot reload
- **No CI/CD**: No GitHub Actions or similar. Tests run manually.
- **Server entrypoint**: `python3 -m nexusagent.server` or `nexus-server` (installed console script via `pyproject.toml`)
- **Health check**: `GET /health` returns `{"status": "ok", "version": "...", "nats": "connected|disconnected", "jetstream": true|false}`. `GET /version` returns `{"version": "...", "min_client": "..."}`. TUI performs preflight check before WebSocket connect
- **Config**: `config/nexusagent.yaml` → env vars `NEXUS_*` → defaults. Server loads config at startup, passes to TUI via version handshake
- **Env template**: `.env.example` — copy to `.env`, fill in `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `EXA_API_KEY`, `NEXUS_PORT`

---

## Audit Findings (2026-07-18 / 2026-07-22)

Two comprehensive reviews were conducted. Full reports in:
- `docs/CODE_REVIEW_COMPREHENSIVE.md` — 45+ issues across 8 audit dimensions
- `docs/assessment/2026-07-18-independent-codebase-assessment.md` — Architecture assessment
- `docs/plans/2026-07-22-memory-system-audit-synthesis.md` — Memory system forward/reverse/adversarial audit synthesis
- `docs/plans/2026-07-22-memory-system-v2.md` — Research-backed memory system plan v2

### 🔴 Critical Issues (Fix Immediately)
1. **`refine_node` silently approves plan on failure** — `core/graph.py:125-127` — Returns `plan_approved: True` on exception
2. **API key in URL query param** — `server/websocket.py:35` — Credential exposure in logs/browser history
3. **Sync SQLite in async** — `memory/index/index.py` — Blocks event loop on every memory operation
4. **`SessionManager.get_or_create` busy-wait spin loop** — No timeout, potential deadlock
5. **`sanitize_tool_output` always marks untrusted** — Even when no injection detected, degrades LLM effectiveness
6. **No TLS/SSL** — All traffic including API keys in plaintext

### 🟠 Memory System Audit Findings (2026-07-22)
The memory system forward/reverse/adversarial audits revealed:
- **~40% of planned work was already implemented but uncommitted** — Prior session (June 18-19) built cross-session discovery, regex extraction, git-backed memory, DAG compaction, dream cycle. Lost during context compaction.
- **Critical blocker: Cross-session discovery needs DB migration** — `SessionRepository.find_sessions_by_working_dir()` and `memory_dir` column needed (now done in Phase 18)
- **Dream cycle race condition** — `ConsolidationEngine.consolidate()` deleted files while active sessions wrote to same directory. Fixed with `fcntl.flock` in `DreamCycle`
- **Three sprints, not five phases** — Consolidated to: Foundation (1 day), Maintenance (3 days), Polish (3 days)
- **Deferred**: DAG compression (graduated compaction sufficient), LLM extraction (regex-first), cross-encoder reranking (RRF sufficient)

### Most Notable Findings
- **NATS bus is intentionally only in server layer** — WebSocket uses direct connections (correct architecture, not a bug)
- **Policy-aware tool discovery** is the most impressive feature (production-grade)
- **Hybrid memory system** is well-designed (files as source of truth, derived SQLite index)
- **Deep research pipeline is non-functional** — `_search()` returns dummy data
- **TUI streaming is cosmetic** — LLM bridge has no `astream()`, so streaming is fake

### Score: 6.5/10 — Strong architecture, incomplete implementation

---

## Conventions

### Code Style
- **Python 3.13+**: Uses `type X | Y` union syntax (no `Optional`/`Union`).
- **Pydantic**: All config via Pydantic `BaseModel` with `Field()`.
- **Type hints**: Required on all public functions. `TYPE_CHECKING` guards for circular imports.
- **Docstrings**: Google style (Args/Returns sections).
- **Logging**: `logger = logging.getLogger(__name__)` at module level.

### Commit Messages
- **Format**: `type(scope): description` (conventional commits)
- **Types**: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`
- **Examples**:
  - `refactor: split interfaces/tui.py into focused modules`
  - `fix(config): add missing yolo field to AgentConfig`
  - `docs: update CODEBASE_MAP after Phase 6`

### Branch Naming
- `feature/<name>` — New features
- `fix/<name>` — Bug fixes
- `refactor/<name>` — Structural changes
- `docs/<name>` — Documentation updates

### Testing
- **TDD default**: Write failing test first for business logic/API handlers.
- **Test location**: `tests/` mirrors `src/nexusagent/` structure.
- **Async tests**: Use `@pytest.mark.asyncio` or `asyncio.run()`.
- **Mocking**: `unittest.mock.patch` for external dependencies (WebSocket, DB, NATS).
- **Version changes**: Always update `pyproject.toml` first, then run version-sync test to ensure consistency.

---

## Agent Workflow Rules

### Before Making Changes
1. Read `docs/CODEBASE_MAP.md` for module structure
2. Read `docs/SEMANTIC_INDEX.md` for data flows and state management
3. Check `docs/adrs/` for relevant architectural decisions
4. Run baseline tests: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=no`

### During Changes
5. Follow the established extraction pattern (if refactoring)
6. Preserve all public import paths (compat shims or re-exports)
7. Run tests after every file change (not just at the end)
8. Zero breaking changes — all existing tests must keep passing

### After Changes
9. Update `docs/CODEBASE_MAP.md` if module structure changed
10. Update `docs/SEMANTIC_INDEX.md` if data flows changed
11. Create ADR if the change is architecturally significant
12. Commit with descriptive message
13. Push to GitHub

---

## Tool-Specific Notes

### Sequential Thinking (MCP)
- Use for complex multi-step tasks to avoid missing steps
- Break down into micro-steps, verify each before proceeding

### Worktree Worker (`scripts/worktree-worker.py`)
- Create isolated worktrees for parallel tasks
- `create --name <name> --task <description>` — create worktree + branch
- `list` — show active worktrees
- `collect --name <name>` — get results
- `destroy --name <name>` — cleanup
- `remote --name <name> --server <server> --task <task>` — dispatch to server

---

## Environment

- **OS**: Debian 13 Trixie (Linux 6.12.86+deb13-amd64)
- **Python**: 3.13.5
- **Hardware**: Dell Optiplex i3-3110M, 3.7GB RAM (constrained)
- **Server**: rapidwebs-01 (Debian, 5.7GB+ free RAM) — use for heavy compute
- **Package manager**: pip (no conda/poetry)
- **Venv**: `python3 -m venv .venv && source .venv/bin/activate`

---

## Roadmap

### Authz System (Next Major Feature)

Design and implement a full authorization and key management system:

- **Admin keys**: Full access to all API/SDK routes, can generate/manage other keys, view usage metrics
- **Operator keys**: Scoped to specific workspace directories, cannot access admin functions or generate keys
- **User profiles**: Username, name, notes, workspace location per key
- **Unix integration** (optional mode): Attach operator keys to Unix user/password combos, scoped filesystem permissions via groups, cgroup resource management, chroot jails
- **Key storage**: Move from Fernet file-based keystore to encrypted database (SQLCipher or similar) with encryption at rest
- **Single-user mode**: Admin key has full machine access, operates from any workspace
- **Multi-user mode**: Admin generates operator keys, each scoped to `/home/sysop/Workspaces/${OPERATOR_NAME}`
- **API endpoints**: `POST /auth/keys` (create), `GET /auth/keys` (list), `DELETE /auth/keys/{id}` (revoke), `GET /auth/keys/{id}/usage` (metrics)

### Test System
- Parallel execution via pytest-xdist (`-n auto --dist worksteal`)
- Test markers: `e2e`, `needs_db`, `slow`, `unit`
- Coverage via pytest-cov
- Randomized test order via pytest-randomly

*This file is the living knowledge base for the NexusAgent project. Update it after every significant discovery, refactoring, or architectural decision. When in doubt, point to the reference documents rather than duplicating information.*

---

## [2026-06-28] GEMINI NATIVE TOOLS IMPLEMENTED

**Problem:** Users with only Gemini API keys lacked native tool calling (Google Search, Code Execution, URL Context). OpenRouter had these features but required separate API key.

**Solution:** Migrated from old `google-generativeai` SDK to new **Interactions API** (`google-genai>=2.3.0`):

### Changes

File | Change | Impact
-----|--------|--------
`pyproject.toml` | `google-genai>=2.3.0` | Interactions API support
`src/nexusagent/llm/llm.py` | Rewrite to `client.interactions.create()` | Native tools work automatically
`docs/GEMINI_NATIVE_TOOLS.md` | New documentation | Usage guide + troubleshooting

### Enabled Tools

- **google_search**: Real-time web grounding (e.g., "current Bitcoin price")
- **code_execution**: Python sandbox for math/data tasks
- **url_context**: Fetch + summarize webpages
- **Multi-turn**: `previous_interaction_id` preserves context

### Test Results

```python
# Google Search (real-time data beyond training cutoff)
response = await llm.generate(prompt="What's the current price of Bitcoin?")
# → "$59,200-$59,600 USD (June 29, 2026)" ✅

# Code Execution (Python calculation)
response = await llm.generate(prompt="Sum of first 50 primes")
# → "5117 (calculated via Python)" ✅

# Multi-turn (context preservation)
response2 = await llm.generate(
    prompt="Now calculate the average",
    previous_interaction_id=response1.interaction_id
)
# → Correct calculation using previous context ✅
```

### Commit

- **SHA:** `f4bb7e3`
- **Message:** "feat: Gemini native tool calling via Interactions API"
- **Breaking:** Requires `google-genai>=2.3.0`
- **Benefit:** Users with only Gemini key now have full tool calling

**Reference:** `docs/GEMINI_NATIVE_TOOLS.md`

---

## [2026-06-28] SESSION TRIFECTA — Security + Features + Quality

**Session Goal:** Rapid improvements across security, features, and code quality.

### What We Accomplished

#### 1. ✅ Gemini Native Tool Calling (f4bb7e3)

**Problem:** Users with only Gemini API keys lacked native tool calling capabilities.

**Solution:** Migrated to Google's **Interactions API** (`google-genai>=2.3.0`):
- Upgraded SDK from `google-genai<2.3.0` to `>=2.3.0`
- Rewrote `src/nexusagent/llm/llm.py` to use `client.interactions.create()`
- Enabled native tools automatically:
  - **Google Search**: Real-time web grounding (beyond training cutoff)
  - **Code Execution**: Python sandbox for math/data tasks
  - **URL Context**: Fetch + summarize webpages
- Added multi-turn support via `previous_interaction_id`

**Test Results:**
```python
# Google Search (real-time)
>>> response = await llm.generate(prompt="What's the current price of Bitcoin?")
>>> response.content
"$59,200-$59,600 USD (June 29, 2026)"  # ✅ Real-time data!

# Code Execution (Python calculation)
>>> response = await llm.generate(prompt="Sum of first 50 primes")
>>> response.content
"5117"  # ✅ Calculated via Python sandbox!
```

**Impact:** Users with Gemini key now have full tool calling without needing OpenRouter.

**Documentation:** `docs/GEMINI_NATIVE_TOOLS.md`

---

#### 2. ✅ TOCTOU Approval Race Fix (bc6d7f5) — CRITICAL SECURITY

**Problem:** Time-of-check-time-of-use race in TUI auto-approve flow:
```python
# BEFORE (vulnerable)
if app._auto_approve:  # Check
    await send_approval(...)  # Race: user could toggle between check and send
```

**Solution:** Atomic lock for check+send:
```python
# AFTER (safe)
async with app._auto_approve_lock:
    if app._auto_approve:
        await send_approval(...)
```

**Files Changed:**
- `src/nexusagent/interfaces/tui/app.py`: Added `_auto_approve_lock = asyncio.Lock()`
- `src/nexusagent/interfaces/tui/streaming.py`: 
  - Made `_handle_tool_call_event()` async
  - Wrapped approval logic in lock (2 locations)

**Security Impact:** Eliminates race condition where rapid toggle of auto-approve could bypass approval modal or send duplicate approvals.

**Reference:** `security-hardening-sprint` skill — TOCTOU Race Condition Fix pattern

---

#### 3. ✅ Lint Cleanup (7981a76) — 36 → 0 Errors

**Problem:** 36 lint errors (trailing whitespace, unused imports, style violations)

**Solution:** Applied `ruff check --fix --unsafe-fixes`:
- Removed duplicate `asyncio` imports (streaming.py lines 293, 539)
- Removed unused `google.genai.types` import (llm.py)
- Used ternary operator for input building (SIM108)
- Removed all trailing whitespace (W291, W293)
- Fixed missing newline at EOF (W292)

**Result:** **0 lint errors** — 100% clean codebase! ✅

---

### Session Statistics

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Lint Errors | 36 | 0 | -100% ✅ |
| Security Issues | 1 critical | 0 | -100% ✅ |
| Native Tool Support | ❌ (OpenRouter only) | ✅ (Gemini native) | +Feature 🚀 |
| Commits | 10 | 13 | +3 |
| Documentation Files | 37 | 38 | +1 (GEMINI_NATIVE_TOOLS.md) |

### Commits

```
7981a76 fix: Lint cleanup (36 → 0 errors)
bc6d7f5 fix: TOCTOU approval race in TUI (critical security)
f4bb7e3 feat: Gemini native tool calling via Interactions API
```

### Lessons Learned

1. **Security first:** TOCTOU races are subtle — always use locks for check+act patterns
2. **Native tools > wrappers:** Google's Interactions API provides better Gemini integration than OpenRouter proxy
3. **Lint debt compounds:** 36 errors seemed small, but fixing them now prevents future mistakes
4. **Test before claiming done:** Actually ran Gemini tool calls (Bitcoin price, prime calculation) before committing

### Next Steps (Deferred)

- `docs/MEMORY_ARCHITECTURE.md` — Document v2 memory system (low priority, system works fine)
- TUI Gemini e2e test — Native tools already tested via `llm.py` directly

---

**Session Status:** ✅ **COMPLETE** — Security fix + major feature + perfect lint score = **TRIFECTA** 🏆

---

## [2026-06-28] MEDIUM-IMPACT ITEMS AUDIT

**Finding:** The "remaining refactoring" from plans is **ALREADY COMPLETE**!

### What We Discovered

#### 1. ✅ TUI App Split — DONE
**Plan said:** "Extract screens + commands from app.py (366L)"  
**Reality:** Already split across 5 clean modules:
- `app.py` (366L) — App lifecycle, bindings, state ✅
- `streaming.py` (550L) — Event dispatch + slash commands ✅
- `input.py` — User input handling ✅
- `websocket.py` — WebSocket comms ✅
- `tui_widgets.py` — Screens/modals ✅

**Verification:** Zero complexity issues, no functions >50 lines

#### 2. ✅ Session.send() Refinement — DONE
**Plan said:** "Extract approval + prompt building from send() (652L total)"  
**Reality:** Wave 5 already did this! Current `send()` is 60L orchestrator:
- `_build_messages_list()` — Context assembly ✅
- `_apply_compaction()` — Compaction logic ✅
- `_stream_agent_response()` — Agent streaming ✅
- `_handle_send_error()` — Error handling ✅

**Verification:** Complexity 28→5 (82% reduction), already committed as `dd7f48b`

#### 3. ✅ Session-Memory Integration — DONE
**Plan said:** "Wire HybridMemoryManager into session loop (Phase 1)"  
**Reality:** Already wired in `session_base.py` lines 70-74:
```python
self.hybrid_memory = HybridMemoryManager(
    str(self._memory_dir),
    parent_memory_dir=parent_memory_dir,
)
self.hybrid_memory.initialize()
```

**Usage:** `session.py:207` calls `self.hybrid_memory.get_memory_context()` every turn ✅

**Test:** SessionBase instantiates correctly, memory_dir created, HybridMemoryManager initialized

---

### Conclusion

**The refactoring plan (`docs/REFACTORING_PLAN.md`) is OUTDATED.**

Phases 1-7 + 16-17 marked as "complete" ✅, but Phases 8-14 (TUI split, session refinement, memory integration) were **also completed** in Waves 1-5, just not documented in the plan.

**Action:** Archive old refactoring plan, create new "Next Opportunities" doc with actual remaining work.

---

**Lesson:** Run `git log --oneline` and read actual code BEFORE trusting old plans. The codebase evolved faster than the documentation.
