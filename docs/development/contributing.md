# Contributing

## Development Setup

```bash
git clone https://github.com/stevenpage/nexusagent.git
cd nexusagent
pip install -e ".[dev]"
pre-commit install
```

## Code Standards

- **Linting**: `make lint` (ruff)
- **Formatting**: `make format` (ruff)
- **Type checking**: `make typecheck` (mypy)
- **Tests**: `make test` (pytest)
- **All checks**: `make all`

## Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON/TOML validation
- Ruff linting and formatting
- Mypy type checking
