# SPEC-003: Session-Memory Integration

> **Status:** Draft
> **Date:** 2026-07-22
> **Author:** OWL (Lucien)
> **Depends:** ADR-006

---

## Goal

Wire `HybridMemoryManager` into the session loop so the agent automatically recalls relevant memories at session start and stores important facts after each turn.

## Problem

`HybridMemoryManager` exists and works (tested in isolation) but `Session` never uses it. The agent has no memory recall during conversation.

## Solution

### Component 1: Session Owns HybridMemoryManager

**File:** `src/nexusagent/core/session/session.py`

```python
class Session:
    def __init__(self, ..., memory_dir: str | None = None):
        # Resolve memory directory
        self.memory_dir = memory_dir or self._resolve_memory_dir()
        self.hybrid_memory = HybridMemoryManager(self.memory_dir)
        self.hybrid_memory.initialize()
```

**Memory directory resolution order:**
1. Explicit `memory_dir` parameter
2. `settings.agent.memory_workspace` (config)
3. `working_dir/.nexusagent/memory` (workspace-scoped)
4. `~/.nexusagent/sessions/{session_id}/memory` (legacy fallback)

### Component 2: Auto-Recall at Session Start

**File:** `src/nexusagent/core/session/session.py`

In `send()`, before building messages:

```python
# Inject memory context as SystemMessage
if self.hybrid_memory:
    memory_context = self.hybrid_memory.get_memory_context(user_message, max_results=5)
    if memory_context:
        messages.append(SystemMessage(content=memory_context))
```

### Component 3: Auto-Extract After Each Turn

**File:** `src/nexusagent/core/session/session.py`

After agent response completes:

```python
# Fire-and-forget memory extraction
asyncio.create_task(
    self._extract_and_store(user_message, agent_response)
)
```

**Extraction logic:**
1. Build extraction prompt: "Extract memorable facts from this conversation turn"
2. Call LLM with lightweight model (configurable, default: current model)
3. Parse response into memory entries
4. Store via `hybrid_memory.remember()` with type=`observation`

### Component 4: Pre-Compaction Flush

**File:** `src/nexusagent/core/session/session.py`

```python
async def pre_compaction_flush(self) -> str:
    summary = self._build_session_summary()
    await self.hybrid_memory.flush(summary)
    return summary
```

### Component 5: SessionManager Memory Discovery

**File:** `src/nexusagent/core/session/manager.py`

```python
def get_or_create(self, session_id, working_dir, agent, db_repo, memory_dir=None):
    # Resolve memory_dir
    resolved_memory_dir = memory_dir or self._resolve_memory_dir(working_dir)
    
    session = Session(
        ...,
        memory_dir=resolved_memory_dir,
    )
    
    # Cross-session memory injection
    if working_dir:
        prev_memories = self._discover_previous_memories(working_dir, session_id, limit=3)
        if prev_memories:
            session.inject_memory_context(prev_memories)
    
    return session
```

### Component 6: Cross-Session Memory Discovery

**File:** `src/nexusagent/core/session/manager.py`

```python
def _discover_previous_memories(self, working_dir: str, current_session_id: str, limit: int = 3) -> list[dict]:
    """Find relevant memories from previous sessions in the same workspace."""
    sessions_dir = Path.home() / ".nexusagent" / "sessions"
    if not sessions_dir.exists():
        return []
    
    # Find sessions with same working_dir (check session metadata in DB)
    prev_sessions = self.db_repo.find_sessions_by_working_dir(working_dir, exclude=current_session_id, limit=5)
    
    all_memories = []
    for prev in prev_sessions:
        prev_memory_dir = Path(prev.memory_dir)
        if prev_memory_dir.exists():
            idx = HybridMemoryIndex(prev_memory_dir / ".memory" / "index.sqlite")
            results = idx.search_sync(self._build_context_query(working_dir), max_results=limit)
            all_memories.extend(results)
    
    # Rank by score, return top-N
    all_memories.sort(key=lambda m: m.get("score", 0), reverse=True)
    return all_memories[:limit]
```

## Files to Modify

| File | Change |
|------|--------|
| `src/nexusagent/core/session/session.py` | Add `hybrid_memory` field, auto-recall in `send()`, auto-extract after turn, flush in `pre_compaction_flush()` |
| `src/nexusagent/core/session/manager.py` | Add `memory_dir` param to `get_or_create()`, cross-session memory discovery |
| `src/nexusagent/core/agent.py` | Pass `memory_dir` from `run_agent_task()` state |
| `src/nexusagent/server/websocket.py` | Pass `memory_dir` from query params |
| `src/nexusagent/infrastructure/config.py` | Add `memory_model` config field (for extraction) |

## Tests

1. `test_session_memory_initialization` — Session creates HybridMemoryManager on init
2. `test_session_auto_recall` — send() injects memory context as SystemMessage
3. `test_session_auto_extract` — after turn, observation memory is created
4. `test_session_pre_compaction_flush` — flush saves summary to daily log
5. `test_cross_session_discovery` — previous session memories are found
6. `test_memory_dir_resolution` — correct priority order

## Acceptance Criteria

- [ ] Session automatically recalls relevant memories at conversation start
- [ ] Agent stores observations after each turn (fire-and-forget)
- [ ] Pre-compaction flush saves session summary to daily log
- [ ] Cross-session memory discovery finds previous session memories
- [ ] All tests pass with zero regressions
- [ ] Memory context appears in agent's message list as SystemMessage
