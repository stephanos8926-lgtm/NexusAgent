# Phase 1: Extract `infrastructure/utils.py` into `infrastructure/utils/` subpackage

## Status: READY FOR EXECUTION

### Forward Audit Findings ✅
- 354 lines → 3 independent concerns
- Zero coupling between concerns
- 2 consumers: `core/worker.py`, `llm/llm.py`
- No test files depend on this

### Reverse Audit Findings ✅
- All forward findings confirmed
- **Blind spots found:**
  1. `retry_on_false` is DEAD CODE (no consumers anywhere)
  2. `scripts/update_imports.py` references old path (update/archive)
  3. Plan's `decorators.py` has no content — DO NOT create

### Final Extraction Plan

```
infrastructure/utils/
├── __init__.py    — re-exports all public symbols
├── retry.py       — retry_with_backoff, retry_on_false (dead code, keep for now)
└── circuit.py     — CircuitState, CircuitBreakerError, CircuitBreaker
```

**Old file:** `infrastructure/utils.py` → **kept as thin compat shim** that re-exports from new subpackage. This ensures:
- Zero import breakage for any consumer we might have missed
- `scripts/update_imports.py` won't cause issues
- Clean removal path for future (delete shim when confident)

### Files to Create
1. `infrastructure/utils/__init__.py` — re-exports
2. `infrastructure/utils/retry.py` — retry_with_backoff, retry_on_false
3. `infrastructure/utils/circuit.py` — CircuitState, CircuitBreakerError, CircuitBreaker

### Files to Modify
1. `infrastructure/utils.py` — replace with thin compat shim
2. `core/worker.py:17` — update import path
3. `llm/llm.py:10` — update import path

### Files to Archive
1. `scripts/update_imports.py` — move to `scripts/archive/`

### Verification
- `PYTHONPATH=src python3 -m pytest tests/ -q --ignore=tests/test_e2e_production.py`
- Must maintain 453 passing, 20 failed baseline
