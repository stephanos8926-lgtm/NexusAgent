# Jules — Active Daily Task

> **Auto-rotating file. Updated by Lucien (orchestrator agent).**
> **Read FIRST after SESSION_START.md + MEMORIES.md.**

## Active Task: ship the next queued migration phase (Phase 9 Memory Evolution)

The **/docs/devboard/README.md** has the current phase status. Pick the highest-priority 🟡 Queued / 🔄 IN_PROGRESS phase and ship it.

### Reference Docs
- `docs/devboard/README.md` — current phase status + active task
- `docs/architecture/migration/DELIVERY_PACT.md` — sequencing rules, per-phase loop
- `docs/architecture/migration/0X-<phase>.md` — the spec for phase X
- `docs/.jules/MEMORIES.md` — crystalized permanent knowledge

### Iron Laws (NON-NEGOTIABLE)

🚫 **DO NOT** delete or rename any of these files (they are migration deliverables):

```
src/nexusagent/core/planner.py              # Phase 5
src/nexusagent/core/orchestrator.py         # Phase 5
src/nexusagent/core/dag.py                  # Phase 6
src/nexusagent/core/dag_engine.py           # Phase 6
src/nexusagent/core/pol.py                  # Phase 7
src/nexusagent/core/pol_subscriber.py       # Phase 7
src/nexusagent/core/events/pol_subscriber.py # Phase 7 (compat shim)
```

🚫 DO NOT revert `docs/devboard/README.md` or any phase-delivered README/devboard/SESSION_STATE docs.

🚫 DO NOT **ever** auto-create a PR with empty diff. Verify with:
```bash
git diff-tree --no-commit-id -r HEAD --name-only | wc -l   # MUST be > 0
```

🚫 DO NOT auto-PR if tests fail. Run first:
```bash
PYTHONPATH=src:. python3 -m pytest tests/ -q --timeout=30 \
  --ignore=tests/api_e2e_project \
  --ignore=tests/test_e2e_production.py \
  --ignore=tests/test_graph_nodes.py \
  --ignore=tests/test_bus.py
```
Baseline **must** show 0 failed and 0 errored before opening PR.

🚫 DO NOT skip migration phases. Each phase gates the next.

🚫 DO NOT import patterns or modules you have not personally read and understood in this session.

### Public API Contracts (PRESERVE ON REFACTOR)

`HybridMemoryManager` (Phase 9 will refactor internally; do **not** change this public surface):
- `__init__(workspace_dir, parent_memory_dir=None)`
- `initialize()` (sync)
- `remember(content, type, description, confidence, entities, ttl_hours, valid_from, valid_until, source_session_id, derived_from, related) -> str` (async)
- `recall(query, max_results, valid_from, valid_until) -> list[dict]` (async)
- `get_memory_context(query, max_results) -> str` (async)
- `flush(session_summary)` (async)
- `close()` (async)
- `inherit_from(parent_dir)` (async)
- `set_nats_memory_bus(nats_memory_bus)` (sync)
- `promote_to_parent(filter_fn) -> int` (sync, file lock)

Callers depending on this surface:
`session_base.py`, `session.py`, `tools/register_all.py`, `compaction.py`.

### Per-Phase Cycle (see DELIVERY_PACT.md for full)

1. Read the spec from `docs/architecture/migration/0X-...md`
2. Read existing code that the phase will integrate with
3. Plan + 7 audits (forward/reverse/adversarial/redteam/topdown/bottomup/completeness)
4. Implement in micro-steps
5. Tests under `tests/<phase>/` or `tests/<issue>/` —_must pass_
6. `ruff check src/ tests/` — must be clean
7. Auto-PR via Jules with `auto_pr=True`, branch from `master`

### When Done — Update

Reverse rotation: when your task lands as PR merged, edit this file:

1. Update the **Active Task** section above to the next phase from devboard
2. Update **Last Updated** row
3. Mark previous task ✅ in the Status Tracker

### Status Tracker (last edited: 2026-07-21)

| Date | Updated by | Active | Result |
|------|-----------|--------|--------|
| 2026-07-21 | Lucien (orchestrator) | Phase 8 Capability Security Model via Jules session `11705737674507167788` | ✅ COMPLETED |
