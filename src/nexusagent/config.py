# src/nexusagent/config.py
import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    nats_url: str = Field(default="nats://localhost:4222")
    db_path: str = Field(default="nexus.db")
    api_port: int = Field(default=8000, ge=1, le=65535)
    worker_threads: int = Field(default=4, ge=1)
    nats_reconnect_wait: int = Field(default=2, ge=0)
    nats_max_reconnects: int = Field(default=60, ge=0)


class ClientConfig(BaseModel):
    tui_theme: str = Field(default="textual-dark")
    timeout: int = Field(default=30, ge=1)
    retry_limit: int = Field(default=3, ge=0)
    result_timeout: int = Field(default=300, ge=1)
    # API key for TUI WebSocket connection (read from env NEXUS_CLIENT__API_KEY)
    api_key: str = Field(default="")


class AuthConfig(BaseModel):
    master_secret_path: str = Field(default=".master.secret")
    keystore_path: str = Field(default="keystore.json")
    salt_path: str = Field(default=".master.salt")
    kdf_iterations: int = Field(default=100000, ge=1000)


class AgentConfig(BaseModel):
    default_model: str = Field(default="gemini-3.1-flash-lite")
    primary_provider: str = Field(default="gemini")
    gemini_model: str = Field(default="gemini-3.1-flash-lite")
    openrouter_default_model: str = Field(default="openrouter/auto")
    openrouter_override_model: str | None = None
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["read_file", "write_file", "run_shell"]
    )
    max_tool_output_chars: int = Field(default=400, ge=100)
    max_conversation_history: int = Field(default=40, ge=4)
    compaction_enabled: bool = Field(default=True)


class PromptConfig(BaseModel):
    """Configuration for the NEXUS.md prompt system."""
    # Path to the base prompt file (relative to project root)
    base_prompt_file: str = Field(default="config/NEXUS.md")
    # Whether to look for a project-specific NEXUS.md in CWD
    load_cwd_prompt: bool = Field(default=True)
    # Maximum @file chain depth (prevents infinite recursion)
    max_chain_depth: int = Field(default=8, ge=1, le=32)
    # Maximum file size for @file injection (bytes)
    max_inject_file_size: int = Field(default=262144, ge=1024)  # 256KB
    # Whether to enable @file injection in chat input
    chat_file_injection: bool = Field(default=True)
    # Number of recent sessions to summarize for context injection
    session_history_count: int = Field(default=5, ge=0, le=20)
    # Max chars per session summary
    session_summary_max_chars: int = Field(default=2000, ge=200)


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(
        default="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


class ConfigSchema(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    # Back-compat: top-level log_level maps to logging.level
    log_level: str = Field(default="INFO")


def get_project_root() -> Path:
    # Resolve root relative to this file: src/nexusagent/config.py -> project_root
    return Path(__file__).parent.parent.parent.absolute()


def load_config(config_file: str = "config/nexusagent.yaml") -> ConfigSchema:
    config_path = get_project_root() / config_file

    raw_data = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                raw_data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config file {config_path}: {e}")
    else:
        logger.warning(f"Configuration file not found at {config_path}, using defaults.")

    def override_from_env(prefix: str, data: dict, current_level: dict):
        for key, value in os.environ.items():
            if key.startswith(prefix):
                stripped = key[len(prefix):]
                if "__" in stripped:
                    parts = stripped.split("__")
                    target = current_level
                    for part in parts[:-1]:
                        target = target.setdefault(part.lower(), {})
                    target[parts[-1].lower()] = value
                else:
                    current_level[stripped.lower()] = value

    # Systematic overrides for each section
    for section in ["server", "client", "auth", "agent", "prompt", "logging"]:
        section_data = raw_data.get(section, {})
        override_from_env(f"NEXUS_{section.upper()}__", section_data, section_data)
        raw_data[section] = section_data

    # Back-compat: NEXUS_LOG_LEVEL -> logging.level
    if "log_level" in raw_data and "logging" not in raw_data:
        raw_data.setdefault("logging", {})["level"] = raw_data["log_level"]

    # Global overrides (NEXUS_SERVER__API_PORT etc.)
    override_from_env("NEXUS_", raw_data, raw_data)

    try:
        config = ConfigSchema(**raw_data)

        # Resolve relative paths to absolute paths
        root = get_project_root()
        config.server.db_path = (
            str(root / config.server.db_path)
            if not Path(config.server.db_path).is_absolute()
            else config.server.db_path
        )
        config.auth.master_secret_path = (
            str(root / config.auth.master_secret_path)
            if not Path(config.auth.master_secret_path).is_absolute()
            else config.auth.master_secret_path
        )
        config.auth.keystore_path = (
            str(root / config.auth.keystore_path)
            if not Path(config.auth.keystore_path).is_absolute()
            else config.auth.keystore_path
        )
        config.auth.salt_path = (
            str(root / config.auth.salt_path)
            if not Path(config.auth.salt_path).is_absolute()
            else config.auth.salt_path
        )

        return config
    except ValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


# Singleton settings instance
settings = load_config()
