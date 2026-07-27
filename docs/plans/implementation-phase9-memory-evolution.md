# Micro-Implementation Plan: Phase 9 Memory Evolution

This document details the exact micro-steps required to code and test Phase 9.

## Micro-Steps

### Step 1: Implement confidence increment & promotion in `LayerMemoryManager`
- File: `src/nexusagent/memory/layer_manager.py`
- Add a helper `jaccard_similarity(str1, str2)` using token overlap.
- Inside `LayerMemoryManager.remember()`:
  - Query existing items in the target layer using `self.query(content, layer=layer, limit=50)`.
  - Calculate Jaccard similarity for each.
  - If a match is found with similarity `>= 0.7`:
    - Increment confidence by `+0.15` up to `1.0`.
    - Persist the updated item.
    - If the layer is `EPISODIC`, the updated confidence is `>= 0.9`, and the authority is `TrustLevel.TRUSTED`, promote (by calling `self.remember` with `MemoryLayer.SEMANTIC`).
    - Return the item ID.
  - Otherwise, proceed to store the new item.

### Step 2: Refactor `HybridMemoryManager`
- File: `src/nexusagent/memory/hybrid_memory.py`
- Import `LayerMemoryManager` inside `__init__` (to avoid circular imports).
- Instantiate `self.layer_manager = LayerMemoryManager(self.workspace_dir)`.
- Inside `remember()`:
  - Map legacy `type` string to appropriate `MemoryLayer`.
  - Resolve `source` and `authority` (e.g. external tools have lower default authority).
  - Call `self.layer_manager.remember()` with resolved arguments.

### Step 3: Add unit & integration tests
- File: `tests/memory/test_layers.py`
- Write tests verifying:
  - Trust-aware ingestion policy (rejecting direct writes to semantic layer for low-trust sources).
  - Jaccard similarity confidence scoring and +0.15 increment for repeated observations.
  - EPISODIC -> SEMANTIC auto-promotion on confidence >= 0.9 and TRUSTED authority.

### Step 4: Verification
- Run tests: `PYTHONPATH=src:. uv run pytest tests/memory/test_layers.py`
- Run lint/checks: `uv run ruff check src/ tests/`
