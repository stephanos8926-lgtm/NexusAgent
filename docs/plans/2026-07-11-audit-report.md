# NexusAgent Combined Audit Report

**Date:** 2026-07-11  
**Auditors:** 3 parallel (reverse audit, forward audit, manual verification)  
**Codebase:** 32 Python files in `src/nexusagent/`  
**Baseline:** 44 tests passing (Stages 1-3 complete)  
**Orphan code:** 8 files (25% of codebase)  

---

## Methodology

Three independent audits ran in parallel:

1. **Reverse Audit** — traced from entry points → imports → used modules. Anything NOT in the used graph is orphan/dead code. Also checked for dead exports, unreachable paths, and name shadowing.
2. **Forward Audit** (api-sdk-audit skill) — read all source files top-down, verified cross-file references, config field drift, call signature mismatches, SDK↔API completeness gaps.
3. **Manual Verification** — confirmed critical findings from both audits by reading source and running checks.

Findings below are deduplicated and merged by severity.

---

## Critical (will crash at runtime)

### C1. `agent.invoke()` does not exist — every task silently fails

- **File:** `agent.py:122`
- **Code:** `result = agent.invoke(state)`
- **Problem:** `Agent` class defines `__call__` (line 106), not `.invoke()`. This raises `AttributeError` on every task.
- **Masked by:** The `except Exception` on line 124 catches the error and returns `{"result": f"task_complete: {task_desc}"}`, making it appear the task succeeded.
- **Impact:** The agent **never actually processes any tasks**. Every result is a silent failure masquerading as success.
- **Fix:** Change `agent.invoke(state)` to `agent(state)`

### C2. `llm.py` uses broken `src.nexusagent.*` import path

- **File:** `llm.py:9-10`
- **Code:**
  ```python
  from src.nexusagent.config import settings
  from src.nexusagent.utils import retry_with_backoff
  ```
- **Problem:** The `src.` prefix is invalid for installed packages. Python resolves `nexusagent.*` from the package root, not `src.nexusagent.*`.
- **Impact:** LLM provider cannot be imported at all. `ImportError` at runtime.
- **Fix:** Change to `from nexusagent.config import settings` and `from nexusagent.utils import retry_with_backoff`

### C3. `orchestration.py` uses broken `src.nexusagent.*` import path

- **File:** `orchestration.py:6-8`
- **Code:**
  ```python
  from src.nexusagent.llm import llm
  from src.nexusagent.registry import ToolRegistry
  from src.nexusagent.tools.research import SearchResult, research_orchestrator
  ```
- **Problem:** Same `src.` prefix issue as C2. Additionally, `SearchResult` and `research_orchestrator` don't exist in `tools/research.py`.
- **Impact:** Module is completely broken. `ImportError` on any attempt to use it.
- **Fix:** This module is also orphan (imported nowhere) — recommend removal.

---

## High (broken functionality or significant dead code)

### H1. `keystore.py` — orphan (imported nowhere)

- `Keystore` class with env-var-based key management.
- Never imported by any file in the codebase.
- Duplicates `auth.py` functionality with different approach.

### H2. `auth.py` — orphan (imported nowhere)

- `AuthManager` + `auth_manager` singleton. Never imported.
- `api_auth.py:verify_api_key` has TODO to validate against keystore but doesn't use either.
- **Current state:** API accepts any non-empty `X-API-Key` header — no actual validation.

### H3. `registry.py` (old `ToolRegistry`) — orphan

- Contains `ToolRegistry`, `ToolDefinition`, `find_suggested_tool()`.
- Never imported (except broken reference in `orchestration.py`).
- Completely superseded by `tools/registry.py` (`_REGISTRY`, `ToolInfo`, policy enforcement).

### H4. `orchestration.py` — orphan + completely broken

- `DeepResearchOrchestrator` with `_generate_plan()` and `_refine_plan()`.
- Both methods have hardcoded mock returns instead of parsing LLM responses.
- Broken imports (see C3). Dead module.

### H5. `graph.py` — orphan (only imported by tests)

- `create_graph()` with LangGraph + SqliteSaver.
- Never reachable from any entry point.
- Contains `asyncio.run()` inside sync function — will crash if called from async context.

### H6. `mcp/client.py` — stub with mock returns

- `_connect_stdio/_connect_sse/_connect_websocket`: just print + set status "connected".
- `call_tool()` always returns `{"result": "Success calling ..."}`.
- `list_tools()` returns hardcoded `[{"name": "example_tool"...}]`.
- Never imported anywhere. Non-functional MCP integration.

### H7. `tools/discovery.py` — orphan

- `validate_tool_call()` function. Never imported anywhere.
- Superseded by `auto_correct()` in `tools/registry.py`.

### H8. `list_tasks()` drops `metadata_json`

- **File:** `db.py:166-176`
- `TaskModel` has `metadata_json` column (db.py:38).
- `create_task()` writes it correctly (db.py:119).
- `list_tasks()` returns dicts that omit `metadata_json` — it's silently dropped.
- **Impact:** Task metadata is persisted but never returned to API consumers.

### H9. `nexus-web` entry point returns `gr.Blocks`, not a callable

- **File:** `pyproject.toml:42`: `nexus-web = "nexusagent.web_ui:create_ui"`
- `create_ui()` returns a `gr.Blocks` object. Console script entry points need a callable that can be invoked.
- **Impact:** `nexus-web` command will fail.
- **Fix:** Create a `run_ui()` function that calls `create_ui().launch()`.

### H10. `nexus-server` entry point is FastAPI app, not a callable

- **File:** `pyproject.toml:39`: `nexus-server = "nexusagent.server:app"`
- `app` is a `FastAPI()` instance. Console scripts need a callable.
- **Impact:** `nexus-server` command won't work as expected.
- **Fix:** Create a `run()` function that calls `uvicorn.run(app, ...)`.

---

## Medium (incomplete or inconsistent)

### M1. `datetime.utcnow` deprecated (Python 3.12+)

- `models.py:21-22,31` and `db.py:36-37,47` use `datetime.utcnow` as default_factory.
- Should use `datetime.now(timezone.utc)` or callable `datetime.utcnow()`.
- Currently generates deprecation warnings in test output.

### M2. SDK missing methods mirroring API endpoints

- API has `GET /workers` → SDK has no `list_workers()`
- API has `GET /tools` → SDK has no `list_tools()`
- API has `GET /health` → SDK has no `health_check()`

### M3. `asyncio.get_event_loop()` deprecated in SDK

- **File:** `sdk.py:133,138` — `wait_for_result()` uses `asyncio.get_event_loop().time()`.
- Deprecated since Python 3.10. Should use `asyncio.get_running_loop()`.

### M4. `loop_threshold` and `post_research_retries` are dead config fields

- **File:** `config.py:47-48`
- `settings.loop_threshold` and `settings.post_research_retries` are never referenced anywhere.
- Leftover from old graph/orchestration logic.

### M5. No input validation on `task_id` path parameters

- `GET /tasks/{task_id}/status`, `GET /tasks/{task_id}/result`, `POST /tasks/{id}/cancel`, `POST /tasks/{id}/retry` accept any string as `task_id`.
- No UUID format validation. Invalid IDs silently return None/400.

### M6. Double task creation in server + worker

- `server.py:94-98` calls `task_repo.create_task()` before publishing to NATS.
- `worker.py:62-68` calls `task_repo.create_task()` again on receiving the NATS message.
- DB `create_task` is idempotent (checks for existence), but this is redundant double-write.

### M7. `agent.py` side-effect import of `register_all` is fragile

- **File:** `agent.py:8`: `import nexusagent.tools.register_all`
- This import populates `_REGISTRY` as a side effect. If someone later imports from `tools.registry` without first importing `register_all`, `_REGISTRY` will be empty.
- The ordering dependency is implicit and fragile.

### M8. `CircuitBreakerError` never caught specifically

- `utils.py:240`: `CircuitBreakerError` is raised by CircuitBreaker when open.
- Worker's except clauses catch bare `Exception`, not `CircuitBreakerError`.
- This means circuit-breaker-rejected calls are indistinguishable from other failures.

---

## Low (nice-to-have)

| # | Finding | File |
|---|---------|------|
| L1 | `retry_on_false` has broken `return` in sync path (returns `None` instead of wrapper) | `utils.py:226` |
| L2 | Inline imports in `server.py` should be top-level | `server.py` (6 locations) |
| L3 | `cryptography.backends.default_backend` deprecated (>= 41.0) | `auth.py:9,57` |
| L4 | `metadata` field has no size limit — arbitrary JSON stored verbatim | `server.py:74` |
| L5 | `asyncio.Lock()` at module level emits deprecation | `utils.py:289` |
| L6 | `graph.py` uses sync `sqlite3` vs async `aiosqlite` (inconsistent) | `graph.py:45-46` |
| L7 | `hasattr(task, "metadata")` is dead code — `TaskSchema.metadata` always exists | `worker.py:67` |
| L8 | `SubmitTaskRequest.metadata` uses mutable default `dict = {}` (Pydantic-safe but inconsistent) | `server.py:74` |

---

## Dead Exports (defined but never used)

| Export | File | Notes |
|--------|------|-------|
| `require_policy()` | `tools/registry.py` | Decorator helper, never applied to any tool |
| `check_tool_access()` | `tools/registry.py` | Inline check helper, never called |
| `clear_policy_context()` | `tools/registry.py` | Never called (needed for agent cleanup) |
| `get_policy_context()` | `tools/registry.py` | Never called |
| `get_tool_info()` | `tools/registry.py` | Never called |
| `retry_on_false()` | `utils.py` | Sync path broken; `retry_with_backoff` IS used |
| `CircuitBreakerError` | `utils.py` | Raised but never caught specifically |
| `DatabaseManager.execute()` | `db.py` | Raw SQL method, never called |
| `get_read_files()` | `tools/fs.py` | Never called externally |
| `reset_read_tracking()` | `tools/fs.py` | Never called externally |

---

## Unreachable Code Paths

| Code | File | Reason |
|------|------|--------|
| `agent.invoke(state)` | `agent.py:122` | Agent has no `.invoke()` — always raises AttributeError |
| `if research_done and loop_count > 6` | `graph.py:38-39` | After research resets count=0, exits at count>4; >6 is unreachable |
| `asyncio.run(push_error_to_nats(...))` | `graph.py:39` | Inside unreachable branch |

---

## Orphan Module Map

```
src/nexusagent/
├── llm.py              ← ORPHAN (broken imports, never imported correctly)
├── orchestration.py    ← ORPHAN (broken imports + mock returns)
├── registry.py         ← ORPHAN (superseded by tools/registry.py)
├── keystore.py         ← ORPHAN (never imported)
├── auth.py             ← ORPHAN (never imported)
├── graph.py            ← ORPHAN (only imported by tests)
├── mcp/client.py       ← ORPHAN (stub, never imported)
└── tools/discovery.py  ← ORPHAN (superseded by auto_correct())
```

---

## Summary Table

| Area | Status | Critical | High | Medium | Low |
|------|--------|----------|------|--------|-----|
| Core runtime | 🔴 | 1 | | | |
| Import paths | 🔴 | 2 | | | |
| Dead/orphan modules | ⚠️ | | 7 | | |
| API surface | ⚠️ | | 2 | 2 | |
| SDK ↔ API sync | ⚠️ | | | 2 | |
| Config drift | ⚠️ | | 1 | 1 | |
| Deprecations | 🟡 | | | 1 | 3 |
| Input validation | 🟡 | | | 1 | |
| **Total** | | **3** | **10** | **8** | **8** |

---

## Recommended Fix Priority (Stage 4+)

1. **C1** — Fix `agent.invoke(state)` → `agent(state)` — **blocks all task processing**
2. **C2** — Fix `src.*` imports in `llm.py` — **blocks LLM provider**
3. **H8** — Return `metadata_json` in `list_tasks()` — data loss
4. **H9/H10** — Fix entry points (`nexus-server`, `nexus-web`)
5. **H1-H7** — Remove/consolidate 7 orphan modules
6. **H2** — Wire `auth.py` into `api_auth.py`
7. **M3** — `asyncio.get_running_loop()` in SDK
8. **M1** — Fix `datetime.utcnow` deprecation
9. **M2** — Add missing SDK methods (`list_workers`, `list_tools`, `health_check`)
