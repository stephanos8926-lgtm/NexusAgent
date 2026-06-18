# Implementation Plan: Memory System Improvements

> Status: DRAFT
> Priority: HIGH
> Author: OWL (Lucien)
> Date: 2026-07-21
> Based on: MEMORY_SYSTEM_ANALYSIS.md, SPEC-001, SPEC-002

## Overview

This plan covers the immediate and short-term improvements to the NexusAgent memory system, organized by priority and dependency. Each phase builds on the previous one.

## Phase 1: Agent Self-Management Tools (SPEC-001)

**Duration:** 1-2 days
**Priority:** CRITICAL
**Dependencies:** None

### Tasks

1.1. **Add `memory_delete` tool** (2 hours)
- Delete memory file + index entries
- Path traversal protection
- Confirmation message
- Tests

1.2. **Add `memory_update` tool** (2 hours)
- Update existing memory file content
- Re-index modified file
- Preserve YAML frontmatter
- Tests

1.3. **Add `memory_list` tool** (1 hour)
- List all memories with filtering (type, date, entity)
- Returns structured list
- Tests

1.4. **Add `memory_prune` tool** (3 hours)
- Prune by age, type, confidence
- Dry-run mode
- Confirmation for destructive ops
- Tests

### Verification
- Run full test suite: `PYTHONPATH=python3 -m pytest tests/ -q --tb=short`
- Zero regressions
- All new tests pass

## Phase 2: Workspace-Scoped Memory (SPEC-002)

**Duration:** 1 day
**Priority:** HIGH
**Dependencies:** Phase 1

### Tasks

2.1. **Update `_get_memory_workspace()` in tools** (2 hours)
- Accept session context
- Default to session's workspace
- Fallback chain: workspace → session → global

2.2. **Add `memory_workspace` config option** (1 hour)
- Add to ConfigSchema
- Tests

2.3. **Add workspace initialization** (2 hours)
- Auto-create directory structure
- Create `.gitignore`
- Separate MEMORY.md per workspace

2.4. **Add cross-workspace search** (2 hours)
- `workspace="all"` parameter
- Results tagged with workspace source
- Tests

2.5. **Update session initialization** (1 hour)
- Point session hybrid_memory to workspace dir
- Tests

### Verification
- Run full test suite
- Zero regressions
- Manual verification: create memories in project A, verify they don't appear in project B

## Phase 3: Write-Time Deduplication

**Duration:** 0.5 days
**Priority:** HIGH
**Dependencies:** Phase 1

### Tasks

3.1. **Add dedup check to `memory_write`** (2 hours)
- Before writing, call `memory_search` with same query
- If top result > 0.95 cosine similarity, skip write
- Return existing file path with "duplicate" flag
- Configurable threshold

3.2. **Update HybridMemoryManager.remember()** (1 hour)
- Add dedup parameter
- Tests

### Verification
- Write same memory twice, verify second is skipped
- Test with threshold configuration

## Phase 4: Background Consolidation Daemon

**Duration:** 2-3 days
**Priority:** MEDIUM
**Dependencies:** Phase 1, 2

### Tasks

4.1. **Design consolidation pipeline** (4 hours)
- Orient: scan all memories, identify stale/contradictory/redundant
- Gather: collect related memories into groups
- Consolidate: merge duplicates, resolve contradictions
- Prune: remove stale entries
- Re-index: rebuild FTS5 index

4.2. **Implement consolidation engine** (8 hours)
- LLM-based memory analysis
- Contradiction detection
- Merge strategies (prefer newer, prefer higher confidence)
- Pruning strategies (age, retrieval count, TTL)

4.3. **Add consolidation tools** (2 hours)
- `memory_consolidate(dry_run=True)`
- `memory_health_report()`
- `memory_resolve_conflicts(path_a, path_b)`

4.4. **Add periodic trigger** (2 hours)
- Time-based: every N hours
- Count-based: every M new memories
- Background execution (threading/async)
- Lock file to prevent concurrent runs

### Verification
- Test with sample memories containing duplicates and contradictions
- Verify consolidation produces correct merged output
- Test dry-run mode
- Test periodic trigger

## Phase 5: Bi-Temporal Memory and Quality Scoring

**Duration:** 2 days
**Priority:** MEDIUM
**Dependencies:** Phase 1

### Tasks

5.1. **Add temporal fields to memory frontmatter** (2 hours)
- `valid_from`, `valid_until`
- `superseded_by`
- Migration for existing memories

5.2. **Add TTL support** (2 hours)
- `ttl_hours` field in frontmatter
- Auto-expire during flush
- Default TTL by memory type

5.3. **Add quality scoring** (4 hours)
- Freshness score (decay by age)
- Retrieval count tracking
- Conflict score (contradicts other memories)
- Confidence score (from source)
- Composite utility score

5.4. **Add quality-based retrieval** (2 hours)
- Sort by utility score
- Filter by minimum quality
- Boost frequently retrieved memories

### Verification
- Test temporal queries: "what did we believe at time T?"
- Test TTL expiration
- Test quality scoring on sample data
- Test quality-based retrieval

## Phase 6: Prompt Engineering Patterns (from Qwen research)

**Duration:** 1 day
**Priority:** LOW (already created as skill)

The patterns from the Qwen llm-application-dev extension have been captured in:
- `prompt-engineering-patterns` skill
- Context engineering protocol in SOUL.md

Key patterns to apply during future development:
- Structured outputs with Pydantic schemas
- Chain-of-thought with self-verification
- Few-shot with dynamic example selection
- Progressive disclosure (simple → complex)
- Error recovery with fallback prompts
- Constitutional AI principles

---

## Total Estimated Effort

| Phase | Duration | Priority |
|-------|----------|----------|
| Phase 1: Self-Management Tools | 1-2 days | CRITICAL |
| Phase 2: Workspace-Scoped Memory | 1 day | HIGH |
| Phase 3: Write-Time Deduplication | 0.5 days | HIGH |
| Phase 4: Background Consolidation | 2-3 days | MEDIUM |
| Phase 5: Bi-Temporal + Quality | 2 days | MEDIUM |
| **Total** | **6.5-8.5 days** | |

## Recommended Order

1. **Phase 1 + Phase 3** (do together, ~2 days) — Unlocks agent autonomy
2. **Phase 2** (1 day) — Fixes workspace isolation
3. **Phase 4** (2-3 days) — Long-term memory health
4. **Phase 5** (2 days) — Advanced features

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Index inconsistency during delete/update | Medium | High | Atomic operations + index rebuild fallback |
| Workspace config breaking existing sessions | Low | Medium | Backward-compatible fallback chain |
| Consolidation daemon consuming too many tokens | Medium | Medium | Budget limits, dry-run mode, manual trigger option |
| Dedup threshold too aggressive | Medium | Low | Configurable threshold, dry-run mode |

## Sign-Off Checklist

Before implementation begins:
- [ ] SPEC-001 reviewed and approved
- [ ] SPEC-002 reviewed and approved
- [ ] Implementation plan reviewed
- [ ] Phase 1 test cases identified
- [ ] Rollback plan documented

After implementation:
- [ ] All tests pass (zero regressions)
- [ ] New features verified manually
- [ ] Documentation updated
- [ ] ADR written for significant architectural changes
