# Category 2: Control Flow & Runtime Safety — Implementation Plan

## Goal
Eliminate unbounded loops, excessive control-flow complexity, and runaway execution paths so NexusAgent cannot hang, spin, or escalate without bounds.

## Current Context
- `worker/worker.py` has `while True:` without backstop/exit guard
- `server/websocket.py` has 3× unbounded loops (`while True:`)
- Cyclomatic complexity breaches in `register_routes` (27), `session_websocket` (34), `_run_worker` (17), `_execute_bounded` (12), `_health_loop` (13)
- Excessive agency pattern in websocket workflow without escalation/approval controls

## Proposed Approach
Restrict runtime control flow in 3 waves:
1. **Wave 1 — Loop Backstops**: add bounded iteration/timeout/exit conditions to all unbounded loops
2. **Wave 2 — Complexity Reduction**: decompose God functions into smaller units with explicit state machines
3. **Wave 3 — Agency Controls**: add approval/escalation checkpoints in websocket flows

## Step-by-Step Plan

### Wave 1: Loop Backstops
- [ ] **W1.1** `src/nexusagent/core/worker/worker.py`
  - Add bounded retry/timeout to loop around agent execution
  - Add explicit break/exit conditions and max iteration cap
- [ ] **W1.2** `src/nexusagent/server/websocket.py`
  - Add loop timeout/backoff to all `while True:` loops
  - Ensure websocket handlers can exit cleanly on disconnect/cancel
- [ ] **W1.3** `src/nexusagent/core/worker/pool.py`
  - Bound worker execution loop and bounded executor loop

### Wave 2: Complexity Reduction
- [ ] **W2.1** `src/nexusagent/server/routes.py`
  - Extract route registration into smaller route modules/classes
  - Reduce `register_routes` complexity below 10
- [ ] **W2.2** `src/nexusagent/server/websocket.py`
  - Split `session_websocket` into state-machine-based handlers
  - Reduce per-function complexity below 10 where possible
- [ ] **W2.3** `src/nexusagent/core/worker/pool.py`
  - Extract `_run_worker` and `_execute_bounded` into smaller workers
- [ ] **W2.4** `src/nexusagent/core/worker/worker.py`
  - Reduce `_health_loop` complexity

### Wave 3: Agency Controls
- [ ] **W3.1** `src/nexusagent/server/websocket.py`
  - Add approval/escalation hooks before high-impact actions
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
