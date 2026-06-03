# Local Development Guide

This guide provides instructions for setting up and working on the NexusAgent codebase.

## Development Workflow

### 1. Environment Configuration
Always use a virtual environment. We recommend using `uv` or `venv`.
Ensure the `NEXUS_MODE` environment variable is set correctly:
- For local development, use: `export NEXUS_MODE=DEVELOPMENT`
- For testing production behavior, use: `export NEXUS_MODE=PRODUCTION`

### 2. Running Tests
We use `pytest` for all testing.

**Run all tests:**
```bash
pytest
```

**Run unit tests only:**
```bash
pytest tests/unit
```

**Run with coverage report:**
```bash
pytest --cov=src/nexusagent --cov-report=term-missing
```

### 3. Linting and Formatting
We use `ruff` for all linting and formatting tasks.

**Check for linting errors:**
```bash
ruff check src/ tests/
```

**Automatically format code:**
```bash
ruff format src/ tests/
```

### 4. Debugging
- **LogLevels:** Use the `NEXUS_DEBUG=true` environment variable to enable verbose debug logging across all channels.
- **Python Debugger:** We recommend using `pdb` or an IDE-integrated debugger (like VS Code's debugger) for deep-dive analysis.

## Troubleshooting

- **NATS Connection Errors:** Ensure your NATS server is running and accessible at the URL specified in `config/nexusagent.yaml`.
- **Missing Dependencies:** If you encounter import errors, ensure you have installed the project in editable mode: `pip install -e .`.
- **Permission Errors (Journald):** If testing `journald` integration on a local machine, you may need `sudo` or specific system configuration to access `/dev/log`.

---
*Part of the NexusAgent Developer Documentation.*
