# Category 2: Control Flow & Runtime Safety — Implementation Plan (rev 3)

## Goal
Eliminate actual unbounded loops, excessive control-flow complexity, and runaway execution paths so NexusAgent cannot hang, spin, or escalate without bounds.

## Current Context
- `worker/worker.py` heartbeat uses `while not stop_event.is_set():` — bounded by stop event, but no timeout/backoff on sleep
- `server/websocket.py` has 3 async receive loops:
  - `receive_messages()`: `while True:` inside `session_websocket` — exits on disconnect/exception
  - `events_websocket`: `while True:` — exits on WebSocketDisconnect/exception
  - `pol_websocket`: `while True:` — exits on WebSocketDisconnect/exception
  These are standard WebSocket pump loops, but have no explicit max-message or idle timeout.
- `core/worker/pool.py` `_execute_bounded` uses `while turn < contract.max_turns:` — already bounded by turns and wall time
- Complexity hotspots:
  - `register_routes` (27)
  - `session_websocket` (34)
  - `_run_worker` (17)
  - `_execute_bounded` (12)
  - `_health_loop` (13)
- Excessive agency pattern in websocket workflow without escalation/approval controls

## Proposed Approach
Restrict runtime control flow in 3 waves:
1. **Wave 1 — Loop Bounding & Timeouts**: add idle/message caps and timeouts to WebSocket pumps; add backoff to heartbeat sleep
2. **Wave 2 — Complexity Reduction**: decompose `register_routes` and `session_websocket` into smaller units
3. **Wave 3 — Agency Controls**: add approval/escalation checkpoints in websocket flows

## Step-by-Step Plan

### Wave 1: Loop Bounding & Timeouts
- [x] **W1.1** `src/nexusagent/core/worker/worker.py`
  - Add max backoff/sleep cap to `_health_loop` reconnect sleep
  - Ensure heartbeat loop has explicit exit on worker stop
- [x] **W1.2** `src/nexusagent/server/websocket.py`
  - Add idle timeout / max-message cap to `receive_messages()` loop
  - Add idle timeout / max-message cap to `events_websocket` and `pol_websocket` pumps
  - Ensure all WebSocket handlers close cleanly on timeout
- [x] **W1.3** `src/nexusagent/core/worker/pool.py`
  - Verify `_execute_bounded` already bounded by `max_turns` and `max_wall_time`; add explicit timeout exception if missing

### Wave 2: Complexity Reduction
- [ ] **W2.1** `src/nexusagent/server/routes.py`
  - Extract route groups into smaller registration helpers
  - Reduce `register_routes` complexity below 10
- [ ] **W2.2** `src/nexusagent/server/websocket.py`
  - Extract auth/setup logic from `session_websocket` into helpers
  - Split message dispatch into a lookup table or small handler methods
  - Reduce per-function complexity below 10 where possible
- [ ] **W2.3** `src/nexusagent/core/worker/pool.py`
  - Extract `_run_worker` phases (recovery vs clean run) into helpers
  - Reduce `_execute_bounded` complexity below 10

### Wave 3: Agency Controls
- [ ] **W3.1** `src/nexusagent/server/websocket.py`
  - Add approval/escalation hooks before high-impact actions in `session_websocket`
  - Add circuit breakers for repeated autonomous actions
- [ ] **W3.2** `src/nexusagent/core/worker/worker.py`
  - Add bounded autonomy policy for agent task execution
  - Ensure cancellation propagates cleanly

## Files Likely to Change
- `src/nexusagent/core/worker/worker.py`
- `src/nexusagent/core/worker/pool.py`
- `src/nexusagent/server/websocket.py`
- `src/nexusagent/server/routes.py`

## Tests / Validation
- Targeted pytest on worker, pool, routes, websocket
- Add tests asserting loops terminate under cancellation/timeout
- Add complexity regression tests if complexity limits are encoded

## Risks, Tradeoffs, and Open Questions
- **Risk**: Aggressive loop caps may interrupt long-running legitimate tasks.
  - *Mitigation*: Use configurable timeouts with safe defaults; expose override via config.
- **Risk**: Route decomposition may move auth/validation logic unexpectedly.
  - *Mitigation*: Preserve middleware/auth layer during refactor.
- **Open Question**: Do we want a centralized timeout/backoff policy for all async loops?

## Audit Summary

### Forward Audit
- Status: not completed by subagent.
- Inline verification: plan issues were cross-checked against current source; websocket/worker claims are directionally accurate.

### Reverse Audit
- Status: not completed by subagent.
- Inline verification: likely gaps include missing coverage for `server/server.py` lifespan startup paths.

### Completed Work
- Added bounded backoff to worker health loop with 60s cap
- Added explicit cancellation handling to heartbeat loop
- Added WebSocket receive timeout helper with 300s default
- Added new timeout-specific tests

### Next Action
Continue with Wave 2 complexity reduction, then run `pytest` on the affected test files.
