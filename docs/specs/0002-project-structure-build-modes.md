# Technical Specification: Project Structure and Build Modes

## 1. Introduction
This document details the implementation of the NexusAgent project structure and defines how different build and runtime modes will be managed. It provides prescriptive guidance for file organization, dependency management, CI/CD integration, and naming conventions to ensure a scalable, maintainable, and collaborative enterprise-grade project.

**Goals:**
- Establish a standardized `src/` based project layout adhering to Python best practices.
- Implement a robust system for managing build modes (`DEVELOPMENT`, `PRODUCTION`) using environment variables and configuration.
- Define clear conventions for Git and GitHub workflows to facilitate multi-user collaboration.
- Enforce strict naming conventions for files, directories, branches, and commit messages.
- Lay the groundwork for a standardized CI/CD pipeline.

**Non-Goals:**
- Full definition of all CI/CD pipelines beyond basic linting, testing, and build stages (detailed CI/CD jobs will be defined in `.github/workflows` as separate artifacts).
- Automatic rebranding scripts (handled by the Branding/Config Tech Spec).
- Support for legacy Python packaging tools (`setup.py`).

## 2. Project Directory Layout
The project will adopt the `src/` layout. The root directory will contain project-level metadata, configuration, and top-level organizational directories. All importable Python code will reside within `src/nexusagent/`.

```
nexusagent/
├── .github/                      # GitHub-specific configurations (workflows, issue templates)
│   └── workflows/                # GitHub Actions CI/CD workflows
├── config/                       # Application-wide static configuration files (e.g., nexusagent.yaml, default.py)
├── deployment/                   # Deployment manifests (Dockerfiles, Kubernetes, Systemd units)
├── docs/                         # All project documentation
│   ├── adrs/                     # Architecture Decision Records
│   ├── specs/                    # Technical Specifications
│   ├── guides/                   # Developer/User Guides, tutorials
│   ├── api_reference/            # Auto-generated API documentation (e.g., Sphinx output)
│   └── ...                       # Other documentation assets
├── src/
│   └── nexusagent/               # Main Python package
│       ├── __init__.py
│       ├── main.py               # Main application entry point for server, worker setup
│       ├── config.py             # Main configuration loading/management
│       ├── models/               # Pydantic data models for shared interfaces
│       │   ├── __init__.py
│       │   └── common.py         # Shared models (e.g., TaskSchema, ResultSchema)
│       ├── core/                 # Core business logic / agent components
│       │   ├── __init__.py
│       │   ├── agent.py          # Main agent orchestration logic
│       │   ├── graph.py          # LangGraph definitions
│       │   └── worker.py         # NATS worker implementation
│       ├── platform/             # Foundational technical concerns (frameworks)
│       │   ├── __init__.py
│       │   ├── auth.py           # Authentication manager
│       │   ├── keystore.py       # Secure key storage
│       │   ├── bus.py            # NATS message bus client
│       │   └── server/           # FastAPI server specific code
│       │       ├── __init__.py
│       │       ├── app.py        # FastAPI app instance and route definitions
│       │       └── middleware.py   # FastAPI middleware (e.g., TelemetryMiddleware)
│       ├── clients/              # Client-side implementations
│       │   ├── __init__.py
│       │   ├── sdk.py            # Public SDK interface
│       │   ├── cli.py            # Command Line Interface
│       │   ├── tui.py            # Terminal User Interface
│       │   └── web_ui.py         # Web User Interface (Gradio/FastAPI frontend)
│       └── telemetry/            # Dedicated NexusTelemetry library (as per ADR 0001)
│           ├── __init__.py
│           ├── models.py
│           ├── config.py
│           ├── channels.py
│           ├── context.py
│           ├── emitter.py
│           ├── decorators.py       # (Added for context binding e.g., @log_metrics)
│           └── subscribers.py
├── tests/                        # All tests, mirroring src/ structure
│   ├── unit/
│   │   └── nexusagent/
│   │       ├── models/
│   │       └── telemetry/
│   │           └── ...
│   ├── integration/
│   │   └── nexusagent/
│   │       ├── platform/
│   │       └── ...
│   └── e2e/
│       └── test_full_system.py
├── .gitignore                    # Specifies intentionally untracked files to Git
├── pyproject.toml                # Centralized project configuration, metadata, dependencies
├── README.md                     # Project overview, installation, quick start
├── LICENSE                       # Project's license information
├── requirements.txt              # (Optional) For direct `pip install` in environments where `pyproject.toml` is not fully processed by installers (e.g. some Docker stages)
└── .env                          # Example .env file for local development (ignored by Git)
```

## 3. `pyproject.toml` Configuration
`pyproject.toml` will be the single source of truth for:
- **Project Metadata:** `[project]` (name, version, description, `requires-python`, dependencies).
- **Build System:** `[build-system]` (`requires`, `build-backend` - e.g., `setuptools` as currently, or `hatchling` for new projects).
- **Tool Configuration:** `[tool.*]` sections for:
    - `pytest`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`.
    - `ruff`: Linting rules, code format settings.
    - `mypy`: Type checking configurations.
    - `setuptools.packages.find`: `where = ["src"]`.

**Example `pyproject.toml` modifications:**
```toml
# pyproject.toml
[project]
name = "nexusagent"
version = "0.1.0" # Dynamically updated by CI/CD based on git tags
description = "An enterprise-grade multi-agent orchestration framework."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "langgraph",
    "langgraph-checkpoint",
    "deepagents",
    "nats-py",
    "pyyaml",
    "patch-ng",
    "fastapi",
    "uvicorn",
    "pydantic>=2.0",
    "structlog",
    "python-json-logger" # For structured logging to journald via SysLogHandler
    # Consider 'systemd-python' for richer journald integration if SysLogHandler is insufficient
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
# Discover tests in the top-level 'tests' directory
testpaths = [
    "tests/unit",
    "tests/integration",
    "tests/e2e"
]
asyncio_mode = "auto" # For testing FastAPI async endpoints
python_files = "test_*.py"
addopts = "--cov=src/nexusagent --cov-report=xml --cov-report=term-missing"

[tool.ruff]
line-length = 120
target-version = "py313"
select = ["E", "W", "F", "I", "N", "D", "UP", "SIM"]
# Add rules for docstring format (e.g., D for pydocstyle)
# Further configuration for docstrings (e.g., Google style) goes here.

[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = true
warn_unused_ignores = true
# Path to source code
files = "src/"

[project.scripts]
nexus-server = "nexusagent.platform.server.app:run_server"
nexus-client = "nexusagent.clients.cli:main"
nexus = "nexusagent.clients.tui:main"
nexus-web = "nexusagent.clients.web_ui:create_ui"
```

## 4. Build Mode Implementation

### 4.1. Environment Variable Control
- **`NEXUS_MODE` (Required):** Set to `DEVELOPMENT` or `PRODUCTION` (default `DEVELOPMENT` in local context). Used by the `ConfigManager` to load environment-specific configurations.
- **`NEXUS_DEBUG` (Optional):** Set to `true` or `false` (default `false`). A runtime flag enabling enhanced debug logging regardless of `NEXUS_MODE`.

### 4.2. Centralized Configuration Loading
- The main `ConfigManager` (e.g., in `src/nexusagent/config.py`) will read these environment variables at application startup.
- It will load base configurations from `config/nexusagent.yaml` and allow environment-specific overrides (e.g., `config/development.yaml`, `config/production.yaml` if needed, or primarily via environment variables).

### 4.3. Docker Integration
Docker builds will utilize multi-stage builds. Build arguments (`--build-arg NEXUS_MODE=PRODUCTION`) and runtime environment variables (`-e NEXUS_MODE=PRODUCTION`) will inject mode information.

**Example `Dockerfile` excerpt:**
```dockerfile
# Dockerfile
ARG NEXUS_MODE=DEVELOPMENT
ENV NEXUS_MODE=$NEXUS_MODE

# ... build steps ...

CMD ["uvicorn", "nexusagent.platform.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 5. Git and GitHub Integration

### 5.1. Branching Strategy: GitHub Flow
- **`main` branch:** Protected, deployable-at-any-time, represents the latest stable release.
- **Feature branches:** Short-lived, created from `main`, implement a single feature/bug fix.
- **Pull Requests (PRs):** Mandatory for all code changes, require code review, automated CI checks must pass before merging.

### 5.2. `Pull Request` (PR) Guidelines
- PRs should be small, focused, and solve a single problem.
- Require at least one approving review.
- All CI checks (linting, testing, build) must pass.
- Clear, descriptive PR titles and descriptions, linking to issues.

### 5.3. CI/CD with GitHub Actions (`.github/workflows/`)
GitHub Actions will automate development workflows:
- **`ci.yaml`:** Runs linting (Ruff), type checking (MyPy), unit/integration tests (`pytest`), and builds the package on every push/PR to feature branches.
- **`cd.yaml`:** Triggered on merge to `main`, builds Docker images (tagged with version), pushes to container registry, and initiates deployment (e.g., to staging/production environments).
- **Automated Documentation Builds:** Triggered on merge to `main`, builds and publishes documentation (e.g., to GitHub Pages).

**Example `ci.yaml` excerpt:**
```yaml
# .github/workflows/ci.yaml
name: CI Build and Test
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.13' # Ensure consistent Python version
    - name: Install dependencies
      run: | 
        python -m pip install --upgrade pip
        pip install -e . "pytest>=7.0" "ruff" "mypy" "pytest-cov" # Install all dev dependencies
    - name: Run Ruff Lint and Format Checks
      run: ruff check src/ tests/
    - name: Run MyPy Type Checks
      run: mypy src/
    - name: Run Pytest and Coverage
      run: pytest
```

## 6. Strict Organizational Parameters: Naming Conventions

- **Project Root Directory:** `nexusagent` (kebab-case).
- **Python Package:** `nexusagent` (snake_case, matches project name).
- **Directories:** `snake_case` (e.g., `src`, `tests`, `docs`, `deployment`, `core`, `platform`, `clients`).
- **Python Modules/Files:** `snake_case.py` (e.g., `emitter.py`, `middleware.py`, `app.py`).
- **Classes:** `PascalCase` (e.g., `NexusTelemetryEmitter`, `TelemetryMiddleware`).
- **Functions/Methods:** `snake_case` (e.g., `log`, `emit`, `submit_task`).
- **Variables/Parameters:** `snake_case`.
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEVELOPMENT`, `NEXUS_MODE`).
- **Environment Variables:** `UPPER_SNAKE_CASE` with `NEXUS_` prefix (e.g., `NEXUS_MODE`, `NEXUS_NATS_URL`).
- **Branch Names:** `feature/<descriptive-name>`, `bugfix/<issue-number>`, `release/<version>`. Use kebab-case.
- **Commit Messages:** Imperative mood, present tense, concise summary line (e.g., `feat: Add NexusTelemetry core emitter`). Detailed body if needed.
- **Log Files:** If `FileSubscriber` is implemented, structured as `<service_name>_<channel>_<date>.log`.
- **Error Messages:** Consistent format `[ERROR_CODE] - Description. Further details: {key=value, ...}`. Error codes will be globally defined constants (e.g., `AUTH_001`, `TELEMETRY_002`).

## 7. Documentation Standards Enforcement
- All new code must include comprehensive docstrings adhering to Google Python Style Guide.
- ADRs will follow the defined template in `docs/adrs/`. (e.g. `00XX-topic-name.md`).
- Technical Specifications will follow their defined template in `docs/specs/`. (e.g. `00XX-topic-name.md`).
- Automated tools (`ruff`, `mypy`) will be configured to check for docstring presence and basic style adherence.
- Documentation builds (Sphinx/MkDocs) will be integrated into CI/CD.

## 8. Migration and Rollout Plan
1. **Refactor Codebase:** Move existing `src/nexusagent/*.py` files into the new structured subdirectories (e.g., `src/nexusagent/core/`, `src/nexusagent/platform/server/`).
2. **Update Imports:** Adjust all Python imports to reflect the new package structure.
3. **Update `pyproject.toml`:** Modify `[project.scripts]` and `[tool.setuptools.packages.find]` to reflect the new structure. Add Ruff and MyPy configurations.
4. **Implement CI/CD Workflows:** Create initial GitHub Actions for linting, type checking, and testing.
5. **Developer Onboarding:** Update `README.md` and create `CONTRIBUTING.md` to guide collaborators through the new structure and conventions.
6. **Progressive Adoption:** Introduce documentation templates and conventions incrementally, starting with new features.
