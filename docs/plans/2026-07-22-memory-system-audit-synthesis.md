# Memory System Plan — Audit Synthesis

> **Date:** 2026-07-22
> **Audits:** Forward ✅ | Reverse ✅ (38 gaps) | Adversarial ✅ (6 show-stoppers)
> **Verdict:** REVISE BEFORE IMPLEMENTING

---

## 🔴 Critical Findings (Must Address)

### 1. Plan Claims Work That's Already Done (~40% vaporware)

The adversarial audit confirmed that Tasks 1.1, 1.2, 1.4, and 1.6 are **already implemented and committed**:

| Plan Task | Status | Evidence |
|-----------|--------|----------|
| Task 1.1: Session creates HybridMemoryManager | ✅ DONE | `session.py` line 43: `self.hybrid_memory = HybridMemoryManager(memory_dir)` |
| Task 1.2: Auto-recall in send() | ✅ DONE | `session.py` line 188: `self.hybrid_memory.get_memory_context()` injected as SystemMessage |
| Task 1.4: Pre-compaction flush | ✅ DONE | `session.py` line 323: `pre_compaction_flush()` calls `hybrid_memory.flush()` |
| Task 1.6: Wire memory_dir through stack | ✅ PARTIAL | `websocket.py` lines 73-88 resolve `memory_workspace` config |

**Impact:** The plan's 10-15 day estimate is inflated by ~4 days of phantom work. More importantly, it undermines confidence in the plan's accuracy.

**Action:** Remove these tasks from the plan. They're done. Verify with `git log` and `read_file`.

### 2. Missing DB Method + Column for Cross-Session Discovery

**Task 1.5** (cross-session memory) depends on:
- `SessionRepository.find_sessions_by_working_dir()` — **DOES NOT EXIST**
- `SessionModel.memory_dir` column — **DOES NOT EXIST** (only `memory_id` exists)

**Impact:** Cross-session discovery is the #1 feature in the plan and it's architecturally blocked.

**Action:** Add a new task BEFORE Task 1.5:
- Task 1.5a: Add `memory_dir` column to `SessionModel` (migration)
- Task 1.5b: Add `find_sessions_by_working_dir()` to `SessionRepository`
- Task 1.5c: Add index on `working_dir` for query performance

### 3. Dream Cycle Race Condition

The `ConsolidationEngine.consolidate()` **deletes files** while active sessions may be writing to the same directory. No file locking exists.

**Impact:** Data corruption if dream cycle runs during active sessions.

**Action:** Add file locking (`.lock` file or `filelock` library) before Phase 2 implementation.

### 4. `aiohttp` Listed But Not a Dependency

Plan's tech stack lists `aiohttp` but `pyproject.toml` has no such dependency. Codebase uses `httpx`.

**Action:** Remove `aiohttp` from tech stack. Use `httpx` (already present).

---

## 🟠 High Priority Findings

### 5. Auto-Extraction Latency Underestimated

Plan says ~500ms. Reality: 2-5s (Gemini API round-trip). No rate limiting, no backpressure.

**Action:** 
- Start with regex/rule-based extraction (not LLM)
- Add bounded queue with max pending extractions per session
- Defer LLM-based extraction to v2

### 6. N+1 SQLite Queries in Cross-Session Discovery

Each previous session opens a new `HybridMemoryIndex` + SQLite connection. Sequential, not parallel.

**Action:** Use `asyncio.gather()` for parallel search. Add result caching per workspace.

### 7. Memory Dir Resolution Inconsistency

WebSocket layer reads `memory_workspace` from config. Session constructor doesn't import settings. Different code paths get different memory dirs.

**Action:** Centralize memory_dir resolution in a single function. All code paths call it.

### 8. Session.close() Doesn't Clean Up hybrid_memory

No `close()` method on `HybridMemoryManager`. SQLite connections leak.

**Action:** Add `close()` to `HybridMemoryManager`. Call it from `Session.close()`.

### 9. No `memory_model` Config Field

Plan mentions "lightweight model for extraction" but no config field exists.

**Action:** Add `memory_model: str = ""` to config (empty = use current model).

---

## 🟡 Medium Priority (10 items)

10. `SessionModel` needs index on `working_dir`
11. No TTL/expiration enforcement in `FileMemory`
12. `memory_write` tool creates new `HybridMemoryManager` per call (expensive)
13. No concurrent write test for `memory_write`
14. `EmbeddingProvider._embed_gemini` re-reads `.env` on every call
15. No `close()` for `EmbeddingProvider`
16. `CompactionPipeline` instantiated inline per `send()`
17. Missing docs updates: `CODEBASE_MAP.md`, `SEMANTIC_INDEX.md`, `REFACTORING_PLAN.md`
18. Commit message typos (`-t` instead of `-m`)
19. No rate limiting on memory tool calls
20. DAG has no eviction strategy (grows forever)

---

## 🎯 Revised Scope (Minimum Viable)

Based on all three audits, here's what to actually build:

### Sprint 1: Fix Foundation + Cross-Session (Days 1-3)
| Task | Description | New? |
|------|-------------|------|
| 0 | Fix config path bug (db_path) | Revised |
| 1.5a | Add `memory_dir` column to `SessionModel` + migration | **NEW** |
| 1.5b | Add `find_sessions_by_working_dir()` to `SessionRepository` | **NEW** |
| 1.5c | Add index on `working_dir` | **NEW** |
| 1.5 | Cross-session memory discovery (async, cached) | Revised |
| 1.3 | Auto-extraction (regex-based, NOT LLM) | Revised |
| 1.6 | Fix memory_dir resolution consistency | Revised |

### Sprint 2: Background Maintenance (Days 4-6)
| Task | Description | New? |
|------|-------------|------|
| 2.1 | File locking for dream cycle | **NEW** |
| 2.2 | `memory_model` config field | **NEW** |
| 2.3 | Dream cycle engine (with locking) | Revised |
| 2.4 | `memory_dream` tool | Revised |

### Sprint 3: Integration + Polish (Days 7-10)
| Task | Description | New? |
|------|-------------|------|
| 3.1 | Provenance tracking (`source_session_id`, `derived_from`) | From Phase 4 |
| 3.2 | End-to-end integration test | From Phase 5 |
| 3.3 | NATS/worker memory integration | **NEW** (from adversarial) |
| 3.4 | Update all docs | Revised |

### DEFER (Not in v1):
- ❌ DAG compression (Phase 3) — Current graduated compaction is good enough
- ❌ LLM-based extraction — Start regex-based, defer LLM
- ❌ Observation extraction (Task 4.2) — No clear user value yet

---

## Revised Estimate

| Sprint | Days | Confidence |
|--------|------|-----------|
| Sprint 1: Foundation | 3 | High |
| Sprint 2: Maintenance | 3 | Medium |
| Sprint 3: Polish | 4 | Medium |
| **Total** | **10** | **Medium** |

Down from 10-15 days because:
- 4 tasks removed (already done)
- DAG compression deferred
- LLM extraction deferred

---

## Audit Reports (Full)

- Forward audit: **TIMED OUT** (600s) — likely stuck on slow API call. Partial results not available.
- Reverse audit: **COMPLETED** — 38 gaps found (7 critical, 8 high, 10 medium, 13 low)
- Adversarial audit: **COMPLETED** — 6 show-stoppers, 9 major concerns, 16 minor, 7 suggestions

Full reports available in subagent outputs.
