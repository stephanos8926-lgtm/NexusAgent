# NexusAgent Codebase Review — 2026-06-22

**Reviewer:** LLxprt Code (AI)  
**Date:** 2026-06-22  
**Commit at review:** ad49cbc  
**Score:** 6.8/10

## Executive Summary

NexusAgent has an unusually well-documented architecture (AGENTS.md, CODEBASE_MAP.md, SEMANTIC_INDEX.md, ADRs 0001-0008, Specs 001-006) and a layered design — LangGraph core + NATS bus + FastAPI/TUI/Gradio frontends + hybrid file+vector memory — that is solid. However, implementation quality and operational hygiene lag behind the architecture: debug prints leak API keys to stdout, a "local-dev" heuristic can silently disable authentication in production, `F821` / `B904` static bugs ship, and there is no CI pipeline to catch regressions. The architecture does not need a rewrite; it needs finishing.

## Baseline Metrics

| Metric | Value |
|---|---|
| Source LOC (`src/nexusagent/`) | 21,704 |
| Test files (`tests/`) | 65 |
| Ruff errors | 164 (120 auto-fixable) |
| Pre-existing test failures (documented) | 11 |
| Largest file | `tools/register_all.py` (1213 L) |
| Files >800 lines | 1 (`register_all.py`) |
| Files >600 lines | 3 (above + `dream.py`, `memory_files.py`) |
| TODO/FIXME markers | 5 |

## Ruff Error Breakdown

| Rule | Count | Severity | Notes |
|---|---|---|---|
| I001 import sort | 44 | Cosmetic | `--fix`able |
| F401 unused import | 44 | Cosmetic | `--fix`able |
| W293 whitespace | 7 | Cosmetic | `--fix`able |
| E402 import order | 5 | Cosmetic | |
| **F821 undefined name** | **2** | **Runtime bug** | See #3 below |
| F811 redefinition | 3 | Shadow bug risk | |
| F841 unused local | 3 | Dead code | |
| **B904 raise-without-from** | 2 | **Real bug** | Loses traceback |
| N801/N806 naming | 2 | Cosmetic | |

---

## Prioritized Action Items

### Priority 1 —  Security: Remove debug prints leaking API keys

**File:** `src/nexusagent/server/websocket.py:42, 52, 77`  
**Impact:** HIGH · **Effort:** 1 minute  

Three `print(..., flush=True)` statements dump `effective_key` (the API key), the full request headers, and the origin to stdout. These end up in Docker/systemd logs and any aggregator attached.

```python
# Lines to delete or gate behind `if DEBUG:`:
print(f"DEBUG headers: {dict(websocket.headers)}", flush=True)  # :42
print(f"DEBUG effective_key: '{effective_key}'", flush=True)    # :52
print(f"DEBUG WS origin: '{origin}', allowed={_WS_ALLOWED_ORIGINS}")  # :77
```

### Priority 2 —  Security: Gate the local-dev auth bypass

**File:** `src/nexusagent/server/websocket.py:56-66`  
**Impact:** HIGH · **Effort:** 30 minutes (design discussion needed)  

When the auth keystore file is missing, the server silently falls through to a "local-dev" mode that accepts any connection without authentication. A production operator who misconfigures the keystore path silently loses all auth.

**Proposed fix:** gate the fallback behind an explicit env var:

```python
if not effective_key:
    if os.getenv("NEXUS_ALLOW_INSECURE_LOCAL", "").lower() == "true":
        logger.warning("NEXUS_ALLOW_INSECURE_LOCAL=true — accepting connection without API key")
        effective_key = "local-dev"
    else:
        await websocket.close(code=4001, reason="Missing API key")
        return
```

**Confirm with user before implementing.**

### Priority 3 —  Bug: `F821` — `Content` annotation undefined

**File:** `src/nexusagent/widgets/messages/assistant.py:69`  
**Impact:** MEDIUM · **Effort:** 5 minutes  

`render(self) -> Content` uses `Content` as a return annotation but `Content` is never imported at module scope — only lazily inside the method body. Under PEP 563 (`from __future__ import annotations`) this is deferred, but Python 3.14+ will drop deferral, and today `get_type_hints()` will raise.

**Fix:** either import `Content` under `TYPE_CHECKING` or change the annotation to a string:

```python
def render(self) -> "Content":
    ...
```

### Priority 4 —  Refactor: Split `tools/register_all.py` (1213 L)

**File:** `src/nexusagent/tools/register_all.py`  
**Impact:** MEDIUM · **Effort:** 2 hours  

Violates the project's own <800-line guideline. The tool-spec tuple list already lives in `tool_specs.py`; the MCP plugin loader and dynamic-tool helpers should be split to their own modules (`mcp_loader.py`, `dynamic_tools.py`).

### Priority 5 —  Ops: Diagnose hanging pytest

**Impact:** HIGH · **Effort:** 1 hour diagnosis  

With `pytest tests/` the suite produces no output and is killed by timeout at 60/180/300 seconds in this environment. AGENTS.md says it takes ~100s. Likely cause: NATS/bus tests try to connect to a nonexistent broker and block on `asyncio.open_connection`. 

**Fix path:**
1. Install `pytest-timeout`: `pip install pytest-timeout`
2. Run `pytest tests/ -x --timeout=30 --tb=short` to find the hanging test.
3. Add `@pytest.mark.skipif(not nats_available, reason="needs nats")` to NATS tests, or stub the bus with a fake.
4. Verify: `pytest tests/ -q` must finish in <120s.

### Priority 6 —  Chore: Run `ruff check --fix`

**Impact:** LOW · **Effort:** 5 minutes  

Eliminates 120/164 errors in one pass (I001, F401, W293). Safe and automated.

```bash
cd /home/sysop/Workspaces/NexusAgent
python3 -m ruff check src/ --fix
python3 -m ruff format src/  # optional
```

Then manually resolve the remaining 44 issues (F811, F841, F821, B904, N801).

### Priority 7 —  Ops: Add minimal CI

**Impact:** HIGH (long-term) · **Effort:** 1 day  

No GitHub Actions. A minimal `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -e ".[dev]"
      - run: ruff check src/ tests/
      - run: pytest tests/ -q --tb=short
```

### Priority 8 —  Bug: Fix `B904` raise-without-from

**File(s):** 2 locations flagged by ruff (run `ruff check src/ --select B904` to find)  
**Impact:** LOW · **Effort:** 10 minutes  

When re-raising inside an `except`, use `raise ... from err` or `raise ... from None` to preserve (or explicitly suppress) the original traceback. Without this, debugging auth/memory failures means tracing blind.

---

## Additional Findings

### Code quality
- `memory/dream.py` (848 L), `memory/index/index.py` (716 L), `memory/memory_files.py` (638 L) — borderline but acceptable.
- `src/nexusagent/infrastructure/bus.py` (500 L) — acceptable single-responsibility size.
- 3 `F811` redefinitions — check for `if TYPE_CHECKING` vs runtime imports of the same name. Likely a compat shim collision.

### Memory system
- Hybrid 4-layer architecture (FileMemory → Index → HybridMemoryManager → CompactionPipeline/DreamCycle) is documented in AGENTS.md and appears faithfully implemented.
- Dream cycle `fcntl.flock` fix mentioned in AGENTS.md is still relevant — verify under concurrent writes.

### Security (other)
- **No TLS on WebSocket or FastAPI** — AGENTS.md flags this as critical and unfixed.
- **API key in query parameter** (`?token=` in `websocket.py:50`) — logs in access logs. Move to a header.
- **`refine_node` silently approves plan on failure** (`core/graph.py:125-127` per AGENTS.md) — verify still present.
- **Sync SQLite in async** (`memory/index/index.py`) — blocks the event loop. Documented but unfixed.

### Documentation
- AGENTS.md inventory lists `test_memory_compaction.py` but the file is `test_compaction.py`. Stale.
- No `CONTRIBUTING.md` or onboarding doc — worth splitting off from AGENTS.md.
- `CHANGELOG.md` exists but its freshness should be verified against commit volume.

---

## Recommended Execution Order

| Step | Task | Effort | Risk |
|---|---|---|---|
| 1 | Delete debug prints in `websocket.py` | 1 min | None |
| 2 | Fix `F821` in `assistant.py` | 5 min | None |
| 3 | `ruff check --fix` | 5 min | None |
| 4 | Fix `B904` raise-without-from | 10 min | None |
| 5 | Diagnose + fix hanging pytest | 1 hour | Low |
| 6 | Gate local-dev auth bypass (confirm design first) | 30 min | Medium |
| 7 | Split `register_all.py` | 2 hours | Medium |
| 8 | Add GitHub Actions CI | 1 day | Low |
| 9 | TLS on FastAPI/WebSocket | 2-4 hours | Low |
| 10 | Move `?token=` to header | 30 min | Low (needs SDK coordination) |

Steps 1-4 can be done in a single commit. Step 5 needs diagnosis first. Step 6 needs a design decision. Steps 7-10 are longer-running.

---

*Report generated by reviewing ruff output, pytest behavior, git log, and spot-checks of key modules (graph.py, websocket.py, assistant.py, register_all.py).*
