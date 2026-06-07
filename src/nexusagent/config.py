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
    tui_colors: str = Field(default="monokai")
    timeout: int = Field(default=30, ge=1)
    retry_limit: int = Field(default=3, ge=0)
    result_timeout: int = Field(default=300, ge=1)


class AuthConfig(BaseModel):
    master_secret_path: str = Field(default=".master.secret")
    keystore_path: str = Field(default="keystore.json")
    salt_path: str = Field(default=".master.salt")
    kdf_iterations: int = Field(default=100000, ge=1000)


class AgentConfig(BaseModel):
    default_model: str = Field(default="gemini-3.1-flash-lite")
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["read_file", "write_file", "run_shell"]
    )


class ConfigSchema(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    loop_threshold: int = Field(default=4, ge=1)
    post_research_retries: int = Field(default=4, ge=0)
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
                stripped = key[len(prefix) :]
                if "__" in stripped:
                    parts = stripped.split("__")
                    target = current_level
                    for part in parts[:-1]:
                        target = target.setdefault(part.lower(), {})
                    target[parts[-1].lower()] = value
                else:
                    current_level[stripped.lower()] = value

    # Systematic overrides for each section
    for section in ["server", "client", "auth", "agent"]:
        section_data = raw_data.get(section, {})
        override_from_env(f"NEXUS_{section.upper()}__", section_data, section_data)
        raw_data[section] = section_data

    # Global overrides
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
