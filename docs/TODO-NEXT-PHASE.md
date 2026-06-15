# TODO — Next Phase Ideas (2026-07-19)

## Priority 1: Integration Testing & Bug Fixing
- [ ] Fix TUI rendering bugs (word wrapping, tool call display)
- [ ] Build test harness for full-stack integration tests (server + worker + TUI)
- [ ] Unify memory system (SQLite + file + vector → single HybridMemoryManager)
- [ ] Add end-to-end tests for token streaming pipeline

## Priority 2: CI/CD
- [ ] Set up GitHub Actions for automated testing on every commit
- [ ] Add pre-commit hooks for ruff linting
- [ ] Add test coverage reporting

## Priority 3: Remaining Refactoring
- [ ] server.py → routes + websocket (354L, low priority — skip for now)
- [ ] worker.py and session.py are now split ✅

## Priority 4: Feature Work
- [ ] Search providers (verify Exa/Tavily are actually wired and working)
- [ ] Memory system unification
- [ ] TUI theme customization UI
- [ ] Agent configuration UI in TUI

## Resources/Tools Needed
- [ ] Dependency graph tool (visualize import relationships before refactoring)
- [ ] "Find all references" tool (find every file that imports from a module)
- [ ] Test failure grouping tool (group failures by root cause)
- [ ] Shared task board for multi-agent coordination (prevent conflicts)

## Workflow Improvements
- [ ] Pre-flight dependency analysis before every extraction (grep imports TO/FROM)
- [ ] Run tests after every single file change, not batches
- [ ] Create "refactoring checklist" skill (codify the extract-to-subpackage pattern)
- [ ] Pin critical skills to prevent archival by Hermes system
