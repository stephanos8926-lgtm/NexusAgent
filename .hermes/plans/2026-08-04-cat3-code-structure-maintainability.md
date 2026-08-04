# Category 3: Code Structure & Maintainability — Implementation Plan

## Goal
Reduce duplication, normalize structure, and bring oversized files/functions into a maintainable shape so future security and feature work is cheaper and safer.

## Current Context
- `server/routes.py` has 5+ blocks with 85–100% structural similarity
- `server/websocket.py` has `events_websocket` and `pol_websocket` at 96% similarity
- `memory_files.py` has 5 methods with 90–98% structural similarity
- `memory_files.py` is 680 lines vs 500-line limit
- Multiple functions above complexity threshold

## Proposed Approach
Improve structure in 3 waves:
1. **Wave 1 — Deduplication**: extract shared route/websocket/memory patterns
2. **Wave 2 — File/Function Size**: split oversized modules and reduce complexity
3. **Wave 3 — Import Hygiene**: resolve hallucinated/unused imports and normalize module boundaries

## Step-by-Step Plan

### Wave 1: Deduplication
- [ ] **W1.1** `src/nexusagent/server/routes.py`
  - Extract shared request/response shaping into helpers
  - Parameterize near-duplicate Pydantic models/endpoints
- [ ] **W1.2** `src/nexusagent/server/websocket.py`
  - Merge `events_websocket` and `pol_websocket` shared path into common handler
  - Keep differences as policy/config, not copy-paste bodies
- [ ] **W1.3** `src/nexusagent/memory/memory_files.py`
  - Extract common file mutation/auth/expiry logic into shared helpers
  - Reduce duplicated entity-update/logging patterns

### Wave 2: File/Function Size
- [ ] **W2.1** `src/nexusagent/memory/memory_files.py`
  - Split into focused submodules/files while preserving public API
  - Keep `__init__` exports stable for import compatibility
- [ ] **W2.2** Complexity reduction targets
  - `register_routes`, `session_websocket`, `_run_worker`, `_execute_bounded`, `_health_loop`, `write_entry`, `_parse_response`, `_heuristic_synthesize`
  - Break into smaller functions with explicit contracts

### Wave 3: Import Hygiene
- [ ] **W3.1** Resolve hallucinated/unused imports
  - `nexusagent.core.task.task_state`
  - `nexusagent.core.agent`
  - `nexusagent.core.events`
  - `sqlalchemy` in `worker/worker.py`
  - `nexusagent.core.worker.handler`
- [ ] **W3.2** Verify package exports in `__init__.py` files match actual modules
- [ ] **W3.3** Remove dead imports and normalize local/absolute import style

## Files Likely to Change
- `src/nexusagent/server/routes.py`
- `src/nexusagent/server/websocket.py`
- `src/nexusagent/memory/memory_files.py`
- `src/nexusagent/core/worker/worker.py`
- `src/nexusagent/core/worker/pool.py`
- `src/nexusagent/memory/refinement.py`
- `src/nexusagent/core/task/task_store.py`
- Related `__init__.py` files as needed

## Tests / Validation
- Run targeted pytest after each extraction/refactor
- Run `ruff check src/ tests/`
- Run `rw_codegate` on refactored files
- Verify public imports still resolve

## Risks, Tradeoffs, and Open Questions
- **Risk**: Splitting files can break tests/imports if compatibility layer is incomplete.
  - *Mitigation*: Keep compat shims until all imports verified.
- **Risk**: Deduplication may over-abstract one-off differences.
  - *Mitigation*: Parameterize only when 3+ call sites share behavior.
- **Open Question**: Should memory files become a subpackage now, or defer until auth cleanup is stable?
