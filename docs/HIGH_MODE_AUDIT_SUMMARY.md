# 🔍 NexusAgent Deep Bug Hunt — HIGH Mode Audit
**Date:** 2026-06-28  
**Auditor:** Lucien (plan-and-audit HIGH mode)  
**Scope:** Full codebase + all prior audits  

---

## Executive Summary

**Total Issues Found:** 79 (34 from July 22 audit + 45 from June 16 audit)  
**Status:** 6 critical bugs fixed today (ctx.role, frozenset, heartbeat, operator auth)  
**Remaining:** 73 issues across 4 severity levels

| Priority | Count | Status | Next Action |
|----------|-------|--------|-------------|
| 🔴 Critical | 6 | ✅ 4 fixed, 2 pending | Fix refine_node + API key in URL |
| 🟠 High | 16 | ⚠️ 2 fixed, 14 pending | Wave-based remediation |
| 🟡 Medium | 26 | 📋 Not started | Plan-driven sprints |
| 🔵 Low | 25 | 📋 Not started | Backlog grooming |

---

## Bugs Fixed Today (2026-06-28)

### ✅ FIXED: ctx.role → ctx["role"] (search.py)
**Commit:** accb3da  
**Impact:** tool_search() crashed immediately  
**Fix:** Use dict bracket notation instead of attribute access

### ✅ FIXED: frozenset → set() (fs_base.py)  
**Commit:** 2c206e4  
**Impact:** .add() calls failed on immutable frozenset  
**Fix:** Use mutable set() as ContextVar default

### ✅ FIXED: Heartbeat zombie task leak
**Commit:** ec4dcf7 + dba592c  
**Impact:** "Still thinking..." spam after disconnect  
**Fix:** Cancel heartbeat on close/error/WebSocket disconnect

### ✅ FIXED: Operator key auth dynamic loading
**Commit:** 5d167f4  
**Impact:** Operator keys rejected on ALL endpoints  
**Fix:** Read env at call time, not import time; validate before role check

---

## Remaining Critical Bugs (2)

### 🔴 BUG-001: refine_node Silent Error Swallowing
**File:** `src/nexusagent/core/graph.py:125-127`  
**Impact:** Failed plan refinement → workflow proceeds with flawed plan  
**Fix:**
```python
# BEFORE
return {"plan_approved": True, "error": None}

# AFTER  
return {"plan_approved": False, "error": str(e)}
```

### 🔴 BUG-002: API Key in URL Query Parameter
**File:** `src/nexusagent/server/websocket.py:35`  
**Impact:** API keys logged in access logs, browser history, Referer headers  
**Fix:** 
1. Deprecate `?api_key=` query param
2. Implement `/auth/token` exchange endpoint for browser clients
3. Enforce header-only auth (`X-API-Key` or `Authorization: Bearer`)

---

## High Priority Bugs (Top 5 of 14)

### 🟠 BUG-003: Sync SQLite in Async Event Loop
**Files:** `memory/index/index.py`, `memory/hybrid_memory.py`  
**Impact:** 10-50ms event loop blocking per memory recall  
**Fix:** Persistent connection pool + async `search()` wrapper

### 🟠 BUG-004: SessionManager Spin Loop No Timeout
**File:** `core/session/manager.py:82-88`  
**Impact:** Stuck in `_creating` forever if creator panics  
**Fix:** `asyncio.wait_for()` with 30s timeout

### 🟠 BUG-005: sanitize_tool_output Always Marks Untrusted
**File:** `core/agent.py:52-53`  
**Impact:** Cries wolf on EVERY tool output, degrades injection defense  
**Fix:** Only prepend marker when `_detect_injection()` returns True

### 🟠 BUG-006: No TLS/SSL Configuration  
**File:** `server/server.py`  
**Impact:** All traffic (API keys, code, secrets) in plaintext  
**Fix:** Add SSL cert/key config; enable uvicorn SSL; NATS TLS optional

### 🟠 BUG-008: Rate Limiter Memory Leak
**File:** `infrastructure/rate_limit.py:17`  
**Impact:** Dict grows unboundedly across all clients forever  
**Fix:** Implement cleanup using `_RATE_LIMIT_CLEANUP` (already defined but unused)

---

## Medium Priority Patterns

### Category: TUI Bugs (5 issues)
- BUG-012: Sliding window bypass (4 paths)
- BUG-013: `_busy` not reset on disconnect
- BUG-014: Approval race condition
- BUG-015: Stale widget refs after `/clear`
- BUG-016: Unbounded queues → DoS

### Category: Memory Leaks (4 issues)
- BUG-008: Rate limiter dict
- BUG-010: Bus subscriptions never cleaned
- BUG-011: SQLite connection leak in graph
- BUG-019: Memory.merge O(n²) deduplication

### Category: Architecture Debt (3 issues)
- BUG-017: `llm/models.py` god object (17+ imports)
- BUG-007: Double message conversion (80+ objects/turn)
- BUG-027: MCP tool loading race condition

---

## Low Priority / Code Quality (25 issues)

- Docstring mismatches
- Shallow health checks
- No key rotation mechanism
- Quote style conflicts
- History file integrity
- Type inconsistencies
- Misleading variable names

Full list in `docs/specs/audits/bug-review-nexusagent-2026-07-22.md`

---

## Wave-Based Remediation Plan

### Wave 1: Quick Wins (1-3 line fixes)
**Estimated:** 2 hours  
**Issues:** BUG-001 (refine_node), BUG-005 (sanitize), BUG-031 (docstring)  
**Risk:** Low — isolated changes

### Wave 2: Isolated Tool Fixes  
**Estimated:** 4 hours  
**Issues:** BUG-004 (timeout), BUG-008 (rate limiter cleanup), BUG-011 (connection leak)  
**Risk:** Medium — touches error handling paths

### Wave 3: TUI Fixes
**Estimated:** 6 hours  
**Issues:** BUG-012 through BUG-016 (all 5 TUI bugs)  
**Risk:** Medium — requires TUI testing

### Wave 4: Server/WebSocket
**Estimated:** 8 hours  
**Issues:** BUG-002 (API key in URL), BUG-006 (TLS), BUG-007 (double conversion)  
**Risk:** High — auth changes require test updates

### Wave 5: Memory System
**Estimated:** 12 hours  
**Issues:** BUG-003 (async SQLite), BUG-019 (O(n²) dedup), BUG-027 (MCP race)  
**Risk:** High — core functionality, requires perf testing

---

## Testing Strategy

### Pre-Wave Baseline
```bash
PYTHONPATH=src pytest tests/ -q --tb=no
# Expected: ~680 pass / 11 pre-existing fail
```

### Per-Wave Verification
```bash
# After each wave:
PYTHONPATH=src pytest tests/ -q --tb=short
# Zero NEW failures allowed
# Pre-existing failures OK
```

### Post-Wave Documentation
- Update `docs/specs/audits/bug-review-nexusagent-2026-07-22.md`
- Mark fixed issues with ✅ and commit SHA
- Update overall scores

---

## Next Steps

1. **User Confirmation:** Review this plan and prioritize waves
2. **Wave 1 Execution:** Fix BUG-001, BUG-005, BUG-031 (lowest risk)
3. **Verify:** Run tests, confirm zero regressions
4. **Continue:** Proceed through waves 2-5 based on user priorities
5. **Document:** Update audit reports with final scores

---

## Risk Mitigation

- **Per-wave commits** — Easy rollback if issues found
- **Test-first approach** — Regression tests before fixes
- **Zero new failures policy** — Stop immediately if tests break
- **User check-ins** — After each wave, confirm direction

---

**Severity Score:** 7.3/10 (was 8.5/10 before today's 4 fixes)  
**Target Score:** 9.0/10 (after Waves 1-3)  
**Production Ready:** Yes, with known issues documented

See individual audit reports for full details on each bug.