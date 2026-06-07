# Contributing Guide

Thank you for your interest in contributing to NexusAgent! This project aims to build a professional-grade orchestration framework for AI agents.

## 🛠️ Development Setup

### Prerequisites
- **Python 3.13+**
- **NATS Server** (JetStream enabled, running on `nats://localhost:4222`)
- **Git**

### Installation
```bash
git clone https://github.com/NexusAgent/nexusagent.git
cd nexusagent
pip install -e .
```

### Environment Variables
NexusAgent uses a hierarchical configuration system. You can override any setting using environment variables with the `NEXUS_` prefix.

#### Global Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_LOG_LEVEL` | `INFO` | System-wide logging level (DEBUG, INFO, WARNING, ERROR) |
| `NEXUS_LOOP_THRESHOLD` | `4` | Max iterations for the agent reasoning loop |

#### Server Settings (`NEXUS_SERVER__`)
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_SERVER__NATS_URL` | `nats://localhost:4222` | NATS connection string |
| `NEXUS_SERVER__DB_PATH` | `nexus.db` | Path to SQLite state database |
| `NEXUS_SERVER__API_PORT` | `8000` | FastAPI server port |

#### Agent Settings (`NEXUS_AGENT__`)
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_AGENT__DEFAULT_MODEL` | `gemini-3.1-flash-lite` | Default LLM provider/model |
| `NEXUS_AGENT__ENABLED_TOOLS` | `read_file,write_file,run_shell` | Comma-separated list of active tools |

### Available Scripts
The system can be launched via the central hub (`main.py`) or via installed entry points.

| Command | Purpose | Equivalent Script |
|---------|---------|-------------------|
| `python main.py server` | Launch Backend Core | `nexus-server` |
| `python main.py tui` | Launch Terminal UI | `nexus` |
| `python main.py web-ui` | Launch Web Dashboard | `nexus-web` |
| `python main.py health` | System Connectivity Check | N/A |

### Testing
We use `pytest` for all verification.
```bash
# Run all tests
pytest

# Run async tests
pytest -n auto # if pytest-xdist is installed
```

### Code Style
- **Linting**: We use `ruff` for formatting and linting.
- **Typing**: `mypy` is used for strict static type checking.
- **Standard**: Follow the Google Python Style Guide.
- **Files**: Prefer many small files (200-400 lines) over monolithic modules.
