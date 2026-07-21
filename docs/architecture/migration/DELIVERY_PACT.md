# NexusManager Migration Delivery Pact

> **Effective:** 2026-07-21 16:50 EDT
> **Owner:** Lucien (autonomous)
> **Goal:** Ship NexusManager through all 12 migration phases. Enterprise livelihood depends on it.

## Runway
| # | Phase | Status | ETA |
|---|-------|--------|-----|
| 1 | Runtime Foundation | ✅ Delivered | — |
| 2 | Durable Task | ✅ Delivered | — |
| 3 | Event-Driven Core | ✅ Delivered | — |
| 4 | LangGraph Worker | ✅ Delivered | — |
| 5 | Planner & Orchestrator | ✅ Delivered | — |
| 6 | DAG Execution Engine | ✅ Delivered | — |
| 7 | POL Control Plane | 🔄 Jules `661066892122530817` | ~45 min |
| 8 | Capability Security Model | 🟡 Next | +30 min after 7 lands |
| 9 | Memory Evolution (4-layer) | 🟡 Queued | +30 min after 8 |
| 10 | Observability & Reliability | 🟡 Queued | +30 min after 9 |
| 11 | Production Readiness | 🟡 Queued | +30 min after 10 |
| 12 | Master Finish (version + RAA + tag) | 🟡 Inline | +30 min after 11 |

## Throughput Rules
1. **Sequencing is sacred.** Phase N+1 reads code from phase N. No parallel phase implementations.
2. **Zero-failure baseline.** If a merge breaks tests, fix before dispatching the next phase.
3. **Jules quota.** 15 PRs/day. We have ~10 left. Each phase = 1 PR.
4. **Mistral/Vibe:** idle until fresh Vibe CLI key arrives.
5. **Dev VM:** parallel test audit + heavy compute.

## Per-Phase Loop
1. `jules.create_session(prompt=phase_spec)`
2. Wait for PR (poll session or watch live transcript)
3. Merge PR with `-X theirs` if minor conflicts; resolve manually if structural
4. Run full test suite on workstation (`tests/` minus e2e/bus/graph_nodes)
5. Fix regressions inline (≤5 file patches)
6. Push master
7. Update `docs/devboard/README.md` (mark phase delivered)
8. Commit + push
9. Dispatch next phase

## Per-Phase Risks (contingency prep)
| Phase | Risk | Mitigation |
|-------|------|------------|
| 7 | POL receiver wiring | Run `tests/test_*.py` for pol_subscriber specifically |
| 8 | Tool-call regression | Diff-test pre/post against `src/nexusagent/tools/registry/` |
| 9 | Memory module churn | Backup `.nexusagent/memory` before, diff after |
| 10 | Plugin territory (Honcho, etc.) | Keep observability minimal — counters + structured logs only |
| 11 | Config refactor touching infra | Test infra validators first, then config polish |

## When Each Phase Lands — Verify
```
cd ~/Workspaces/NexusAgent
git pull origin master
.venv/bin/python3 -m pytest tests/ -q --timeout=30 \
  --ignore=tests/api_e2e_project \
  --ignore=tests/test_e2e_production.py \
  --ignore=tests/test_graph_nodes.py \
  --ignore=tests/test_bus.py
```

Acceptable state: `XXX passed, Y skipped, Z errors` where **Z = 0** and Y ≤ 9 (skips are intentional). Anything else = stop the run and fix.

## Phase 12 Finale Sequence
1. Bump version in `src/nexusagent/version.py`
2. Final master test run
3. `docs/devboard/README.md` → fully delivered view
4. `docs/SESSION_STATE.md` → final handoff
5. AGENTS.md → fresh state
6. Commit + push + tag `v0.6.0-phase12` (or current VERSION)
7. **RAA backup** to srv1: `rwa backup run --repo NexusAgent`
8. Celebrate Phase 12 in memory + channel.

## Out of Scope (Do Not Touch)
- TUI UX polish (Phase 5 overcooked; ship as-is)
- Doc pruning beyond spec requirements
- Any feature not in spec
- Mistral/Vibe until fresh key arrives
- External projects (RapidPrompt, ast-tools, etc. — different projects)

## Delivery Cadence
- **Daily checkpoint:** devboard update with `pass/fail per phase test set`
- **Per phase:** SESSION_STATE snapshot
- **Phase 12 done:** full release notes in `CHANGELOG.md`
