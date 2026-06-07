# LLXPRT: NexusAgent Orchestration Framework

## Project Overview
**NexusAgent** is a production-grade platform for the intelligent orchestration of multi-agent AI systems. It is designed to move beyond prototype-level agents by providing a robust infrastructure for communication, security, and persistence.

### Core Architecture
The system employs a **contract-first** design using a shared SDK and Pydantic models to ensure type safety between disparate components.

- **Orchestration Core**: A co-located **FastAPI** server and **NATS Worker**. The API handles external requests, while the Worker processes the actual agent logic in the background.
- **Messaging Bus**: Uses **NATS JetStream** for asynchronous, durable task submission and a Key-Value (KV) store for result retrieval.
- **Persistence Layer**: A SQLite database (via **SQLAlchemy/aiosqlite**) tracks the full lifecycle of every task (`PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `COMPLETED`/`FAILED`) and archives results.
- **Security**: Features an industrial-grade encryption system. A **Secret Wizard** handles initialization, utilizing PBKDF2 and AES-GCM with per-installation salts to secure the `keystore.json`.
- **Interfaces**:
    - **TUI**: A professional terminal interface built with **Textual**.
    - **Web UI**: An industrial-themed dashboard built with **Gradio**.
    - **SDK**: A Python client library for programmatic interaction.

## Building and Running

### Prerequisites
- Python 3.13+
- NATS Server (with JetStream enabled)

### Setup
```bash
pip install -e .
```

### Key Commands
The system is managed via the central hub `main.py`:

| Command | Description |
| :--- | :--- |
| `python main.py server` | Starts the Backend API and NATS Worker |
| `python main.py tui` | Launches the Terminal User Interface |
| `python main.py web-ui` | Launches the Web-based Control Center |
| `python main.py health` | Runs a connectivity check for DB and NATS |

### Deployment
For production environments, the system includes a `nexusagent.service` file for **systemd** registration to ensure background persistence and automatic restarts.

## Development Conventions

### Coding Standards
- **Type Safety**: Extensive use of Pydantic models for all data exchange.
- **Async First**: The entire backend is built on `asyncio` to handle high-concurrency messaging and database I/O.
- **Configuration**: Centralized configuration in `src/nexusagent/config.py` supporting YAML files and environment variable overrides (prefixed with `NEXUS_`).

### Testing
- **Framework**: Uses `pytest` and `pytest-asyncio`.
- **Verification**: E2E testing is focused on the "SDK $\rightarrow$ API $\rightarrow$ Worker $\rightarrow$ DB" pipeline.

### Project Structure
- `src/nexusagent/`: Core source code.
- `docs/`: Comprehensive technical documentation and ADRs.
- `tests/`: Integration and unit tests.
- `config/`: System configuration files.
