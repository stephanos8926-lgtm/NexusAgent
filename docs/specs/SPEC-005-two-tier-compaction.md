# SPEC-005: Two-Tier Context Compaction

> **Status:** Draft
> **Date:** 2026-07-22
> **Author:** OWL (Lucien)
> **Depends:** ADR-007, Phase 1 (session wiring)

---

## Goal

Replace the current single-pass compaction with a two-tier system: lightweight observation masking every turn (Tier 1) + background LLM summarization when context exceeds 75% capacity (Tier 2).

## Problem

Current compaction (in `CompactionPipeline`) uses a single graduated approach: clear old tool results → microcompact → summarize → emergency truncation. This is:
- **Lossy** — once summarized, original messages are gone
- **Blocking** — compaction stalls agent inference
- **Unpredictable** — summary volume varies by model/run

## Solution

### Tier 1 — Observation Masking (every turn, synchronous, <10ms)

Replace tool outputs older than 5 turns with stubs. No LLM call.

**Before:**
```
[Tool output: read_file — 200 lines of code...]
[Tool output: shell — 50 lines of output...]
[Tool output: search_code — 30 results...]
```

**After (older than 5 turns):**
```
[Tool output: read_file(src/auth.py) — 3 lines]
[Tool output: shell(git status) — 1 line]
[Tool output: search_code("auth") — 5 matches]
```

**Rules:**
- Keep all user messages verbatim
- Keep all assistant messages verbatim
- Keep tool call metadata (name, args) — only truncate tool results
- Keep last 5 turns' tool results at full length
- Replace older tool results with: `[{tool_name}({args_summary}) — {line_count} lines]`
- Orphaned tool results (tool_use without matching tool_result) are removed

### Tier 2 — Background Summarization (async, when context > 75%)

Triggered when estimated context tokens exceed `compaction_tier2_threshold` (default: 75% of context window).

**Design (inspired by PicoClaw + parallel compaction research):**

```
Context Pressure Check (after each turn)
  │
  ├─ < 75% → No action
  ├─ 75-90% → Launch background summarization (non-blocking)
  └─ > 90% → Blocking compaction (emergency, with fresh tail protection)
```

**Background summarization process:**
1. Identify compaction candidates: messages older than fresh_tail (last 32)
2. Group into blocks of ~16k tokens
3. For each block, call LLM to generate ~2k token summary
4. Replace original messages with summary + pointer to source
5. Source messages preserved in SQLite (recoverable via `session_search`)

**Fresh tail protection:** Last 32 messages are NEVER summarized. Always kept verbatim.

**Summary format:**
```json
{
  "type": "summary",
  "depth": 1,
  "content": "Summary of conversation arc...",
  "source_messages": [123, 124, 125, 126],
  "timestamp": "2026-07-22T10:00:00Z",
  "model": "gemini-3.1-flash-lite"
}
```

### Configuration

```python
# config.py additions
compaction_tier2_threshold: float = 0.75        # % of context window
compaction_tier2_fresh_tail: int = 32           # messages never summarized
compaction_tier2_block_size: int = 16000         # tokens per block
compaction_tier2_summary_size: int = 2000        # tokens per summary
compaction_tier2_model: str = ""                 # empty = use current model
compaction_tier2_enabled: bool = True
```

## Files to Modify

| File | Change |
|------|--------|
| `src/nexusagent/memory/compaction.py` | Add `TwoTierCompactor` class with Tier 1 + Tier 2 |
| `src/nexusagent/core/session/session.py` | Wire Tier 1 in `send()`, Tier 2 trigger after agent response |
| `src/nexusagent/infrastructure/config.py` | Add compaction config fields |
| `src/nexusagent/interfaces/cli.py` | Add `--compaction-threshold` flag |

## Tests

1. `test_tier1_masks_old_tool_outputs` — Tool results older than 5 turns are stubbed
2. `test_tier1_preserves_recent_tool_outputs` — Last 5 turns' results kept verbatim
3. `test_tier1_preserves_user_assistant_messages` — Never masked
4. `test_tier2_triggers_at_threshold` — Background summarization launches at 75%
5. `test_tier2_does_not_block_agent` — Async, non-blocking
6. `test_tier2_fresh_tail_protection` — Last 32 messages never summarized
7. `test_tier2_summary_has_source_pointers` — Can recover original messages
8. `test_emergency_compaction_at_90` — Blocking compaction when critical
9. `test_config_defaults` — Config fields have correct defaults

## Acceptance Criteria

- [ ] Tool outputs older than 5 turns are stubbed (Tier 1)
- [ ] Background summarization triggers at 75% context (Tier 2)
- [ ] Agent is never blocked by Tier 1 (<10ms)
- [ ] Agent is never blocked by Tier 2 (async)
- [ ] Last 32 messages are never summarized
- [ ] Source messages recoverable via session_search
- [ ] All tests pass with zero regressions
- [ ] Config fields have correct defaults
