# Jules — NexusAgent MEMORIES

> **Purpose:** High-value permanent context for every Jules session.
> **Read this file first thing each session start.**
> **Last updated:** 2026-07-20

---

## 1. Project Identity

NexusAgent is a **production-grade AI coding agent platform** — terminal-native, privacy-first, with hybrid memory, NATS-backed task orchestration, a Textual TUI, FastAPI WebSocket server, and multi-provider LLM bridge. **Do NOT confuse it with Hermes Agent (Nous Research) — that is a separate project we use but never modify.** Repository: `github.com/stephanos8926-lgtm/NexusAgent`. SSH remote: `git@github.com:stephanos8926-lgtm/NexusAgent.git`.

---

## 2. Environment Setup — CRITICAL

The project requires **Python >= 3.13**. Jules VM defaults to Python 3.12.11. **Always start every session with:**

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
```

Tests require `PYTHONPATH=src:.` — use this in every pytest invocation:

```bash
PYTHONPATH=src:. python3 -m pytest tests/core/ -q --tb=no --asyncio-mode=auto
```

Do NOT install system-wide packages. Use `uv` for everything. Do NOT use `pip` directly.

---

## 3. Source Layout — What Lives Where

```
src/nexusagent/
├── core/           # Agent core — session, worker, agent, graph, task, events
│   ├── task/       # Phase 2: Task, TaskState, Checkpoint, TaskStore, RecoveryManager
│   ├── events/     # Phase 3: SystemEvent, EventEmitter, EventStore, subscribers
│   ├── worker/     # WorkerPool + handler (Phase 4 WorkerGraph in progress)
│   ├── session/    # SessionManager, SessionBase
│   ├── agent.py    # DeepAgents Agent wrapper
│   └── graph.py    # LangGraph research workflow (existing pattern to follow)
├── tools/          # 25+ tools + registry subpackage
├── memory/         # Hybrid memory (FileMemory + SQLite index + DreamCycle)
├── infrastructure/ # Config, DB, NATS bus, auth, utilities
├── server/         # FastAPI app, WebSocket, SDK, version
├── interfaces/     # CLI (Click), TUI (Textual), web (Gradio)
└── llm/            # Multi-provider LLM bridge
```

Tests mirror source: `tests/core/` for `src/nexusagent/core/`. Configuration in `config/nexusagent.yaml`. Base prompt in `config/NEXUS.md`. Version single-sourced from `pyproject.toml` via `importlib.metadata`.

---

## 4. 12-Phase Migration — Strict Order, No Skipping

| Phase | Name | Status |
|-------|------|--------|
| 1 | Runtime Foundation | ✅ **Delivered** — 104 tests |
| 2 | Durable Task Execution | ✅ **Delivered** — PR #10 |
| 3 | Event-Driven Core | ✅ **Delivered** — PR #11, 173 tests |
| 4 | **LangGraph Worker Runtime** | 🟡 **IN PROGRESS** — PR #13 (empty commit, needs fix) |
| 5 | Planner & Orchestrator | ⬜ Not started |
| 6-11 | Remaining phases | ⬜ Not started |

**Chief Architect Directive: NEVER skip phases.** Each phase gates the next. Phase 1 → 2 → 3 → 4 → 5 → ... in strict order. The full spec for every phase lives in `docs/architecture/migration/`.

---

## 5. Testing Conventions

- **Core tests:** `PYTHONPATH=src:. python3 -m pytest tests/core/ -q --tb=no --asyncio-mode=auto`
- **Baseline:** 173 passing, 9 pre-existing skips (test skeletons for future features)
- **2 tests may fail** when NATS isn't connected — expected, skip them with `-k "not nats"`
- **DO NOT** run the full `tests/` suite — it times out on slow environments and includes e2e/mock/performance tests that aren't relevant
- **Always use `--asyncio-mode=auto`** for async tests
- New features need new tests under the matching `tests/` subdirectory

---

## 6. Event System Architecture

Phases 3 delivered a complete event-driven architecture:

```
Task.transition_to() → TaskEvent → emit_event_sync() → nexus.task.* NATS subjects
WorkerPool._run_worker() → WorkerEvent → emit_event_sync() → nexus.worker.* NATS subjects
```

Key files in `src/nexusagent/core/events/`:
- `base.py` — `SystemEvent` base class with `EventType` enum and `to_dict()`/`to_json()` serialization
- `task_events.py`/`worker_events.py`/`tool_events.py`/`policy_events.py` — typed event factories
- `emitter.py` — `EventEmitter` with async `emit()` + sync `emit_event_sync()` via background thread
- `event_store.py` — SQLite append-only log with query-by-time/source/type
- `subscribers.py` + `pol_subscriber.py`/`memory_subscriber.py`/`dashboard_subscriber.py` — JetStream durable consumer framework

**When building anything that produces or consumes events, wire through this system.** Do NOT create ad-hoc event emission.

---

## 7. Task Model (Phase 2) — Durable State Machine

The Phase 2 Task model is the backbone of all worker execution:

- **`Task` dataclass**: `id`, `objective`, `owner`, `state` (7-state enum), `parent_task`, `child_tasks`, `checkpoints`, `artifacts`
- **`TaskState` enum**: `CREATED → PLANNING → EXECUTING → VERIFYING → COMPLETED | FAILED | RECOVERING`
- **`StateTransitionValidator`**: validates every transition, rejects invalid ones
- **`TaskStore`**: SQLite-backed async persistence via SQLAlchemy ORM
- **`Checkpoint`**: `current_node`, `completed_actions`, `files_changed`, `tool_results`, `next_action`
- **`RecoveryManager`**: retry (exponential backoff max 3) → rollback → escalate (emit `worker.failed`)

Located at `src/nexusagent/core/task/`. All worker execution should integrate with this model.

---

## 8. LangGraph Patterns — Follow the Research Graph

The existing research graph at `src/nexusagent/core/graph.py` is the **pattern to follow** for any new LangGraph work:

```python
# Factory function pattern
async def create_research_graph(db_path: str | None = None) -> Any:
    workflow = StateGraph(dict)
    workflow.add_node("plan", plan_node)
    workflow.add_edge(START, "plan")
    workflow.add_conditional_edges("execute", route_fn, {...})
    # Checkpointing via AsyncSqliteSaver
    async with AsyncSqliteSaver.from_conn_string(db_path or ":memory:") as memory:
        await memory.setup()
        return workflow.compile(checkpointer=memory)
```

Key patterns to copy:
- `StateGraph(dict)` with `TypedDict` for state
- Factory function returning compiled graph
- `AsyncSqliteSaver` for checkpoint persistence
- SECURITY: validate `db_path` is within workspace root
- Conditional edges with routing functions
- Graceful fallback when `aiosqlite` not available

---

## 9. Infrastructure Topology — 3 Incus VMs

NexusAgent runs across 3 Incus VMs over Tailscale mesh:

| VM | Tailscale IP | SSH Host | Role | Services |
|----|-------------|----------|------|----------|
| `infra` | 100.122.246.112 | `ssh infra` | Infrastructure | NATS JetStream, PostgreSQL 16, Caddy, Honcho API |
| `enterprise` | 100.81.49.91 | `ssh enterprise` | Enterprise apps | — |
| `dev` | 100.109.15.31 | `ssh dev` | Development | Phase worktrees, test execution, dev builds |

- **NATS** runs on `infra` VM at port 4222 (NOT on `dev` — do not expect it there)
- **Dev VM worktrees** at `/home/sysop/Workspaces/NexusAgent/.hermes/worktrees/<name>/` with their own venv
- **Workstation RAM ceiling: 4GB** — do NOT run heavy parallel processes locally

---

## 10. What NOT To Do

- **NEVER modify the Hermes Agent repo** (`~/.hermes/hermes-agent/` — belongs to Nous Research). Zero exceptions.
- **Do NOT modify `src/` files without tests** — every change must maintain 173+ passing baseline
- **Do NOT create ad-hoc event emission** — always wire through `src/nexusagent/core/events/`
- **Do NOT use `pip`** — use `uv` for all Python package operations
- **Do NOT skip phases** — the 12-phase migration is strict-ordered
- **Do NOT run full test suite** — target `tests/core/` only (full suite times out)
- **Do NOT push to `master` directly** — create PRs, let CI run
- **Do NOT run out of memory on workstation** — RAM is 4GB with ~300MB free during heavy use; offload to dev VM or Jules
- **Do NOT commit empty changes** — Jules PR #13 was an empty commit (messaged but zero files); always verify `git diff-tree --no-commit-id -r HEAD --name-only | wc -l` > 0 before creating PR
