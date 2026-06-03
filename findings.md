# Project Findings: Architecture Design

## Production Refactor Architecture
- **Backend Service:** FastAPI API + NATS Worker, co-located in a single process.
- **Client Strategy:** Modular, SDK-based Clients (CLI, TUI, Web-UI via Gradio).
- **Communication:** Shared SDK Pydantic models for type-safe interaction.
- **Authentication:** Custom initialization wizard (`.master.secret`), `keystore.json` for API key management, FastAPI Security dependencies.
- **Error Handling:** Global middleware, logging middleware, and TUI/Web-UI interactive modal error handling.
- **Config Management:** Centralized `config/` directory with YAML + Env Var overrides.
