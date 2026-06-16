# AGENTS.md — NexusAgent Project Knowledge Base

> Last updated: 2026-07-18
> Maintained by: OWL (Lucien)
> Purpose: Critical project knowledge for any agent working on this codebase

---

## Project Overview

NexusAgent is a production-grade AI coding agent platform. It combines an LLM-powered agent (via `deepagents` / LangGraph) with a NATS-backed task orchestration system, a Textual TUI, a FastAPI WebSocket server, and a hybrid file+vector memory system.

**Language:** Python 3.13+ | **Package:** `nexusagent` (src layout) | **Tests:** pytest (528 pass / 15 pre-existing fail)

---

## Critical Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| **Codebase Map** | `docs/CODEBASE_MAP.md` | Module structure, fan-in/fan-out, extraction candidates |
| **Semantic Index** | `docs/SEMANTIC_INDEX.md` | Data flows, state management, extension points, tech debt |
| **Refactoring Plan** | `docs/REFACTORING_PLAN.md` | 14-item prioritized refactoring roadmap |
| **State** | `docs/STATE.md` | Module-by-module inventory (⚠️ partially outdated) |
| **Compliance** | `docs/DOC_COMPLIANCE.md` | Documentation audit and gap analysis |
| **Version** | `src/nexusagent/version.py` | Single source of truth (importlib.metadata) |
|| **ADRs** | `docs/adrs/` | Architecture decision records (0001-0005) |
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
│   │   ├── memory_bank.py   # Memory class (scoped SQLite bank)
│   │   ├── memory_manager.py # MemoryManager (lifecycle)
│   │   ├── hybrid_memory.py # HybridMemoryManager (file + index)
│   │   ├── memory_files.py  # FileMemory (canonical)
│   │   ├── memory_index.py  # Compat shim → index/ subpackage
│   │   ├── index/           # embeddings.py, index.py (extracted Phase 6)
│   │   └── compaction.py    # CompactionPipeline
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
| 17 | Memory split (474L) | `memory/` subpackage: memory_item.py, memory_bank.py, memory_manager.py, hybrid_memory.py; memory.py = compat shim |

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

### TUI
- **Textual framework**: Uses Textual (not Rich directly). Widgets extend `Static`, `Horizontal`, etc.
- **CSS variables**: Theme colors use `$surface`, `$text`, `$primary` etc. defined by `register_themes()`.
- **NO_COLOR**: Respects https://no-color.org. Check `NO_COLOR` env var before adding color.
- **SIGWINCH**: Resize handler installed in `on_mount()`. Uses debounce (0.2s) to avoid excessive re-renders.
- **Streaming**: `_write_response_chunk()` accumulates tokens in `_streaming_response` string. `_finalize_response()` writes to log and clears widget.

### Memory System
- **Two systems coexist**: Old SQLite `Memory` class (in `memory.py`) and new file-based `HybridMemoryManager` (also in `memory.py`). Session uses the hybrid system.
- **Embedding fallback chain**: Gemini API → local sentence-transformers → SHA256 hash (deterministic, low quality)
- **sqlite-vec**: Virtual table for vector search. Requires `sqlite_vec.load(conn)` at startup.

### Testing
- **Baseline**: 528 pass / 15 fail (all pre-existing). Zero regressions allowed.
- **Run command**: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
- **Timeout**: Full suite takes ~100s. Use `timeout 120` for safety.
- **Pre-existing failures**: `test_orchestration.py` (module path issues), `test_tui_responsive.py` (wrong mock paths), `test_e2e_production.py` (WebSocket dependency)
- **New tests**: `test_version.py` (8), `test_server_version.py` (5) — version system coverage

### Build & Deploy
- **No pyproject.toml build config**: Uses setuptools with `src/` layout.
- **Dependencies**: See `pyproject.toml`. Key: `textual`, `fastapi`, `sqlalchemy[asyncio]`, `sqlite-vec`, `nats-py`, `deepagents`, `langgraph`.
- **Dev server**: `uvicorn nexusagent.server.server:app --reload --port 8000` (auto-reload on code changes)
- **Docker dev**: `docker-compose -f docker-compose.dev.yml up` for containerized development
- **No CI/CD**: No GitHub Actions or similar. Tests run manually.

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

*This file is the living knowledge base for the NexusAgent project. Update it after every significant discovery, refactoring, or architectural decision. When in doubt, point to the reference documents rather than duplicating information.*
