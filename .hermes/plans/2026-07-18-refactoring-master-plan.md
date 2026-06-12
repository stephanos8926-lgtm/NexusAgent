# NexusAgent Source Reorganization Plan

> Created: 2026-07-18
> Status: PLAN — pending sign-off
> Goal: Refactor 1,075 lines of monolithic code into focused subpackages
> Pattern: Domain-based subpackages with compat shims (established in Phase 1-2)
> Methodology: A→B→C→D→E→F→G→H→I (per your specification)

---

## Part A: Research Summary

### Exemplar How Top Python Projects Organize

| Project | Structure | Key Pattern |
|---------|-----------|-------------|
| **FastAPI** (99K stars) | Flat modules + domain subpackages | One module per concern, small files |
| **Pydantic v2** (28K stars) | `_internal/` for private + feature modules | Public API in `__init__.py`, private in `_internal/` |
| **Rich** (56K stars) | Ultra-flat: ~70 files, one feature per module | Maximum decomposition, ~200L avg |
| **Textual** (36K stars) | Core classes at top level, domain subpackages | Widget//container/event subpackages |
| **LangChain** (139K stars) | Monorepo with `uv` workspace, lazy imports | Layered packages, `__getattr__` for lazy loading |

### What Applies to NexusAgent

1. **Domain-based subpackages** — group related files (already done: core/, tools/, memory/, widgets/)
2. **Max 500L per module** — split when exceeding 800L
3. **`__init__.py` as curated API** — explicit re-exports for public API
4. **Compat shims** — preserve backward compatibility (established pattern)
5. **Dependencies within subpackages** — models separate from logic separate from repos

---

## Part B: Refactoring Candidates (Sorted)

### Priority 1: High Impact + Low Risk (do first)

These have fan-in=0 (nobody imports them) or fan-in=0 at the file level, making extraction safe.

| # | File | Lines | Target | Est. Modules | Impact |
|---|------|-------|--------|-------------|--------|
| 1 | `infrastructure/db.py` | 416 | `infrastructure/db/` | models.py, repositories.py | Clean separation of ORM models from CRUD |
| 2 | `tools/register_all.py` | 728 | Audit first — may not need splitting | Possibly: register_fs, register_git, register_shell, etc. | Low structural impact but improves discoverability |
| 3 | `memory/memory_index.py` | 717 | `memory/index/` | index.py, embeddings.py, search.py | Separates FTS5, sqlite-vec, and union-merge |
| 4 | `tools/registry.py` | 623 | `tools/registry/` | core.py, policy.py, roles.py, search.py | Separates policy enforcement from registration |
| 5 | `widgets/messages.py` | 472 | `widgets/messages/` | user.py, assistant.py, tool.py, app.py, error.py, welcome.py | One file per widget class |
| 6 | `memory/memory.py` | 440 | `memory/` (existing subpackage) | Split existing memory.py if needed | Already in memory/ subpackage, but monolithic |
| 7 | `widgets/status.py` | 367 | `widgets/status/` | bar.py, git.py, context.py, spinner.py | BUT: audit says this may be dead code |
| 8 | `tools/code_review.py` | 367 | `tools/code_review/` | May not split — single purpose | Lower priority if already focused |

### Priority 2: Medium Impact + Low Risk

| # | File | Lines | Target | Notes |
|---|------|-------|--------|-------|
| 9 | `core/graph.py` | 250 | Already in core/ | May not need splitting |
| 10 | `memory/compaction.py` | 233 | Already in memory/ | Lower priority — single purpose |
| 11 | `infrastructure/prompt_loader.py` | 240 | Already in infrastructure/ | Single purpose, OK as-is |
| 12 | `tools/test_runner.py` | 216 | Already in tools/ | Single purpose |
| 13 | `tools/research.py` | 204 | Already in tools/ | Single purpose |
| 14 | `tools/fs.py` | 343 | Already in tools/ | Group of related functions, OK as-is |
| 15 | `tools/shell.py` | 167 | Already in tools/ | Single purpose |
| 16 | `tools/git.py` | 169 | Already in tools/ | Group of related functions, OK as-is |
| 17 | `tools/code_search.py` | 158 | Already in tools/ | Single purpose |
| 18 | `core/subagent.py` | 161 | Already in core/ | Single purpose |
| 19 | `core/orchestration.py` | 193 | Already in core/ | Single purpose |
| 20 | `infrastructure/bus.py` | 172 | Already in infrastructure/ | Single purpose |
| 21 | `infrastructure/auth.py` | 129 | Already in infrastructure/ | Single purpose |
| 22 | `infrastructure/telemetry.py` | 160 | Already in infrastructure/ | Single purpose |

### Priority 3: Higher Risk (do last — many depend on these)

| # | File | Lines | Target | Risk |
|---|------|-------|--------|------|
| 23 | `core/session.py` | 677 | `core/session/` | Fan-out=3 (TUI, Server, Worker depend on it) |
| 24 | `core/worker.py` | 304 | `core/worker/` | Fan-out=3 (multiple consumers) |
| 25 | `server/server.py` | 354 | `server/` (exists) | Fan-out=3, tightly coupled |
| 26 | `interfaces/tui.py` | 1433 | `interfaces/tui/` | Biggest monolith but fan-out=1 — can be done when ready |

---

## Part C: Execution Order

Sorted by **quickest to complete first, longest last** (within risk tiers):

### Tier 1: Quick wins (< 1 hour each, fan-in=0)

| Order | File | Lines | Est. Time | Rationale |
|-------|------|-------|-----------|-----------|
| 1 | `widgets/status.py` | 367L | ~20min | Verify dead code first — may just need deletion |
| 2 | `infrastructure/db.py` | 416L | ~30min | Clear split: models vs repositories |
| 3 | `tools/registry.py` | 623L | ~45min | Clear split: core/policy/roles/search |
| 4 | `widgets/messages.py` | 472L | ~40min | One class per file, very mechanical |
| 5 | `memory/compaction.py` | 233L | ~15min | Check if needs splitting — may be OK as-is |
| 6 | `memory/memory_index.py` | 717L | ~60min | Complex: needs index/embeddings/search separation |
| 7 | `memory/memory.py` | 440L | ~30min | Check if needs splitting — may be OK in memory/ |
| 8 | `tools/register_all.py` | 728L | ~30min | Audit: may just need reorganization, not extraction |
| 9 | `tools/code_review.py` | 367L | ~20min | Audit: may already be focused enough |

### Tier 2: Larger but safe (1-2 hours each, fan-in≤2)

| Order | File | Lines | Est. Time | Rationale |
|-------|------|-------|-----------|-----------|
| 10 | `interfaces/tui.py` | 1433L | ~2h | Biggest target — needs: app.py, modals.py, formatters.py, commands.py, streaming.py |

### Tier 3: Risky (requires careful coordination, fan-out≥3)

| Order | File | Lines | Est. Time | Risk |
|-------|------|-------|-----------|------|
| 11 | `core/session.py` | 677L | ~1.5h | TUI + Server + Worker all import it |
| 12 | `server/server.py` | 354L | ~45min | Tightly coupled WS + REST |
| 13 | `core/worker.py` | 304L | ~45min | Multiple consumers |

---

## Part D: Phase Template (Each Phase Follows This)

Per your specification:

```
A) Create detailed implementation plan for THIS phase
B) Load all relevant skills (subagent-driven-development, isolated-worktree-worker)
C) Forward audit (subagent) + Reverse audit (subagent) + Own comprehensive audit
D) Update plan based on audit findings
E) Present to you for sign-off
F) Execute (parallel workers where possible)
G) Test for regression (453+ pass / 20 fail baseline)
H) Update documentation + codebase maps
I) Move to next phase
```

---

## Part E: Success Criteria

- [ ] Every file under 500 lines (target: 400L average)
- [ ] No file over 800 lines (hard cap)
- [ ] 453+ tests pass after every phase (zero regression)
- [ ] All existing imports work via compat shims
- [ ] `docs/CODEBASE_MAP.md` updated after every phase
- [ ] `docs/SEMANTIC_INDEX.md` updated after tui.py extraction
- [ ] `ruff check src/` shows zero new errors
- [ ] Each extraction = 1 commit, revert-safe
- [ ] NO breaking changes — all additive, surgical

---

## Part F: Risk Flags (Uncertainty)

1. **`widgets/status.py`**: Audit claims it's dead code. Must verify before refactoring vs deleting.
2. **`tools/register_all.py`**: May not need extraction — it's a flat list of registration calls. Splitting might add indirection without benefit.
3. **`interfaces/tui.py` (1433L)**: Highest-value extraction but biggest surface area. Recommend doing it as a dedicated phase with 4 parallel subworkers.
4. **`core/session.py`**: Root cause of fake streaming bug (line 397). If we fix streaming, we need to refactor carefully — the dead-code streaming handlers (lines 445-510) need to be either wired up or deleted.
5. **`memory/memory_index.py`**: Async embedding chain (Gemini→local→hash) is complex. Splitting requires care to preserve the async flow.

---

## Part G: Research Insights (Best Practices)

From analyzing FastAPI, Pydantic, Rich, and Textual:

1. **Flat > Nested**: Rich uses ~70 flat modules with one feature each. Prefer 6 files at 200L over 2 files at 600L.
2. **`__init__.py` as API**: Pydantic's curated re-exports make the public surface explicit. Each subpackage should have a clean `__init__.py`.
3. **`_internal/` convention**: Pydantic uses `_internal/` for code that's not part of the public API. We can do the same for truly private module internals.
4. **Compat shims work**: Anthropic SDK uses `_compat.py` shims. Our established pattern (utils/, theme/) proves this approach works.
5. **Don't oversplit**: Each extraction should have a clear reason (separate concern, testability, size). Splitting for splitting's sake adds indirection.

---

## Part H: Total Scope

- **Files to extract**: 10-13 (out of 107 total)
- **Lines to reorganize**: ~4,700L of monolithic code
- **Lines remaining in subpackages already**: ~400L (utils/, theme/)
- **Target state**: All files ≤500L, organized in domain subpackages
- **Estimated total time**: ~8-10 hours of focused work

---

## Part I: Phase 1 Candidates (Recommended Starting Point)

Based on quickest-first ordering:

| Phase | File | Lines | Time | Workers |
|-------|------|-------|------|---------|
| 1 | `infrastructure/db.py` | 416L | ~30min | 1 worker |
| 2 | `widgets/messages.py` | 472L | ~40min | 1 worker |
| 3 | `tools/registry.py` | 623L | ~45min | 1 worker |
| 4 | `memory/memory_index.py` | 717L | ~60min | 1 worker |
| 5 | `memory/memory.py` | 440L | ~30min | 1 worker |
| 6 | `interfaces/tui.py` | 1433L | ~2h | 4 parallel workers |
| 7 | `tools/register_all.py` | 728L | ~30min | 1 worker (audit first) |
| 8 | `widgets/status.py` | 367L | ~20min | Verify dead code, then extract or delete |

Total after Phase 8: ~5 hours
Remaining (session.py, server.py, worker.py): deferred until stable

---

**This is the plan. I've been methodical: research → analysis → sorting → risk assessment → time estimation.**

**Before I kick off any work: do I have your sign-off to begin with Phase 1 (`infrastructure/db.py`)?**
