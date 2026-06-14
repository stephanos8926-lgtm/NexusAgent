# Forward Audit Report: Version Handshake + Dev Workflow v1

> **Date**: 2026-07-19
> **Auditor**: OWL (Lucien)
> **Spec**: `docs/specs/version-handshake-v1.md`
> **Plan**: `docs/plans/version-handshake-v1.md`
> **Test baseline**: 485 passed / 15 failed (pre-existing) — confirmed live

---

## Summary

The spec and plan are **largely accurate**. Most file paths, current-state claims, and proposed changes are verified correct against the actual codebase. Several issues were found: one file-path discrepancy in the spec's File Manifest (🔍), one over-engineered field in the spec's `/version` response (⚠️), one missing guard in the plan's proposed code (⚠️), and one plan task with a feasibility concern (⚠️). No showstopper errors (❌) were found — all proposed changes are technically feasible.

---

## Verified Claims (✅)

### File Existence and Paths
| File | Claim | Verified |
|------|-------|----------|
| `src/nexusagent/server/server.py` | EXISTS, has `/health` endpoint | ✅ Line 148: `@app.get("/health")` |
| `src/nexusagent/server/sdk.py` | EXISTS, has `NexusSDK.health_check()` | ✅ Line 164: `async def health_check(self) -> dict:` |
| `src/nexusagent/interfaces/cli.py` | EXISTS, has `--version`, `submit`, `run` | ✅ Line 23: `@click.version_option`, Line 28: `submit`, Line 59: `run` |
| `src/nexusagent/interfaces/tui.py` | EXISTS, has WebSocket loop, `/version` command | ✅ Line 237: `_ws_loop()`, Line 488: `/version` handler |
| `src/nexusagent/infrastructure/config.py` | EXISTS, `ServerConfig` model | ✅ Line 12: `class ServerConfig(BaseModel)` |
| `docker-compose.yml` | EXISTS, 22 lines | ✅ Confirmed |
| `pyproject.toml` | EXISTS, version `0.1.0`, entry points | ✅ Line 3: `version = "0.1.0"`, Line 41-44: scripts |
| `config/nexusagent.yaml` | EXISTS, `server` section | ✅ Line 1-4: `server:` block |

### Current State Claims (Spec §1 — Problems)
| Claim | Verdict |
|-------|---------|
| "Server emits no version info" | ✅ Confirmed — no `VERSION` constant, no `/version` endpoint |
| "TUI connects with no version check" | ✅ Confirmed — `_ws_loop()` goes straight to `websockets.connect()` with no HTTP preflight |
| "No `--reload` flag for local dev" | ✅ Confirmed — `run()` takes no arguments; `uvicorn.run()` called without `reload=` |
| "Docker Compose has no watch/hot-reload" | ✅ Confirmed — no `develop:` or `watch:` sections |
| "No `docker compose down && up` pain point" | ✅ Confirmed — `docker-compose.yml` is production-only |

### Technical Feasibility
| Proposal | Verdict |
|----------|---------|
| Add `/version` endpoint to `server.py` | ✅ FastAPI `@app.get("/version")` — trivial addition |
| Add `reload: bool` to `ServerConfig` | ✅ Pydantic `Field(default=False)` — trivial |
| Pass `reload=` to `uvicorn.run()` | ✅ `uvicorn.run(reload=True)` is supported; `reload` param confirmed in signature |
| Docker Compose `develop.watch` | ✅ Docker Compose v5.1.4 supports `develop.watch` (requires Compose v2.22+) |
| `VERSION` file creation | ✅ No conflict; file does not exist yet |
| `Dockerfile.dev` creation | ✅ `Dockerfile` exists as template — can derive dev variant |
| Enhance `health_check()` in `sdk.py` | ✅ Method exists at line 164 — can add version fields |
| Preflight in `cli.py` | ✅ `NexusSDK` and `sdk` global exist; `get_version()` already defined at line 11 |
| TUI version check | ✅ `_handle_slash_command` can be extended; `AppMessage` widget exists for warnings |

### Version and Dependencies
| Claim | Verdict |
|-------|---------|
| `pyproject.toml` version = `0.1.0` | ✅ Confirmed |
| `uvicorn` in dependencies | ✅ Line 15 of `pyproject.toml` |
| `uvicorn.run()` accepts `reload` param | ✅ Confirmed via `inspect.signature` |
| Existing `--version` uses `get_version()` | ✅ Line 11: `def get_version()` with `importlib.metadata` fallback |
| Existing `/version` TUI command | ✅ Line 488: hardcoded `"NexusAgent v0.1.0"` — needs updating to be dynamic |

---

## Corrections Needed (⚠️)

### 1. `workers` field in `/version` response is misleading
- **Spec** (§4.1): `"workers": 4` is proposed in the `/version` JSON response.
- **Reality**: The server co-locates a single `NexusWorker` instance (Line 42 of `server.py`: `worker_task = asyncio.create_task(worker.start())`). The worker uses an `asyncio.Semaphore(max_workers=4)` for concurrency, but `worker.max_workers` is only on the `WorkerPool` class, not on the singleton `worker` instance. The singleton is `NexusWorker`, which has no `max_workers` attribute.
- **Fix**: Either expose `max_workers` via the worker's config or remove the `workers` field from `/version`. Recommended: remove it or derive from `settings.server.worker_threads`.

### 2. `VERSION` file should not be the single source of truth without a sync mechanism
- **Plan** (Task 1.1): proposes `VERSION` file with `0.1.0`.
- **Spec** (Q1): acknowledges it should match `pyproject.toml`.
- **Risk**: Without an automated sync test or `importlib.metadata` read, the `VERSION` file, `pyproject.toml`, and `server.py`/`sdk.py` constants will drift.
- **Fix**: Add a test that reads `VERSION` file, `pyproject.toml`, and `server.VERSION` constant and asserts all three match. The plan mentions this in Q1 ("Yes — add a test") but it is not in any task.

### 3. Plan Task 3.4 (enhance `--version`) breaks existing Click contract
- **Plan**: "Replace with custom callback that also checks server version."
- **Reality**: `cli.py` Line 23 uses `@click.version_option(version=f"nexusagent {get_version()}")`. Replacing this with a custom callback requires importing async SDK code synchronously in a Click context, which is non-trivial (it creates an event loop clash with the `asyncio.run()` in the command body).
- **Fix**: Either (a) create a separate `nexus --version --server` flag that skips `version_option` and does its own thing, or (b) add a `--check-server` flag to the main group. Do not remove the existing `@click.version_option` — it's the standard Click mechanism.

### 4. Plan Task 2.1 proposes duplicate version constants
- **Plan**: Add `SERVER_VERSION = "0.1.0"` and `MIN_CLIENT_VERSION = "0.1.0"` to `sdk.py`.
- **Reality**: The spec says "Single source of truth" but introduces `VERSION` file, `server.py` `VERSION` constant, AND `sdk.py` `SERVER_VERSION` constant — three copies of the same string.
- **Fix**: Read from `importlib.metadata` or a single shared constant. All version strings should be derived from `pyproject.toml` at runtime. Hardcoding in 3 places guarantees drift.

### 5. TUI `_check_server_version` needs async HTTP, not `urllib.request`
- **Plan** (§6.3): Proposes `urllib.request.urlopen()` for the preflight.
- **Reality**: `urllib.request` is synchronous and will block the Textual event loop. The TUI is fully async (Textual `App`). Using `urllib` in `_ws_loop()` would freeze the UI during the HTTP request.
- **Fix**: Use `httpx` (already in dependencies, line 27 of `pyproject.toml`) or `aiohttp` for the async preflight call.

---

## Errors Found (❌)

No blocking errors found. All proposed changes are structurally feasible given the current codebase.

---

## Missing Items (🔍)

### 1. Spec File Manifest lists `src/nexusagent/server/server.py` and `src/nexusagent/server/sdk.py`
- The spec §4 says "Add version constant in `server.py`" and §5 says "Add constants to `sdk.py`".
- This is correct — both files exist at these exact paths.
- ✅ No issue, but the spec §5 is misleading: it says `SERVER_VERSION = "0.1.0"  # Single source of truth`. If `sdk.py` is the single source, `server.py` should import from it, not define its own `VERSION`. The spec contradicts itself.

### 2. Plan Phase 5 doesn't mention `NEXUS_LOG_LEVEL=DEBUG` in dev compose
- **Plan Task 5.2**: `Dockerfile.dev` with `ENV NEXUS_LOG_LEVEL=DEBUG` — good.
- **Missing**: The `docker-compose.dev.yml` (Plan §8.1) already sets `NEXUS_LOG_LEVEL=DEBUG` in the `environment` block, but `Dockerfile.dev` would also set it. This is redundant but not harmful. However, the plan should note that `Dockerfile.dev` can simply be `FROM nexus-base` + `ENV NEXUS_LOG_LEVEL=DEBUG` to avoid duplicating the full build.

### 3. No task for `nexus-client` entry point test
- **Plan Phase 6**: Tests `test_cli_preflight.py` for `nexus run` and `nexus --version`.
- **Missing**: No test for `nexus-client submit` preflight. The `submit` command (line 28-56 of `cli.py`) has no version check either. The plan should explicitly mention adding `preflight()` to the `submit` command as well.

### 4. Docker Compose `develop.watch` format needs Compose v2.22+
- **Verified**: Docker Compose v5.1.4 is installed, which supports `develop`.
- **Missing**: The plan should note that `develop.watch` requires Docker Compose file format 3.8+ and Docker Compose CLI v2.22+. If anyone uses an older version, this is silently ignored. A fallback `docker-compose.dev.yml` without `develop` should be provided.

### 5. Test plan claims "485+ tests pass"
- **Verified**: Baseline is 485 passed / 15 failed (not 485+ passing as implied). The 15 failures are pre-existing.
- **Impact**: None for implementation, but the acceptance criterion should read "485 tests pass, 15 pre-existing failures unchanged" to be precise.

### 6. `server.py` `lifespan` log message should match spec exactly
- **Spec §4.3**: `"INFO: NexusAgent Server v0.1.0 starting..."`
- **Current** (Line 28): `"Starting NexusAgent Backend..."`
- **Missing**: The plan should explicitly state that the existing log message on line 28 is being replaced. It's a minor rename but a direct claim of the spec.

---

## Feasibility Verdict

| Area | Risk | Notes |
|------|------|-------|
| `/version` endpoint | **Low** | Trivial FastAPI addition |
| `/health` enhancement | **Low** | Add 1 line to existing handler |
| `--reload` flag | **Low** | `uvicorn.run(reload=...)` directly supported |
| `config.py` `reload` field | **Low** | Pydantic model add 1 field |
| SDK `health_check()` | **Low** | Add keys to existing dict return |
| Docker Compose watch | **Low** | Feature available in v5.1.4 |
| `VERSION` file | **Low** | Simple file creation |
| TUI preflight | **Medium** | Must use async HTTP (`httpx`), not `urllib`; needs careful integration into `_ws_loop()` without breaking existing retry logic |
| CLI preflight | **Medium** | Sync/async boundary in Click; must not break `--version` or `submit` |
| Tests | **Low** | Standard pytest patterns; no exotic fixtures needed |

---

## Recommendations Before Implementation

1. **Resolve the version constants architecture** — pick exactly one source of truth. Recommended: read from `pyproject.toml` via `importlib.metadata` at runtime, eliminating all hardcoded copies.

2. **Fix the TUI preflight** — use `httpx.AsyncClient` instead of `urllib.request`.

3. **Don't break `--version`** — keep `@click.version_option` for `nexus --version` (local only) and add a separate `--check-server` flag for the server-aware variant.

4. **Add a version-sync test** — assert `VERSION` file == `pyproject.toml` version == `server.VERSION` == `sdk.SERVER_VERSION`.

5. **Clarify the `workers` field** — either remove it from `/version` or derive from `settings.server.worker_threads`.

6. **Add `preflight()` to `submit` command** — the plan only mentions `run` and `--version`, but `submit` also connects to the server.

---

## Conclusion

The spec and plan are **ready for implementation with minor corrections**. The core design is sound, all file paths are correct, and all proposed changes are technically feasible. The issues identified are primarily around version-constant duplication, async/sync boundaries in the TUI and CLI, and one misleading field in the `/version` response. None require architectural changes — all are fixable at the task level.
