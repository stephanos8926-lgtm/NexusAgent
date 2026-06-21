# Cross-Agent Memory — Implementation Plan

> **Date:** 2026-06-20
> **Author:** OWL (Lucien)
> **Priority:** P1 — Hard
> **Estimated Effort:** 3-4 days

---

## Goal

Workers spawned by the orchestrator should inherit memories from the parent session. This enables multi-agent workflows where sub-agents build on the parent agent's context without duplicating information.

## Architecture

```
Parent Session
├── hybrid_memory/              ← Parent's memory directory
│   ├── bank/
│   ├── .memory/
│   └── MEMORY.md
│
└── Sub-Agent Session (Worker)
    ├── hybrid_memory/          ← Worker's own memory directory (isolated writes)
    │   ├── bank/
    │   ├── .memory/
    │   └── MEMORY.md
    │
    └── parent_memory_dir → symbolic reference to parent's memory_dir
```

**Key principles:**
1. **Read sharing**: Sub-agents can READ parent memories (via `get_memory_context()` searching both dirs)
2. **Write isolation**: Sub-agents WRITE only to their own memory directory
3. **Promotion**: After sub-agent completes, relevant memories can be promoted to parent
4. **No circular deps**: Parent never reads from sub-agent (one-way flow)

## Implementation Steps

### Step 1: Add `parent_memory_dir` to `HybridMemoryManager`
**File:** `src/nexusagent/memory/hybrid_memory.py`
- Add `parent_memory_dir: Path | None` parameter to `__init__()`
- Add `_get_index()` method that returns both own and parent indices
- Modify `remember()` to write ONLY to own directory
- Modify `recall()` to search both own and parent indices, merge results
- Add `get_memory_context()` enhancement to include parent context with `[Parent]` prefix

### Step 2: Add `inherit_from()` method
**File:** `src/nexusagent/memory/hybrid_memory.py`
```python
def inherit_from(self, parent_dir: str | Path) -> None:
    """Set parent memory directory for read-only cross-agent memory sharing."""
    self.parent_memory_dir = Path(parent_dir)
    if self.parent_memory_dir.exists():
        self._parent_index = HybridMemoryIndex(str(self.parent_memory_dir))
        logger.info("Inherited parent memory from %s", parent_dir)
    else:
        logger.warning("Parent memory dir %s does not exist", parent_dir)
```

### Step 3: Add `promote_to_parent()` method
**File:** `src/nexusagent/memory/hybrid_memory.py`
```python
async def promote_to_parent(self, filter_fn=None) -> int:
    """Copy selected memories from this agent's directory to parent's directory.
    
    Args:
        filter_fn: Optional callable(memory_dict) -> bool to select which memories to promote.
                   If None, promotes all observations with confidence >= 0.7.
    
    Returns:
        Number of memories promoted.
    """
```

### Step 4: Wire into `SessionManager`
**File:** `src/nexusagent/core/session/manager.py`
- Modify `get_or_create()` to accept optional `parent_memory_dir` parameter
- When creating sub-agent sessions, pass parent's `memory_dir` as `parent_memory_dir`
- Add `get_parent_memory_dir(session_id)` to retrieve a session's parent memory dir

### Step 5: Wire into `Session`
**File:** `src/nexusagent/core/session/session.py`
- Modify `__init__()` to accept `parent_memory_dir` parameter
- Pass to `HybridMemoryManager` initialization
- Add `inherit_from()` call after initialization
- Store `parent_memory_dir` for later retrieval

### Step 6: Wire into Worker Pool
**File:** `src/nexusagent/core/worker/pool.py` (or wherever workers are spawned)
- When spawning sub-agents, pass `parent_memory_dir` from the orchestrator's session
- After sub-agent completes, call `promote_to_parent()` to merge results

### Step 7: Add tests
**File:** `tests/test_memory_cross_agent.py`
- Test parent memory inheritance (sub-agent can read parent memories)
- Test write isolation (sub-agent writes don't pollute parent)
- Test memory promotion (selected memories move to parent)
- Test multi-level inheritance (grandparent → parent → child)

### Step 8: Add CLI commands
**File:** `src/nexusagent/interfaces/cli.py`
- `memory inherit <parent_session_id>` — manually inherit from another session
- `memory promote [--min-confidence 0.7]` — promote memories to parent
- `memory family` — show parent/child memory relationships

---

## Files to Modify

| File | Change |
|------|--------|
| `src/nexusagent/memory/hybrid_memory.py` | Add parent_memory_dir, inherit_from, promote_to_parent |
| `src/nexusagent/core/session/manager.py` | Pass parent_memory_dir on creation |
| `src/nexusagent/core/session/session.py` | Accept + pass parent_memory_dir |
| `src/nexusagent/core/worker/pool.py` | Pass parent_memory_dir when spawning |
| `tests/test_memory_cross_agent.py` | New test file (~12 tests) |

---

## Verification

After implementation:
1. Start a session, store some memories
2. Spawn a sub-agent that reads those memories
3. Verify sub-agent can recall parent memories
4. Verify sub-agent writes go to own directory
5. Promote sub-agent memories to parent
6. Verify parent now has both sets of memories
7. Run full test suite — zero regressions

---

## Deferred (Not in this phase)
- NATS-based distributed memory (requires message serialization)
- LLM extraction replacement (separate task)
- Memory conflict resolution across agents (can use existing contradiction detection)
