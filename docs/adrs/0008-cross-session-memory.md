# ADR-008: Cross-Session Memory Strategy

> **Status:** Proposed
> **Date:** 2026-07-22
> **Context:** The competitive analysis identified cross-session memory as the #1 gap. The prior session's summary also lists this as the top recommendation.

## Problem

Each session is isolated. When a new session starts, the agent has zero knowledge of what happened in previous sessions for the same workspace. This causes:
- Repeated work (agent rediscovers preferences, decisions, errors)
- Broken continuity (agent contradicts previous decisions)
- Lost context (user info, project state, learned patterns)

## Decision

Implement **federated cross-session search with lazy discovery and caching**.

### Discovery Flow

```
Session Start
  │
  ├─ Check cache for workspace (TTL: 5 min)
  ├─ If cached → Inject cross-session memories as SystemMessage
  └─ If not cached → Async discovery (non-blocking)
       ├─ Query DB for previous sessions in same workspace
       ├─ Open each session's HybridMemoryIndex
       ├─ Search for relevant memories (parallel)
       ├─ Rank by score + recency + quality
       ├─ Cache results
       └─ Inject top-3 as SystemMessage (on next send)
```

### Data Model Changes

1. Add `memory_dir` column to `SessionModel` (migration needed)
2. Add `find_sessions_by_working_dir()` to `SessionRepository`
3. Add index on `working_dir` for query performance

### Performance Targets

| Operation | Target | Rationale |
|-----------|--------|-----------|
| Cache hit | <50ms | Memory recall must feel instant |
| Cache miss (async) | <500ms | First session only; cached after |
| Parallel search | 5 sessions max | Diminishing returns beyond 5 |
| Result injection | <100ms | SystemMessage string formatting |

## Consequences

**Positive:**
- Agent remembers across sessions (continuity)
- Previous session context reduces repeated work
- Cached discovery is near-instant

**Negative:**
- Session startup adds ~200ms on cache miss
- Requires DB migration (new column)
- Cross-session search adds SQLite I/O

**Mitigations:**
- Cache results with 5-min TTL
- Async discovery doesn't block session creation
- Limit to 5 previous sessions (configurable)

## Alternatives Considered

1. **Full conversation history in context** — Rejected: context window too small
2. **External memory service (Mem0/Zep)** — Rejected: adds dependency; file-based is our strength
3. **Periodic consolidation only** — Rejected: no session-start recall
4. **Global shared index** — Rejected: pollutes sessions with irrelevant context

## Related

- SPEC-003: Session-Memory Integration (Task 1.5)
- ADR-006: Memory System Architecture
