# Contributing to NexusAgent

Thanks for your interest in contributing!

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Getting Started

```bash
git clone git@github.com:stephanos8926-lgtm/NexusAgent.git
cd NexusAgent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Development Guidelines

- **Python 3.13+** with strict type hints
- **Ruff** for linting and formatting
- **pytest** with asyncio support for tests
- Follow conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- All new features require tests

## Architecture

NexusAgent uses a hybrid file+vector memory system with:
- FileMemory (canonical storage, git-backed)
- HybridMemoryIndex (SQLite FTS5 + sqlite-vec)
- DreamCycle for background consolidation
- CompactionPipeline for context window management

## Pull Requests

1. Ensure tests pass: `python3 -m pytest`
2. Lint clean: `ruff check src/ tests/`
3. Update CHANGELOG.md
4. Link related issues
