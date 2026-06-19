# SPEC-004: Consolidation Daemon (Dream Cycle)

> **Status:** Draft
> **Date:** 2026-07-22
> **Author:** OWL (Lucien)
> **Depends:** ADR-006

---

## Goal

Implement a background consolidation daemon that maintains memory health by scanning for duplicates, pruning stale entries, and extracting patterns.

## Problem

Memories accumulate without maintenance. Duplicates proliferate, stale entries waste index space, and no pattern extraction occurs across entries.

## Solution

### Component 1: Dream Cycle Engine

**File:** `src/nexusagent/memory/dream.py` (new)

```python
class DreamCycle:
    """4-phase memory consolidation (inspired by Claude Code's auto-dream)."""
    
    async def run(self, memory_dir: str, dry_run: bool = False) -> dict:
        """Execute full dream cycle. Returns report."""
        # Phase 1: Scan
        scan_report = await self._scan(memory_dir)
        
        # Phase 2: Find patterns
        patterns = await self._find_patterns(scan_report)
        
        # Phase 3: Merge and prune
        if not dry_run:
            actions = await self._consolidate(scan_report, patterns)
        else:
            actions = self._preview_actions(scan_report, patterns)
        
        # Phase 4: Trim index
        if not dry_run:
            await self._trim_index()
        
        return {"scan": scan_report, "patterns": patterns, "actions": actions}
```

### Component 2: Scan Phase

- Read all `bank/*.md` files
- Compute content hashes for deduplication
- Identify stale entries (>30 days or `valid_until` in past)
- Find entries with `quality_score < 0.3`
- Build report: `{total, duplicates, stale, low_quality, health_score}`

### Component 3: Pattern Extraction

- Analyze memory entries for recurring themes
- Extract observations: "User prefers X in 80% of cases"
- Store as `observation` type memories with `derived_from` links
- Uses LLM for synthesis (lightweight model)

### Component 4: Consolidation Actions

- Remove exact duplicates (keep highest-quality copy)
- Prune stale entries (archive to `bank/archive/` before deleting)
- Merge near-duplicates (combine content, preserve both sources in provenance)
- Update entity pages

### Component 5: Cron Integration

**File:** `src/nexusagent/infrastructure/config.py`

```python
# New config fields
dream_enabled: bool = True
dream_interval_hours: int = 24
dream_after_sessions: int = 5
dream_model: str = ""  # empty = use current model
dream_dry_run: bool = False
```

**Cron setup:** `hermes cron` triggers `dream_cycle.run()` for each configured workspace.

### Component 6: CLI Integration

```bash
nexusagent memory dream              # Run dream cycle
nexusagent memory dream --dry-run    # Preview only
nexusagent memory status             # Health report
```

## Files to Create/Modify

| File | Change |
|------|--------|
| `src/nexusagent/memory/dream.py` | New — DreamCycle engine |
| `src/nexusagent/infrastructure/config.py` | Add dream config fields |
| `src/nexusagent/interfaces/cli.py` | Add `memory dream` subcommand |
| `src/nexusagent/tools/register_all.py` | Add `memory_dream` tool |

## Tests

1. `test_dream_scan` — Scan identifies duplicates and stale entries
2. `test_dream_patterns` — Pattern extraction finds recurring themes
3. `test_dream_consolidate` — Consolidation removes duplicates, prunes stale
4. `test_dry_run` — Dry run previews without modifying
5. `test_health_report` — Health score computed correctly

## Acceptance Criteria

- [ ] Dream cycle runs via cron or manual trigger
- [ ] Duplicates removed, stale entries pruned
- [ ] Pattern observations created with provenance
- [ ] Dry-run mode previews without modifying
- [ ] Health report shows improvement after consolidation
- [ ] All tests pass with zero regressions
