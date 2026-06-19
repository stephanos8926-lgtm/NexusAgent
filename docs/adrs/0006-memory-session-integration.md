# ADR-006: Memory System Architecture — Session Integration & Cross-Session Continuity

> **Status:** Proposed
> **Date:** 2026-07-22
> **Deciders:** OWL (Lucien)
> **Context:** NexusAgent's memory system has solid building blocks (FileMemory, HybridMemoryIndex, ConsolidationEngine, self-management tools) but they are NOT wired into the session loop. The agent has no memory recall at session start, no auto-extraction during conversation, and no cross-session continuity.

---

## Problem

The memory infrastructure exists but is orphaned:
1. `HybridMemoryManager` is never instantiated by `Session`
2. `memory_search`, `memory_write` tools exist but the agent never calls them automatically
3. Each session is completely isolated — no knowledge transfer between sessions
4. No background consolidation (dream cycle)
5. No context compression for session history

## Decision

### 1. Session-Memory Integration (P0)

**Approach:** Wire `HybridMemoryManager` into `Session.__init__()` via `SessionManager.get_or_create()`.

```
SessionManager.get_or_create(session_id, working_dir, agent, db_repo, memory_dir=None)
  → Session(..., hybrid_memory=HybridMemoryManager(memory_dir or default))
```

- `memory_dir` resolution: `memory_workspace` config → `working_dir/.nexusagent/memory` → `~/.nexusagent/sessions/{id}/memory`
- Session calls `hybrid_memory.get_memory_context(query)` at the start of `send()` and injects as `SystemMessage`
- Session calls `hybrid_memory.remember()` after each agent turn (auto-extraction)
- Session calls `hybrid_memory.flush()` in `pre_compaction_flush()`

**Rationale:** The session is the unit of conversation. Memory must be owned by the session, not floating globally.

### 2. Cross-Session Memory (P0)

**Approach:** Federated search across session directories.

- `memory_search(cross_session=True)` queries: current session + previous N sessions + global + workspace
- At session start, `SessionManager` discovers previous sessions for the same `working_dir`
- Injects top-3 relevant memories from previous sessions as `SystemMessage`
- Uses existing `HybridMemoryIndex.search()` per directory, merges results by score

**Rationale:** The #1 complaint from the competitive analysis. Agent forgets everything between sessions.

### 3. Auto Memory Extraction (P1)

**Approach:** Post-turn hook extracts salient facts.

- After each `send()`, analyze the conversation turn for memorable information
- Extract: decisions made, files modified, errors encountered, user preferences
- Store as `observation` type memories
- Deduplicate via existing write-time dedup (cosine similarity)

**Rationale:** Manual `memory_write()` is unreliable. The agent forgets to save important facts.

### 4. Consolidation Daemon (P1)

**Approach:** Cron-based background dream cycle.

- Runs every 24h or after 5 new sessions (configurable)
- 4-phase: scan → find patterns → merge/prune → trim index
- Sandboxed: can only write to memory files, never source code
- Triggered via `hermes cron` or `memory_consolidate` tool

**Rationale:** Memory health degrades over time without maintenance. Proactive consolidation prevents bloat.

### 5. Hierarchical Context Compression (P2)

**Approach:** LCM-style DAG for session history.

- Depth-0: specific decisions and technical details (recent turns)
- Depth-1: conversation arc and outcomes (summarized from depth-0)
- Depth-2: durable narrative and milestone timeline (summarized from depth-1)
- Fresh tail protection: last 64 messages never compacted
- Agent tools: `session_search`, `session_expand`, `session_describe`

**Rationale:** Current compaction loses detail. DAG preserves pointers to source messages.

### 6. Provenance Tracking (P2)

**Approach:** Every memory entry stores `source_session_id` and `derived_from`.

- `FileMemory.write_entry()` accepts `source_session_id` parameter
- `derived_from` links to parent memory for observation extraction
- Enables "show me where this was learned" audit trail

**Rationale:** Required for trust and auditability. Can't verify a memory without knowing its source.

## Consequences

**Positive:**
- Agent remembers across sessions (continuity)
- Memory health maintained automatically (no bloat)
- Context compression preserves detail (LCM DAG)
- Full audit trail for memories

**Negative:**
- Session startup now has memory recall latency (~200ms for federated search)
- Auto-extraction adds ~500ms per turn (LLM call for fact extraction)
- Consolidation daemon needs cron setup

**Mitigations:**
- Federated search is parallel across directories (fast)
- Auto-extraction is fire-and-forget (non-blocking)
- Consolidation runs in background (no user impact)

## Alternatives Considered

1. **Vector-only cross-session search** — Rejected: loses keyword precision for code/IDs
2. **Full conversation history in context** — Rejected: context window too small
3. **External memory service (Mem0/Zep)** — Rejected: adds dependency, file-based is our strength
4. **Manual memory management only** — Rejected: agent forgets, unreliable

---

## Related

- ADR-001 through ADR-005 (existing project decisions)
- SPEC-001: Memory Self-Management (implemented)
- SPEC-002: Workspace-Scoped Memory (implemented)
- MEMORY_SYSTEM_COMPREHENSIVE_ANALYSIS.md (full analysis)
