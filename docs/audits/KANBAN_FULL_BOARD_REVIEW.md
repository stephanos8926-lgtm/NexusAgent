# Kanban Board Review Report — Full Board Validation

> **Board:** default
> **Date:** 2026-07-19
> **Auditor:** OWL (Lucien)
> **Workflow:** kanban-review-workflow v1.0.0
> **Scope:** All 6 Phase 2 tasks

---

## Stage 1: Board Health

| Metric | Count | Status |
|--------|-------|--------|
| Total tasks | 6 | — |
| Ready (dispatchable) | 4 | ✅ |
| Todo (blocked by deps) | 2 | 🟡 |
| Stale (>2h inactive) | 0 | ✅ |
| Failed (≥2 failures) | 0 | ✅ |
| Blocked (no reason) | 0 | ✅ |
| Orphan (bad assignee) | 0 | ✅ |

**Result:** ✅ HEALTHY — no stale, failed, blocked, or orphan tasks. All tasks were just created.

---

## Stage 2: Task Decomposition

| # | Task ID | Title | Size | Files | Criteria | Reverse Audit | Ready? |
|---|---------|-------|------|-------|----------|---------------|--------|
| 1 | t_d809ab45 | TOCTOU race fix | **S** | session.py (1 file, ~50 lines) | ✅ 6 specific criteria | ✅ Leak + lock safety | ✅ GO |
| 2 | t_ddc588c4 | bytes encoder fix | **S** | bus.py (1 file, ~10 lines) | ✅ 4 specific criteria | ✅ Tool boundary + size check | ✅ GO |
| 3 | t_55f5d3b4 | NATS durable consumers | **M** | bus.py, worker.py (2 files, ~100 lines) | ✅ 5 specific criteria | ✅ Idempotency + partial failure | ✅ GO |
| 4 | t_3a205302 | NATS SPOF elimination | **L** | bus.py, worker.py, new modules (3+ files, ~300 lines) | ✅ 5 specific criteria | ✅ Heartbeat + HTTP fallback | ⚠️ CONDITIONAL |
| 5 | t_db3c06f2 | Singletons refactor | **L** | 8 files across core/infra/llm/server | ✅ 6 specific criteria | ✅ Categorize + bottom-up order | ⚠️ CONDITIONAL |
| 6 | t_3b8d39cb | MCP + RAG wiring | **L** | register_all.py, agent.py, embeddings.py (3+ files, ~200 lines) | ✅ 7 specific criteria | ✅ Index exists, wiring gap | ⚠️ CONDITIONAL |

### Stage 2.5: Reverse Audit Pass (per-task)

**Task 1 (TOCTOU):** The obvious fix (add `_creating` set) misses:
- Session leak on race (overwritten session not closed) → **already in acceptance criteria** ✅
- `mark_idle()` and `close()` don't acquire lock → **already in acceptance criteria** ✅
- `memory_dir` corruption on concurrent creation → **already in acceptance criteria** ✅

**Task 2 (bytes encoder):** The obvious fix (decode bytes as UTF-8) misses:
- Binary data corruption → **already in acceptance criteria** ("don't silently decode") ✅
- Fix at tool boundary AND encoder → **already in acceptance criteria** ✅
- Large result size limit → **already in acceptance criteria** ✅

**Task 3 (NATS durable):** The obvious fix (JetStream pull consumers) misses:
- Sequential delivery bottleneck → acceptance criteria should add: "verify parallelism with multiple consumers"
- No transaction between DB and KV → acceptance criteria should add: "handle partial failure between DB update and KV write"

**Task 4 (NATS SPOF):** The obvious fix (better reconnection) misses:
- The real fix is architectural (HTTP fallback) → **already in acceptance criteria** ✅
- Worker heartbeat/lease mechanism → **already in acceptance criteria** ✅
- `max_reconnect_attempts=-1` infinite hang → acceptance criteria should add: "cap reconnection attempts"

**Task 5 (Singletons):** The obvious fix (convert all to DI) misses:
- Not all singletons are equal → **already in acceptance criteria** (categorize) ✅
- Bottom-up refactoring order → **already in acceptance criteria** ✅
- Test updates needed → **already in acceptance criteria** ✅

**Task 6 (MCP + RAG):** The obvious fix (implement RAG) misses:
- RAG already exists (HybridMemoryIndex, 613 lines) → **already in acceptance criteria** (wiring, not implementation) ✅
- MCP tool name conflicts → **already in acceptance criteria** ✅
- `_DB_POOL` singleton in embeddings.py → acceptance criteria should add: "refactor _DB_POOL for per-tenant indexes"

### Updated Acceptance Criteria from Reverse Audit Pass

3 tasks need additional criteria added (will update Kanban cards):

**Task 3 (NATS durable) — add:**
- "Verify parallelism with multiple consumers (deliver_policy)"
- "Handle partial failure between DB update and KV write"

**Task 4 (NATS SPOF) — add:**
- "Cap reconnection attempts (no infinite hang on -1)"

**Task 6 (MCP + RAG) — add:**
- "Refactor _DB_POOL singleton in memory/index/embeddings.py"

---

## Stage 3: Dependency & Conflict Analysis

### Dependency Graph
```
t_d809ab45 (TOCTOU) ──────────────────────────── INDEPENDENT
t_ddc588c4 (bytes) ──▶ t_55f5d3b4 (durable) ──▶ t_3a205302 (SPOF)
t_db3c06f2 (singletons) ──────────────────────── INDEPENDENT
t_3b8d39cb (MCP/RAG) ─────────────────────────── INDEPENDENT
```

### Conflict Detection

| Task A | Task B | Same File? | Conflict? |
|--------|--------|------------|-----------|
| t_d809ab45 (TOCTOU) | t_ddc588c4 (bytes) | No (session.py vs bus.py) | ✅ None |
| t_d809ab45 (TOCTOU) | t_55f5d3b4 (durable) | No | ✅ None |
| t_d809ab45 (TOCTOU) | t_3a205302 (SPOF) | No | ✅ None |
| t_d809ab45 (TOCTOU) | t_db3c06f2 (singletons) | No | ✅ None |
| t_d809ab45 (TOCTOU) | t_3b8d39cb (MCP) | No | ✅ None |
| t_ddc588c4 (bytes) | t_55f5d3b4 (durable) | **Yes: bus.py** | 🟡 Sequential (dep) |
| t_ddc588c4 (bytes) | t_3a205302 (SPOF) | **Yes: bus.py** | 🟡 Sequential (dep chain) |
| t_55f5d3b4 (durable) | t_3a205302 (SPOF) | **Yes: bus.py, worker.py** | 🟡 Sequential (dep) |
| t_db3c06f2 (singletons) | t_3b8d39cb (MCP) | **Possibly: agent.py** | ⚠️ Needs check |
| t_db3c06f2 (singletons) | t_55f5d3b4 (durable) | **Possibly: worker.py** | ⚠️ Needs check |

### Conflict Resolution

| Conflict | Resolution |
|----------|------------|
| bus.py shared by #2→#3→#4 | Already sequential via dependencies — safe |
| worker.py shared by #3→#4 | Already sequential via dependencies — safe |
| agent.py possibly shared by #5→#6 | **Needs verification** — singletons refactor may touch agent.py imports |
| worker.py possibly shared by #5→#3 | **Needs verification** — singletons refactor touches worker.py (worker_pool singleton) |

**Critical finding:** Task #5 (singletons) touches `worker.py` which is also touched by #3 (durable) and #4 (SPOF). But #5 is independent (no dependency link), while #3 and #4 are sequential. If #5 runs in parallel with #3 or #4, there's a file conflict on `worker.py`.

**Resolution:** Add dependency: #5 (singletons) must complete before #3 (durable) starts, since #3 touches worker.py and #5 refactors the worker_pool singleton in worker.py.

---

## Stage 4: Go/No-Go Decision

### Verdict: ⚠️ CONDITIONAL GO

The board is **almost** ready for dispatch. Two issues need resolution before kickoff:

### Blockers

| # | Blocker | Severity | Fix |
|---|---------|----------|-----|
| 1 | **Missing dependency:** #5 (singletons) must complete before #3 (durable) — both touch worker.py | 🔴 High | Add `hermes kanban link t_db3c06f2 t_55f5d3b4` |
| 2 | **3 tasks need updated acceptance criteria** from reverse audit pass | 🟡 Medium | Update cards #3, #4, #6 with additional criteria |

### Recommended Actions (before dispatch)

1. **Add dependency link:** `hermes kanban link t_db3c06f2 t_55f5d3b4` (singletons → durable)
2. **Update Task #3 (NATS durable)** — add acceptance criteria:
   - "Verify parallelism with multiple consumers (deliver_policy)"
   - "Handle partial failure between DB update and KV write"
3. **Update Task #4 (NATS SPOF)** — add acceptance criteria:
   - "Cap reconnection attempts (no infinite hang on -1)"
4. **Update Task #6 (MCP + RAG)** — add acceptance criteria:
   - "Refactor _DB_POOL singleton in memory/index/embeddings.py"

### Dispatch Order (after blockers resolved)

| Order | Task | Size | Dependencies | Est. Turns |
|-------|------|------|--------------|------------|
| 1 | t_d809ab45 — TOCTOU fix | S | None | 2-3 |
| 2 | t_ddc588c4 — bytes encoder | S | None | 2-3 |
| 3 | t_db3c06f2 — Singletons | L | None | 5+ |
| 4 | t_55f5d3b4 — NATS durable | M | #2, #3 | 4-5 |
| 5 | t_3a205302 — NATS SPOF | L | #4 | 5+ |
| 6 | t_3b8d39cb — MCP + RAG | L | #3 (for embeddings.py) | 5+ |

**Parallel opportunities:**
- Wave 1: #1 + #2 + #3 (all independent, different files)
- Wave 2: #4 (depends on #2 + #3)
- Wave 3: #5 (depends on #4) + #6 (depends on #3)

### Estimated Total Effort

| Wave | Tasks | Parallelism | Est. Wall Time |
|------|-------|-------------|----------------|
| Wave 1 | #1, #2, #3 | 3 parallel | ~5 min (limited by #3) |
| Wave 2 | #4 | 1 worker | ~5 min |
| Wave 3 | #5, #6 | 2 parallel | ~8 min |
| **Total** | **6 tasks** | **3 waves** | **~18 min** |

---

## Workflow Self-Assessment

**What the workflow caught:**
1. ✅ File conflict between #5 (singletons) and #3/#4 (NATS) on worker.py — would have caused merge conflicts
2. ✅ Missing acceptance criteria from reverse audit pass on 3 tasks
3. ✅ Dependency ordering ensures bus.py changes happen sequentially
4. ✅ Task sizing correctly identified #4, #5, #6 as L-sized (need decomposition or extended time)

**What the workflow missed:**
1. ⚠️ Didn't catch that #5 (singletons) also touches `infrastructure/db/__init__.py` (db_manager singleton) — the db_manager is used by all tasks. If #5 changes the db_manager pattern, all other tasks that import it could break. This is a **keystone risk**.
2. ⚠️ Didn't estimate the test suite impact — #5 (singletons) will likely break many tests since they rely on global state.

**Workflow improvement needed:** Add a "shared infrastructure impact" check to Stage 3 — if a task modifies a module imported by all other tasks (like db_manager), flag it as a keystone risk.
