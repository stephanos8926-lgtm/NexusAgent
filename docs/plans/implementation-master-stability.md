# Implementation Specification & Micro-Steps: Master Stability and Observability Hardening

> **Created:** 2026-08-05
> **Author:** NEXUS MISSION CONTROL ⚡

---

## 1. Specification & ADR

### Context
1. **`/metrics` Route:** During Phase 10 (Observability & Reliability), a `/metrics` route was added to return a JSON representation of internal metrics. It was implemented with API-key dependencies (`verify_api_key`). However, the architectural specification requires `/metrics` to be public, and the integration test `test_metrics_endpoint` in `tests/test_observability.py` relies on this endpoint being public (making a request without authorization headers).
2. **Tool Registry Tests:** The tool registry is a shared singleton in memory across all tests. Some tests clear `registry` completely (`_pending`, `_snapshots`, etc.). `tests/tools/test_spawn_subagent.py` requires `spawn_subagent` to be registered. Its existing fixture only reloaded `nexusagent.tools.register_all` if `registry._pending` was completely empty. If `registry._pending` was partially populated (by other test artifacts) but did not contain `spawn_subagent`, or if the registry was not frozen afterwards, `spawn_subagent` would be missing from `registry.current`.

### Proposed Changes
- **`src/nexusagent/server/routes.py`:** Remove `dependencies=[Depends(verify_api_key)]` from the `@app.get("/metrics")` decorator.
- **`tests/tools/test_spawn_subagent.py`:** Change the `ensure_registry_populated` fixture to explicitly check if `"spawn_subagent" not in registry.current`. If so, reload `nexusagent.tools.register_all` and invoke `registry.freeze()`.

---

## 2. Micro-Steps Implementation Plan

### Step 2.1: Expose `/metrics` Publicly
- **Target File:** `src/nexusagent/server/routes.py`
- **Action:** Locate `@app.get("/metrics", dependencies=[Depends(verify_api_key)])` (around line 170).
- **Change:** Remove the `dependencies` parameter so it becomes `@app.get("/metrics")`.

### Step 2.2: Harden Test Fixture in `test_spawn_subagent.py`
- **Target File:** `tests/tools/test_spawn_subagent.py`
- **Action:** Locate the `ensure_registry_populated` fixture (around line 12).
- **Change:**
  - Change `if not registry._pending:` to `if "spawn_subagent" not in registry.current:`.
  - Inside the block, after reloading, add `registry.freeze()`.

### Step 2.3: Verify Specifically
- **Action:** Run `pytest tests/test_observability.py` and `pytest tests/tools/test_spawn_subagent.py`.

### Step 2.4: Run All Tests
- **Action:** Run the complete NATS-isolated suite to guarantee zero regressions.
