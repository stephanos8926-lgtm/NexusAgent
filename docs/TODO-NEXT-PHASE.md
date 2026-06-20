# TODO — Next Phase Ideas (2026-07-22)

## Priority 1: Memory System Polish
- [ ] Unify memory system — remove dead `Memory`/`MemoryManager` SQLite classes (only `HybridMemoryManager` is used)
- [ ] Add integration tests for DreamCycle end-to-end
- [ ] Add tests for ConsolidationEngine (duplicate/contradiction detection)
- [ ] Add tests for LLMRefinement layer
- [ ] Test coverage target: 80%

## Priority 2: Remaining Refactoring
- [ ] `tui/app.py` — Complete TUI split (screens, slash commands)
- [ ] `session/session.py` — Extract prompt building, approval flow
- [ ] `memory/memory_files.py` — Split into frontmatter, entity_ops, daily_log
- [ ] `memory/dream.py` — Split phases into separate modules
- [ ] `tools/register_all.py` — Self-describing tools pattern

## Priority 3: CI/CD
- [ ] Set up GitHub Actions for automated testing on every commit
- [ ] Add pre-commit hooks for ruff linting
- [ ] Add test coverage reporting (codecov or similar)

## Priority 4: Feature Work
- [ ] P0: MCP support — implement MCP client + server
- [ ] P0: Codebase indexing — add Tree-sitter + embedding index
- [ ] P1: Sandboxing — add subprocess sandboxing for tool execution
- [ ] P1: Skills/plugins — build extensible skill marketplace
- [ ] P2: IDE extension — VS Code extension
- [ ] P2: Structured logging — JSON logging with correlation IDs
- [ ] P3: Replace global singletons with DI container
- [ ] P3: Migrate from SQLite to PostgreSQL
- [ ] P3: NATS clustering
- [ ] P3: Multi-tenancy support

## Priority 5: Documentation
- [x] Update `CODEBASE_MAP.md` with current structure
- [x] Update `SEMANTIC_INDEX.md` with data flows and state management
- [x] Update `README.md` with memory v2 features
- [x] Update `CHANGELOG.md` with all recent work
- [x] Update `REFACTORING_PLAN.md` with completion status
- [ ] Fix `docs/ROADMAP/index.html` — pre-compile JSX for browser loading
- [ ] Add architecture overview docs
- [ ] Add memory system v2 user guide
- [ ] Add deployment guide for Hetzner/server setup

## Resources/Tools Needed
- [x] Dependency graph tool (ast-tools)
- [x] "Find all references" tool (ast-tools)
- [ ] Test failure grouping tool (group failures by root cause)
- [x] Shared task board for multi-agent coordination (Kanban)

## Workflow Improvements
- [x] Pre-flight dependency analysis before every extraction
- [x] Run tests after every single file change, not batches
- [x] Create "refactoring checklist" skill (extract-to-subpackage pattern)
- [x] Pin critical skills to prevent archival
