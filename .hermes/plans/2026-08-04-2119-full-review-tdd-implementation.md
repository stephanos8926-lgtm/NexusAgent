# Full-Review TDD Implementation Plan (rev 2 — post-audit)

## Goal
Implement fixes for all findings from the `full-review` architecture-first code review of the NexusAgent security/control/structure changes (commit 8a263d3), using strict Test-Driven Development methodology.

## Current Context
- **Base commit**: 8a263d3 (feat: security,control,structure)
- **Changed files**: 6 files (+1 new test file, +1 new module)
- **Review performed**: `full-review` skill (kadenn/full-review) — architecture-first, two-phase review
- **Audit status**: Forward audit complete, reverse audit pending

## Summary of Findings (Post-Forward Audit)

### Phase 1 — Architecture (Question 5)
| # | Finding | Severity |
|---|---------|----------|
| 5 | Session websocket loses origin diagnostic logging for ACCEPTED connections in `_authenticate_websocket()` helper | QUESTION |

### Phase 2 — Implementation Dimensions (Post-Audit Adjustments)
| Dimension | Finding | File | Severity | Audit Status |
|-----------|---------|------|----------|--------------|
| 2.1 Correctness | `_recv_with_timeout` catches all exceptions, loses error distinction | `websocket.py:34-40` | MEDIUM | ✅ CONFIRMED |
| 2.1 Correctness | Heartbeat interval hardcoded 15s (was 30s), no config/constant | `worker.py:221` | LOW | ✅ CONFIRMED |
| 2.1 Correctness | `_cancel_authorizer` attribute not initialized in `__init__` | `worker.py:243` | LOW | ✅ CONFIRMED |
| 2.2 Silent failures | `_health_loop` swallows reconnection exceptions at WARNING level | `worker.py:172` | LOW | ✅ CONFIRMED |
| 2.2 Silent failures | `_execute_bounded` returns error strings instead of structured errors | `pool.py:288,290,291` | MEDIUM (pre-existing) | ✅ CONFIRMED |
| 2.3 Dead code | Local `import math` inside `_compute_quality_score` | `memory_files.py:216` | NIT | ✅ CONFIRMED |
| 2.5 Types/invariants | `memory_utils.py` missing `__all__` exports | `memory_utils.py` (NEW) | LOW | ✅ CONFIRMED |
| 2.5 Types/invariants | `serialize_frontmatter` doesn't handle `None` body | `memory_utils.py:48` | LOW | ⚠️ PARTIAL |
| 2.8 Tests | No integration test for WebSocket idle timeout behavior | `test_websocket_timeouts.py` | MEDIUM | ✅ CONFIRMED |
| 2.11 Security | `resolve_short_lived_token` may log token parameter | `websocket.py:48-59` | QUESTION | ❌ NOT CONFIRMED — REMOVE |
| **NEW (audit)** | Bare `except Exception:` in `receive_messages()` | `websocket.py:149-151` | MEDIUM | ✅ CONFIRMED |
| **NEW (audit)** | Bare `except Exception:` in `events_websocket` callback | `websocket.py:290-294` | MEDIUM | ✅ CONFIRMED |
| **NEW (audit)** | Bare `except Exception:` in `pol_websocket` callback | `websocket.py:343-350` | MEDIUM | ✅ CONFIRMED |
| **NEW (audit)** | Bare `except Exception:` in `_heartbeat` | `worker.py:232-233` | LOW | ✅ CONFIRMED |
| **NEW (audit)** | String return "Max turns reached" in `_execute_bounded` | `pool.py:293` | LOW | ✅ CONFIRMED |
| **NEW (audit)** | Quality score not updated on file append | `memory_files.py:188` | LOW | ✅ CONFIRMED |

---

## Audit Summary

### Forward Audit: PASS
- 9 items ✅ PASS (confirmed, feasible)
- 2 items ⚠️ PARTIAL (partially confirmed)
- 1 item ❌ FAIL (issue doesn't exist — A.4 security logging)
- **Total plan items**: 12 original → 12 confirmed + 6 new from audit = 18 actionable

### Reverse Audit: PENDING
*Subagent still running — will incorporate when complete*

### Audit Findings Incorporated
- ✅ Removed A.4 from plan (no issue exists)
- ✅ Adjusted A.2 scope: origin logging for ACCEPTED connections, not "restoration"
- ✅ Added 6 new findings from forward audit (bare except handlers, string returns, quality score)
- ✅ Updated severity/priority based on audit evidence

---

## Proposed Approach
**TDD for each finding:**
1. Write a failing test that asserts the CORRECT behavior
2. Verify test fails against current (broken) code
3. Implement minimal fix
4. Verify test passes
5. Refactor if needed (keeping tests green)

**Execution order:** Group by file/module to minimize context switching.

---

## Step-by-Step Plan (rev 2)

### Phase A: WebSocket Module Fixes (src/nexusagent/server/websocket.py)

#### A.1 `_recv_with_timeout` exception handling (MEDIUM)
**Target**: `src/nexusagent/server/websocket.py:34-40`

**RED test**:
```python
# tests/test_websocket_timeouts.py
@pytest.mark.asyncio
async def test_recv_with_timeout_distinguishes_disconnect_from_error():
    """WebSocketDisconnect should return __DISCONNECT__, other errors logged."""
    class DisconnectWS:
        async def receive_text(self):
            raise WebSocketDisconnect()
    
    class ErrorWS:
        async def receive_text(self):
            raise RuntimeError("unexpected error")
    
    # WebSocketDisconnect -> __DISCONNECT__
    result = await _recv_with_timeout(DisconnectWS(), timeout=0.05)
    assert result == "__DISCONNECT__"
    
    # Other errors -> __DISCONNECT__ but logged
    with caplog.at_level(logging.ERROR):
        result = await _recv_with_timeout(ErrorWS(), timeout=0.05)
        assert result == "__DISCONNECT__"
        assert "WebSocket receive error" in caplog.text
```

**GREEN fix**: Modify `_recv_with_timeout` to catch `WebSocketDisconnect` explicitly, log other exceptions.

---

#### A.2 Session websocket origin logging for ACCEPTED connections (Phase 1 Question 5)
**Target**: `src/nexusagent/server/websocket.py:97-100` (after `_authenticate_websocket()` call)

**RED test**:
```python
# tests/test_websocket.py
@pytest.mark.asyncio
async def test_session_websocket_logs_origin_on_accept():
    """session_websocket should log origin for accepted connections."""
    ws = MockWebSocket(origin="http://localhost:8000")
    with caplog.at_level(logging.INFO):
        await session_websocket(ws, "test-session")
        assert "WebSocket origin: http://localhost:8000" in caplog.text
```

**GREEN fix**: After `_authenticate_websocket()` call in `session_websocket`, add origin logging for accepted connections.

---

#### A.3 Bare `except Exception:` in `receive_messages()` (MEDIUM) — **NEW from audit**
**Target**: `src/nexusagent/server/websocket.py:149-151`

**RED test**:
```python
# tests/test_websocket.py
@pytest.mark.asyncio
async def test_receive_messages_handles_exception():
    """receive_messages should handle exceptions gracefully without bare except."""
    # Verify the bare except is replaced with specific exception handling
```

**GREEN fix**: Replace `except Exception:` with specific exception types or at minimum log the error.

---

#### A.4 Bare `except Exception:` in `events_websocket` callback (MEDIUM) — **NEW from audit**
**Target**: `src/nexusagent/server/websocket.py:290-294`

**RED test**: Similar pattern test

**GREEN fix**: Replace bare except with specific handling.

---

#### A.5 Bare `except Exception:` in `pol_websocket` callback (MEDIUM) — **NEW from audit**
**Target**: `src/nexusagent/server/websocket.py:343-350`

**RED test**: Similar pattern test

**GREEN fix**: Replace bare except with specific handling.

---

#### A.6 Integration test for WebSocket idle timeout (MEDIUM)
**Target**: `tests/test_websocket_timeouts.py` (new test)

**RED test**:
```python
@pytest.mark.asyncio
async def test_events_websocket_idle_timeout():
    """events_websocket should timeout after _WRAPPED_TIMEOUT of no events."""
    # Use short timeout for test
    # Verify asyncio.TimeoutError triggers clean close
```

**GREEN fix**: Ensure timeout logic works end-to-end (already implemented, just need test).

---

#### A.7 Security: `resolve_short_lived_token` — REMOVED from plan
**Reason**: Forward audit confirmed function does NOT log token parameter. No issue exists.

---

### Phase B: Worker Module Fixes (src/nexusagent/core/worker/worker.py)

#### B.1 Heartbeat interval constant (LOW)
**Target**: `src/nexusagent/core/worker/worker.py:221`

**RED test**:
```python
# tests/core/worker/test_worker.py
def test_heartbeat_interval_is_constant():
    """HEARTBEAT_INTERVAL should be a class constant, not hardcoded."""
    assert hasattr(NexusWorker, 'HEARTBEAT_INTERVAL')
    assert NexusWorker.HEARTBEAT_INTERVAL == 15
```

**GREEN fix**: Add `HEARTBEAT_INTERVAL = 15` class constant, use it in `_heartbeat`.

---

#### B.2 `_cancel_authorizer` initialization (LOW)
**Target**: `src/nexusagent/core/worker/worker.py:52-65` (`__init__`)

**RED test**:
```python
def test_cancel_authorizer_initialized_to_none():
    """_cancel_authorizer should be explicitly initialized to None."""
    worker = NexusWorker()
    assert hasattr(worker, '_cancel_authorizer')
    assert worker._cancel_authorizer is None
```

**GREEN fix**: Add `self._cancel_authorizer: Callable[[str], bool] | None = None` in `__init__`.

---

#### B.3 Health loop reconnection exception handling (LOW)
**Target**: `src/nexusagent/core/worker/worker.py:172`

**RED test**:
```python
@pytest.mark.asyncio
async def test_health_loop_reconnect_failure_logged_at_error_after_threshold():
    """Consecutive reconnect failures should escalate log level."""
    # Mock bus.connect to always fail
    # Run health loop for N iterations
    # Verify ERROR level logging after threshold
```

**GREEN fix**: Track consecutive reconnect failures, escalate log level after N failures.

---

#### B.4 Bare `except Exception:` in `_heartbeat` (LOW) — **NEW from audit**
**Target**: `src/nexusagent/core/worker/worker.py:232-233`

**RED test**: Test that heartbeat exceptions are logged appropriately

**GREEN fix**: Replace bare except with specific handling or at minimum log the error.

---

### Phase C: Pool Module Fixes (src/nexusagent/core/worker/pool.py)

#### C.1 `_execute_bounded` structured error returns (MEDIUM, pre-existing)
**Target**: `src/nexusagent/core/worker/pool.py:286-293`

**RED test**:
```python
# tests/test_worker_pool.py
@pytest.mark.asyncio
async def test_execute_bounded_returns_structured_error():
    """_execute_bounded should raise/return structured error, not string."""
    # Create contract with on_failure="abort"
    # Make _run_agent_task raise specific exception
    # Verify result is structured (Exception type, message) not string
```

**GREEN fix**: Define `ExecutionError(Exception)` with `error_type` field (e.g., "aborted", "escalated", "max_turns") and raise instead of returning strings. **Risk**: Breaking change — audit call sites (`_run_worker` at line 175, recovery path at line 153).

---

#### C.2 String return "Max turns reached" (LOW) — **NEW from audit**
**Target**: `src/nexusagent/core/worker/pool.py:293`

**RED test**: Test that max turns result is structured

**GREEN fix**: Return structured result instead of string.

---

### Phase D: Memory Module Fixes

#### D.1 `memory_utils.py` `__all__` exports (LOW)
**Target**: `src/nexusagent/memory/memory_utils.py` (NEW file)

**RED test**:
```python
# tests/test_memory_utils.py
def test_memory_utils_exports_all_public_functions():
    """memory_utils should define __all__ with all public functions."""
    import nexusagent.memory.memory_utils as mu
    assert hasattr(mu, '__all__')
    expected = ['parse_expiry', 'is_expired', 'parse_frontmatter', 
                'serialize_frontmatter', 'strip_frontmatter']
    assert set(mu.__all__) == set(expected)
```

**GREEN fix**: Add `__all__ = ['parse_expiry', 'is_expired', 'parse_frontmatter', 'serialize_frontmatter', 'strip_frontmatter']` to module.

---

#### D.2 `serialize_frontmatter` None body handling (LOW)
**Target**: `src/nexusagent/memory/memory_utils.py:47-49`

**RED test**:
```python
def test_serialize_frontmatter_handles_none_body():
    """serialize_frontmatter should treat None body as empty string."""
    fm = {"name": "test", "type": "world"}
    result = serialize_frontmatter(fm, None)
    assert "None" not in result
    assert result.endswith("\n\n")
```

**GREEN fix**: Add `body = body or ""` at function start for defense-in-depth.

---

#### D.3 Local `import math` style (NIT)
**Target**: `src/nexusagent/memory/memory_files.py:216`

**RED test**: Style check - verify `import math` is at module level.

**GREEN fix**: Move `import math` to module top-level imports.

---

#### D.4 Quality score not updated on file append (LOW) — **NEW from audit**
**Target**: `src/nexusagent/memory/memory_files.py:188`

**RED test**:
```python
# tests/test_memory_files.py
def test_write_entry_updates_quality_score_on_append():
    """Appending to existing file should update quality_score in frontmatter."""
    # Write entry, then append to same file
    # Verify frontmatter quality_score is recalculated
```

**GREEN fix**: When appending to existing file, recalculate and update quality_score in frontmatter.

---

### Phase E: Test Infrastructure

#### E.1 Run all new tests and verify full suite
```bash
PYTHONPATH=src pytest tests/test_websocket.py tests/test_websocket_timeouts.py \
  tests/test_worker_pool.py tests/test_memory_files.py \
  tests/test_memory_utils.py tests/core/worker/test_worker.py -v
```

---

## Files Likely to Change

| File | Changes |
|------|---------|
| `src/nexusagent/server/websocket.py` | A.1, A.2, A.3, A.4, A.5, A.6 |
| `src/nexusagent/core/worker/worker.py` | B.1, B.2, B.3, B.4 |
| `src/nexusagent/core/worker/pool.py` | C.1, C.2 |
| `src/nexusagent/memory/memory_utils.py` | D.1, D.2 |
| `src/nexusagent/memory/memory_files.py` | D.3, D.4 |
| `tests/test_websocket_timeouts.py` | A.1 (extend), A.6 |
| `tests/test_websocket.py` | A.2, A.3, A.4, A.5 |
| `tests/test_worker_pool.py` | C.1, C.2 |
| `tests/core/worker/test_worker.py` (NEW) | B.1, B.2, B.3, B.4 |
| `tests/test_memory_utils.py` (NEW) | D.1, D.2 |

---

## Tests / Validation

### Per-Fix Verification
Each fix must:
1. Have a test written FIRST (RED)
2. Test fails against current code
3. Fix applied (GREEN)
4. Test passes
5. No regression in existing tests

### Full Regression
```bash
# Targeted suite
PYTHONPATH=src pytest tests/test_memory_files.py tests/test_websocket.py \
  tests/test_websocket_timeouts.py tests/test_worker_pool.py \
  tests/test_server.py tests/core/worker tests/security/test_category1_security.py -q

# Full suite (excluding E2E)
PYTHONPATH=src pytest tests/ -q --ignore=tests/test_e2e_production.py
```

### Codegate Check
```bash
rw_codegate check src/nexusagent/server/websocket.py \
  src/nexusagent/core/worker/worker.py \
  src/nexusagent/core/worker/pool.py \
  src/nexusagent/memory/memory_files.py \
  src/nexusagent/memory/memory_utils.py
```

---

## Risks, Tradeoffs, and Open Questions

### Risks
1. **WebSocket timeout behavior change**: Fixing `_recv_with_timeout` exception handling changes error flow. Must ensure existing WebSocket clients aren't broken.
2. **Pool error structure change**: Converting string returns to structured exceptions is a breaking change for any internal callers. Need to audit call sites.
3. **Memory utils API**: New module `memory_utils.py` — ensure no circular imports with `memory_files.py`.

### Tradeoffs
1. **Heartbeat interval**: 15s vs 30s — more responsive cancellation but 2x DB writes. Configurable would be ideal but adds complexity. Start with constant, add config if needed.
2. **Reconnect logging escalation**: Adds state to health loop. Keep simple — counter + threshold.

### Open Questions
1. **Pool structured errors**: What exception hierarchy? Single `ExecutionError` with `error_type` field, or hierarchy?
2. **Feature flag for heartbeat interval**: Worth adding now or defer?

---

## Execution Order (Dependency-Aware)

1. **Memory utils** (D.1, D.2) — no dependencies, new module
2. **Memory files style** (D.3) — depends on D.1 imports
3. **Memory files quality score** (D.4) — depends on D.1
4. **Worker constants/init** (B.1, B.2) — no dependencies
5. **Worker health loop** (B.3) — depends on B.1 constant
6. **Worker heartbeat bare except** (B.4) — independent
7. **WebSocket timeout helper** (A.1) — no dependencies
8. **WebSocket origin logging** (A.2) — depends on A.1 helper
9. **WebSocket receive_messages bare except** (A.3) — independent
10. **WebSocket events/pol callbacks bare except** (A.4, A.5) — independent
11. **WebSocket integration test** (A.6) — depends on A.1, A.2
12. **Pool structured errors** (C.1, C.2) — depends on worker types
13. **Test infrastructure** (E.1) — all above

---

## Plan Status
**Ready for execution after reverse audit completion.**

This plan will be executed in strict TDD mode — no production code without failing test first.

---

## Reverse Audit Status: PENDING
*Will incorporate findings when reverse audit subagent completes*