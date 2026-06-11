# Getting Started with NexusAgent

Welcome to the NexusAgent ecosystem! This guide will help you set up your local development environment and get your first agent orchestrator running.

## Prerequisites

Ensure you have the following installed:
- **Python 3.13+**
- **NATS Server** (Running on `nats://localhost:4222`)
- **Git**

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/NexusAgent/nexusagent.git
   cd nexusagent
   ```

2. **Set Up Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -e .
   ```

## Running a Quick Demo

Once installed, you can launch the default server:
```bash
nexus-server
```

Then, in a new terminal, use the SDK to submit a test task:
```python
from nexusagent.sdk import NexusSDK
from nexusagent.models import TaskSchema

sdk = NexusSDK()
task = TaskSchema(id="test-1", description="Hello, NexusAgent!")
result = sdk.submit_task(task)
print(result)
```

## Next Steps
- Explore the [Local Development Guide](local_development.md) for more advanced setup.
- Check out the [API Reference](../api/agent.md) to see all available endpoints.
- Contribute to the project by following our [Contributing Guide](https://github.com/NexusAgent/nexusagent/CONTRIBUTING.md).
