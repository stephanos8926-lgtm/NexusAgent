# ADR 0002: Project Structure and Build Modes

## 1. Status
Accepted

## 2. Context
The NexusAgent project requires a robust, scalable, and maintainable structure suitable for enterprise-grade applications. It needs to support multi-user collaboration in a GitHub repository, adhere to Python community best practices, and enable clear separation of concerns for different development, testing, and production environments.

Key drivers for this decision include:
- **Scalability:** The project is expected to grow, requiring a modular and organized codebase.
- **Maintainability:** Clear boundaries between components, easy onboarding for new developers.
- **Collaboration:** Facilitate multiple developers working concurrently without stepping on each other's toes.
- **Deployment:** Standardized build artifacts and deployment processes for different environments.
- **Quality Assurance:** Reliable testing (unit, integration, E2E) across environments.
- **Python Ecosystem:** Alignment with modern Python packaging and project layout best practices (e.g., PEP 517/518, `src/` layout).

## 3. Decision
We will adopt a standardized project structure that prioritizes modularity, testability, and CI/CD friendliness. Build mode separation will be achieved through a combination of environment variables and configuration management, ensuring a single codebase can be adapted to various environments.

### 3.1. Project Layout (`src/` layout)
All importable Python source code will reside under a top-level `src/` directory, containing a single package named `nexusagent`. This prevents accidental imports of development files during testing and ensures consistency with distributed packages.

```
nexusagent/
├── .github/              # GitHub-specific files (workflows, issue templates)
├── config/               # Application-wide static configuration files (e.g., nexusagent.yaml)
├── deployment/           # Deployment scripts, container definitions (Docker, Systemd)
├── docs/                 # Project documentation
│   ├── adrs/             # Architecture Decision Records
│   ├── specs/            # Technical Specifications
│   └── ...               # Other documentation (user guides, API reference)
├── src/
│   └── nexusagent/       # Main Python package
│       ├── __init__.py
│       ├── auth.py
│       ├── bus.py
│       ├── cli.py
│       ├── config/       # (Moved from main nexusagent/ folder if needed) Config-related code
│       ├── config.py
│       ├── emitter.py    # NexusTelemetry emitter (new)
│       ├── graph.py
│       ├── keystore.py
│       ├── models.py
│       ├── sdk.py
│       ├── server/       # FastAPI server specific components (e.g., middleware, routers)
│       │   ├── __init__.py
│       │   └── middleware.py
│       ├── server.py
│       ├── telemetry/    # NexusTelemetry package (new, detailed in 0001-telemetry-system-design.md)
│       │   ├── __init__.py
│       │   ├── channels.py
│       │   ├── config.py
│       │   ├── context.py
│       │   ├── emitter.py
│       │   ├── models.py
│       │   └── subscribers.py
│       ├── tools/
│       ├── tui.py
│       ├── web_ui.py
│       └── worker.py
├── tests/                # All test categories (unit, integration, e2e)
│   ├── unit/
│   │   └── nexusagent/
│   │       └── ...
│   ├── integration/
│   │   └── ...
│   └── e2e/
│       └── ...
├── .gitignore            # Git ignored files
├── pyproject.toml        # Project metadata, dependencies, build config, tool config
├── README.md             # Project overview
├── LICENSE               # Project license
└── ...                   # Other root-level config (e.g., .env, .editorconfig)
```

### 3.2. Build Mode Separation
Build modes will be primarily controlled by the `NEXUS_MODE` environment variable, set to either `DEVELOPMENT` or `PRODUCTION`. This environment variable will influence how application configurations are loaded (e.g., log levels, database connections, external service endpoints) using a dedicated `ConfigManager` (which extends the existing `config.py` in `src/nexusagent/`).

### 3.3. Git and GitHub Integration
- **Branching Strategy:** We will adopt a GitHub Flow-like model, utilizing short-lived feature branches, Pull Requests (PRs) for code review, and merging into `main`.
- **CI/CD:** GitHub Actions will be used to automate linting, testing, building, and deploying the application based on branch protection rules.

### 3.4. Naming Conventions
Consistent naming will be enforced across the board, from directories and files to variables, functions, branches, and commit messages. Details will be specified in `tech_spec_project_structure_build_modes.md`.

## 4. Alternatives Considered
- **Flat Project Layout:** Rejected due to increased risk of import errors, poorer modularity for larger projects, and less clear separation of application code from project-level files.
- **Multiple `setup.py` / Custom Build Scripts:** Rejected in favor of a single `pyproject.toml` and PEP 517/518 compliant build system (`setuptools` or `hatchling`) for standardization and reduced complexity.
- **Hardcoded Environment Checks:** Rejected as it scatters environment-specific logic throughout the codebase, making it harder to manage and prone to errors. Centralized configuration driven by environment variables is preferred.

## 5. Consequences
- **Positive:** Improved clarity and discoverability of project components, simplified CI/CD pipelines, enhanced test isolation, better adherence to Python community standards, easier developer onboarding, and a solid foundation for future growth and advanced features. Consistent application behavior across environments due to explicit configuration management.
- **Negative:** Initial overhead in refactoring to the new structure and configuring build/CI processes. Requires strict adherence to conventions from all collaborators. Initial learning curve for `pyproject.toml` if developers are used to older packaging tools. However, these short-term costs are significantly outweighed by long-term benefits for an enterprise-grade project.
