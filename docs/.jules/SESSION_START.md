# Jules — Session Start Instructions

**MANDATORY: Read `docs/.jules/MEMORIES.md` at the START of EVERY session.**

This file contains 10 high-value permanent memories about the NexusAgent codebase including: environment setup, source layout, phase migration status, testing conventions, event system architecture, task model, LangGraph patterns, infrastructure topology, and critical anti-patterns to avoid.

**Setup ritual — do this first, every session:**
1. Read `docs/.jules/MEMORIES.md` (this file adjacent)
2. Run setup: `uv venv --python 3.13 && source .venv/bin/activate && uv pip install -e .`
3. Read the relevant phase spec from `docs/architecture/migration/` for your task
4. Read `docs/devboard/README.md` for current dispatch status
5. Verify test baseline: `PYTHONPATH=src:. python3 -m pytest tests/core/ -q --tb=no --asyncio-mode=auto`

**Before creating a PR:** verify `git diff-tree --no-commit-id -r HEAD --name-only | wc -l` > 0 — empty commits waste everyone's time.
