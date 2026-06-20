# Quick Start

## Prerequisites

- **Python 3.13+**
- **NATS Server** (optional, for multi-agent features — `nats-server -js`)
- **Git**

## Install

```bash
git clone https://github.com/stephanos8926-lgtm/NexusAgent.git
cd NexusAgent
pip install -e ".[dev]"
```

## Run the TUI

```bash
# Start NATS first (if using multi-agent features)
nats-server -js &

# Launch the TUI
python -m nexusagent
```

The TUI connects to the local server at `ws://127.0.0.1:8000`. On first launch it performs a version compatibility check.

### Version Preflight

```bash
# Check server compatibility
python -m nexusagent --check-server

# Skip version check
python -m nexusagent --skip-version-check
```

## Run Headless

```bash
# Single task
python -m nexusagent run "Fix the auth bug in server.py" -d /project

# With model override
python -m nexusagent run "Add tests for memory.py" -d /project --model gemini-2.0-flash
```

## Session Management

```bash
# List sessions
python -m nexusagent session list

# Memory management
python -m nexusagent session memory health
python -m nexusagent session memory stats
```

## Use the SDK

```python
from nexusagent.sdk import NexusSDK
from nexusagent.models import TaskSchema, TaskContract

sdk = NexusSDK()

# Submit a task
task = TaskSchema(id="task-1", description="Analyze the memory system")
result = sdk.submit_and_wait(task, timeout=120)
print(result.data)

# Spawn an isolated worker
contract = TaskContract(
    id="research-1",
    description="Research best practices for agent memory",
    working_dir="/home/user/project",
    model="gemini-2.0-flash",
    max_depth=2,
)
result = sdk.submit_and_wait(contract)
```

## Run Tests

```bash
# All tests
pytest tests/ -q

# With coverage
pytest tests/ --cov=src/nexusagent --cov-report=term-missing

# Specific test file
pytest tests/test_memory_e2e.py -v
```

## Configuration

Configuration is loaded from (in order):
1. `config/nexusagent.yaml` — project defaults
2. Environment variables (`NEXUS_*__`)
3. `~/.nexusagent/config.yaml` — user overrides

Key config sections:
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  nats_url: "nats://localhost:4222"

agent:
  default_model: "gemini-2.0-flash"
  max_depth: 3

memory:
  enabled: true
  extraction: true
  git: true
  workspace: "~/.nexusagent/memory"
```

## Next Steps

- [Architecture Overview](architecture/overview.md) — System design
- [Codebase Map](CODEBASE_MAP.md) — Module inventory and coupling analysis
- [Memory System v2](../src/nexusagent/memory/) — File+vector memory with dream cycle
- [ADRs](adrs/index.md) — Architecture decision records
