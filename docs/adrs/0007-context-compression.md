# ADR-007: Context Compression Strategy

> **Status:** Proposed
> **Date:** 2026-07-22
> **Deciders:** OWL (Lucien)
> **Context:** NexusAgent's current compaction is single-pass, lossy, and blocking. Research shows two-tier compaction is the production pattern.

## Problem

Current `CompactionPipeline` uses graduated strategies (clear old tool results → microcompact → summarize → truncation) that are:
- **Lossy** — once summarized, original messages are irrecoverable from context
- **Blocking** — compaction stalls agent inference
- **Unpredictable** — summary volume varies by model/run

## Decision

Adopt **two-tier compaction** based on PicoClaw's pattern and parallel compaction research.

### Tier 1 — Observation Masking (every turn, synchronous, <10ms)
- Replace tool outputs older than 5 turns with stubs
- No LLM call required
- Handles 80% of context bloat

### Tier 2 — Background Summarization (async, when context > 75%)
- Triggered when estimated tokens exceed configurable threshold
- Runs in background goroutine/task (doesn't block agent)
- Fresh tail protection: last 32 messages never summarized
- Source messages preserved in SQLite (recoverable via session_search)

## Consequences

**Positive:**
- Context bounded without losing reasoning chain
- Agent never waits for Tier 2 compaction
- Predictable summary volume (configurable block size)
- Original messages always recoverable

**Negative:**
- Tier 2 requires LLM API calls (cost)
- Summary quality varies by model
- Adds complexity to session code

**Mitigations:**
- Use configurable lightweight model for Tier 2
- Dry-run mode to preview before committing
- Disable Tier 2 if context window is large enough

## Alternatives Considered

1. **Single-pass summarization** (current) — Rejected: lossy, blocking
2. **DAG-based compression** (CMV paper) — Deferred: too complex for v1
3. **Parallel compaction** (arXiv 2605.23296) — Partially adopted: async Tier 2
4. **Observation masking only** — Insufficient: doesn't handle large tool outputs

## Related

- SPEC-005: Two-Tier Context Compaction
- ADR-006: Memory System Architecture
