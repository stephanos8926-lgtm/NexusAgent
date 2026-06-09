# Installation

## Prerequisites

- Python 3.13+
- NATS Server (optional, for multi-agent features)
- ripgrep (optional, for code search)

## Install from source

```bash
git clone https://github.com/stevenpage/nexusagent.git
cd nexusagent
pip install -e ".[dev]"
```

## Install dependencies

```bash
# Core dependencies
pip install -e .

# Development dependencies
pip install -e ".[dev]"
```

## Verify installation

```bash
# Run tests
make test

# Check linting
make lint

# Start dev server
make dev
```

## Docker (optional)

```bash
docker build -t nexusagent .
docker run -p 8000:8000 nexusagent
```
