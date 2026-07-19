# M3 — Event-Oriented Memory

**Goal:** Store structured events (what happened, why, result, verification) instead of text snippets.
**Current state:** MemoryEntryType has WORLD / EXPERIENCE / OPINION / OBSERVATION — all are text blobs with a type label. No structured event fields.

---

## New memory type: EVENT

Add to `MemoryEntryType`:

```python
class MemoryEntryType(StrEnum):
    WORLD = "world"
    EXPERIENCE = "experience"
    OPINION = "opinion"
    OBSERVATION = "observation"
    EVENT = "event"                     # ← NEW
```

### Event fields

An EVENT entry in the frontmatter:

```yaml
---
name: "Session memory: WebSocket OOM fix"
description: "Fixed receive_json() OOM in websocket.py"
type: event
event:
  action: "patched websocket.py"
  trigger: "user reported session freeze on large messages"
  result: "receive_text() + size check before json.loads()"
  verification: "pytest test_websocket_oom passes; manual wscat test confirmed"
  success: true
  duration_seconds: 120
  related_files:
    - src/nexusagent/server/websocket.py
timestamp: 2026-07-14T12:00:00
---
```

### EventEvent dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

class EventType(StrEnum):
    FIX = "fix"                 # Bug fix
    FEATURE = "feature"         # New capability
    REFACTOR = "refactor"       # Code restructuring
    RESEARCH = "research"       # Investigation / discovery
    DECISION = "decision"       # Architectural choice
    ERROR = "error"             # Failure / incident
    CORRECTION = "correction"   # User correction
    VERIFICATION = "verification"  # Test / verification


@dataclass
class MemoryEvent:
    """Structured event for event-oriented memory."""
    action: str                     # What was done ("patched websocket.py")
    trigger: str                    # Why ("user reported session freeze")
    result: str                     # What happened ("receive_text() + size check")
    verification: str               # How verified ("pytest passes, wscat confirms")
    event_type: EventType = EventType.FIX
    success: bool = True
    duration_seconds: int | None = None
    related_files: list[str] = field(default_factory=list)
    related_events: list[str] = field(default_factory=list)  # Memory IDs
```

---

## Writing events

### New method: `write_event()`

```python
class FileMemory:
    def write_event(
        self,
        event: MemoryEvent,
        description: str,
        entities: list[str] | None = None,
        ttl_hours: int | None = None,
    ) -> str:
        """Write a structured event to memory.

        Events are stored with the full structured frontmatter,
        enabling timeline queries and causality chains.
        """
        return self.write_entry(
            content=event.action,           # Primary text content
            entry_type=MemoryEntryType.EVENT,
            description=description,
            confidence=1.0 if event.success else 0.0,
            entities=entities or event.related_files,
            ttl_hours=ttl_hours,
            # Store structured event in frontmatter
            _extra_frontmatter={"event": dataclasses.asdict(event)},
        )
```

### Higher-level: `record_event()` on HybridMemoryManager

```python
class HybridMemoryManager:
    async def record_event(
        self,
        action: str,
        trigger: str,
        result: str,
        verification: str,
        event_type: EventType = EventType.FIX,
        success: bool = True,
        related_files: list[str] | None = None,
    ) -> str:
        """Record a structured event in memory.

        Returns the file path of the written event.
        """
        event = MemoryEvent(
            action=action,
            trigger=trigger,
            result=result,
            verification=verification,
            event_type=event_type,
            success=success,
            related_files=related_files or [],
        )
        return await self.remember(
            content=event.action,
            type="event",
            description=f"{event_type.value}: {action[:60]}",
            confidence=1.0 if success else 0.0,
            source=MemorySource.SYSTEM,
            authority=0.8,  # Events are agent-recorded, high authority
            _event=event,   # Pass structured event to FileMemory
        )
```

---

## Querying events

### New method: `recall_events()`

```python
async def recall_events(
    self,
    event_type: EventType | None = None,
    success: bool | None = None,
    action_query: str = "",
    max_results: int = 10,
    timeframe: tuple[datetime, datetime] | None = None,
) -> list[dict]:
    """Search structured events with event-specific filters.

    Uses hybrid search on content + event fields, then filters
    by event_type, success, and timeframe.
    """
    query = f"event:{action_query}" if action_query else "type:event"
    results = await self.index.search(query, max_results=max_results * 3)

    filtered = []
    for r in results:
        fm = self._read_full_frontmatter(r["file"])
        event_data = fm.get("event")
        if not event_data:
            continue
        if event_type and event_data.get("event_type") != event_type.value:
            continue
        if success is not None and event_data.get("success") != success:
            continue
        filtered.append(r)

    return filtered[:max_results]
```

---

## Timeline reconstruction

Events can be linked into causal chains via `related_events`:

```yaml
---
event:
  action: "Implemented ToolRegistry snapshots"
  trigger: "User spec for immutable tool cache"
  result: "ToolRegistry class with freeze/prune"
  verification: "23 tests passing"
  event_type: feature
  related_events:
    - "md5abc-def0-defect-analysis-websocket"
    - "md5abc-def1-decided-immutable-tool-cache"
---
```

The timeline is reconstructed by following `related_events` chains:

```
Session start
  → EVENT: "Decided immutable tool cache approach" (decision)
    → EVENT: "Implemented ToolRegistry snapshots" (feature)
      → EVENT: "Tests pass for ToolRegistry" (verification)
  → EVENT: "Discovered Agent.__del__ unreliability" (research)
    → EVENT: "Switched to WeakValueDictionary cleanup" (fix)
```

### Timeline rendering

```python
async def get_timeline(
    self,
    root_event_id: str,
    max_depth: int = 3,
) -> list[dict]:
    """Reconstruct a causal chain of events from a root event ID."""
    chain = []
    visited = set()
    queue = [root_event_id]

    while queue and len(chain) < max_depth:
        eid = queue.pop(0)
        if eid in visited:
            continue
        visited.add(eid)
        fm = self._read_full_frontmatter(eid)
        event_data = fm.get("event")
        if event_data:
            chain.append({"id": eid, **event_data})
            for rel in event_data.get("related_events", []):
                queue.append(rel)

    return chain
```

---

## Integration with existing types

| Type | Migrates to | How |
|------|------------|-----|
| EXPERIENCE (current) | EVENT (new) | `trigger="agent experience"`, `verification="agent-reported"` |
| OBSERVATION (current) | EVENT (new) or stays | If structured → EVENT; if unstructured → stays OBSERVATION |
| WORLD (current) | Stays WORLD | Events reference WORLD facts, but WORLD is not an event |
| OPINION (current) | Stays OPINION | Preferences are not events |

---

## Files to modify

| File | Change | ± Lines |
|------|--------|---------|
| `memory/memory_files.py` | Add `MemoryEvent` dataclass, `EventType` enum, `write_event()` method, `_extra_frontmatter` parameter to `write_entry()` | +50 |
| `memory/memory_item.py` | Add `MemoryEntryType.EVENT` | +1 |
| `memory/hybrid_memory.py` | Add `record_event()` and `recall_events()` methods, `_read_full_frontmatter()` helper | +60 |
| `memory/extraction.py` | Auto-extract events from EXPERIENCE entries during dream cycle | +15 |
| `core/session/session.py` | Auto-record events for key actions (fixes, decisions, user corrections) | +10 |

## Effort

- Implementation: ~0.75 day
- Tests: ~0.75 day (event round-trip, recall filtering, timeline reconstruction)
- Risk: Low (additive — existing memory paths unchanged, EVENT is new type alongside existing types)
