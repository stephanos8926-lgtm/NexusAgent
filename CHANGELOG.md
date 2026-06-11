# Changelog

## 2026-06-11 — Codebase Cleanup & Security Hardening

### Security
- Scrubbed `.master.salt`, `.master.secret`, `keystore.json`, `tests/buggy_code.py` from git history via `git filter-repo`
- Added `.gitignore` patterns: `*.db`, `*.log`, `*.secret`, `*.salt`, `keystore*`, `tests/buggy_code.py`
- Force-pushed all branches to propagate rewritten history

### Cleanup
- Removed 10 root-level cruft files (spam, logs, stale TODOs, LLM exports)
- Deleted `tui_legacy.py` (1195L monolithic TUI, replaced by `widgets/` modular system)
- Removed `venv_fix/` (legacy venv, 286MB)
- Removed `docs/superpowers/`, `docs/collab/`, `docs/development/`, `docs/specs/`
- Consolidated `docs/guides/` into `docs/` root
- Pruned `docs/plans/` from 10 files to 2 (latest roadmap + recent sprint)
- Merged 4 CODEBASE_MAP files into single `docs/CODEBASE_MAP.md`
- Deleted `codemaps/`, `docs/api/`, `docs/api_reference/`
- Removed 7 worktrees + 10 feature branches (freed ~17MB)
- Fixed `main.py` entrypoint (was 4-line stub, now delegates to CLI)
- Removed empty `__init__.py` files (3)
- Fixed hardcoded `sys.path` in tests (2 files)

### Features (from feat/track-a-feature-parity)
- Skills system — load custom skills from `~/.hermes/skills/` with YAML frontmatter
- Todo tools — `todowrite`/`todoread` for multi-step task tracking
- Responsive TUI — `Breakpoint` enum, `NO_COLOR` detection, SIGWINCH handler, `_is_ascii_terminal()`

### Test Fixes
- Fixed 14 pre-existing test failures:
  - 5 session/memory tests — agent invocation + environment context injection
  - 9 fs permission tests — workspace-safe temp paths
- Added DB init to `conftest.py` for server tests
- All 476 tests passing

### Documentation
- Updated `README.md` with current feature set and doc structure
- Updated `mkdocs.yml` nav to match consolidated layout
- Updated `docs/index.md` with new hierarchy
