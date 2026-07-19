"""Pydantic configuration schema for NexusAgent.

Provides ``ConfigSchema`` and its sub-models (``ServerConfig``, ``ClientConfig``,
``AuthConfig``, ``AgentConfig``, ``PromptConfig``, ``LoggingConfig``,
``HooksConfig``), plus ``load_config`` for three-tier configuration loading
(file → env vars → Pydantic defaults) and ``get_project_root`` /
``get_nexus_home`` path helpers.
"""

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load API keys from .env files into os.environ.

    Searches in order (later overrides earlier):
    1. ~/.nexusagent/.env (runtime data)
    2. <project_root>/.env (product repo — API keys committed to .gitignore)

    Only sets keys that are not already in os.environ (env vars win).

    NOTE: Hermes Agent keys are NOT loaded here. Hermes owns ~/.hermes/ —
    NexusAgent owns ~/.nexusagent/ and its project repo. API keys needed by
    the product must live in the product's .env (gitignored).
    """
    project_root = Path(__file__).parent.parent.parent.parent.absolute()
    env_paths = [
        Path.home() / ".nexusagent" / ".env",
        project_root / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    # Always override: project .env should win over parent env
                    os.environ[key] = value
        except Exception as exc:
            logger.debug("Failed to load %s: %s", env_path, exc)


# Load .env files at module import time (before settings singleton is created)
_load_dotenv()


class ServerConfig(BaseModel):
    """Server-side configuration for NATS, database, and API settings."""

    nats_url: str = Field(default="nats://localhost:4222")
    db_path: str = Field(default="nexus.db")
    api_port: int = Field(default=8000, ge=1, le=65535)
    worker_threads: int = Field(default=4, ge=1)
    nats_reconnect_wait: int = Field(default=2, ge=0)
    nats_max_reconnects: int = Field(default=60, ge=0)
    reload: bool = Field(default=False, description="Enable uvicorn --reload for development")
    # TLS settings (set via env: NEXUS_SERVER__TLS_CERTFILE, NEXUS_SERVER__TLS_KEYFILE)
    tls_certfile: str | None = Field(default=None, description="Path to TLS certificate file (PEM)")
    tls_keyfile: str | None = Field(default=None, description="Path to TLS private key file (PEM)")
    tls_enabled: bool = Field(
        default=True,
        description="Enable TLS for the API server (default: True for production security)",
    )

    shell_tool_approval_required: bool = Field(
        default=True, description="Require approval even in YOLO mode for shell tools"
    )


class ClientConfig(BaseModel):
    """Client-side configuration for the TUI (theme, timeouts, retries)."""

    tui_theme: str = Field(default="textual-dark")
    timeout: int = Field(default=30, ge=1)
    retry_limit: int = Field(default=3, ge=0)
    result_timeout: int = Field(default=300, ge=1)
    # API key for TUI WebSocket connection (read from env NEXUS_CLIENT__API_KEY)
    api_key: str = Field(default="")
    # Enable/disable responsive TUI behavior
    tui_responsive_enabled: bool = Field(default=True)


class AuthConfig(BaseModel):
    """Authentication configuration for master secret, keystore, and KDF parameters."""

    master_secret_path: str = Field(default="auth/.master.secret")
    keystore_path: str = Field(default="auth/keystore.json")
    salt_path: str = Field(default="auth/.master.salt")
    kdf_iterations: int = Field(default=100000, ge=1000)


class AgentConfig(BaseModel):
    """Agent runtime configuration (model, provider, compaction, images).

    Tool access is controlled via Agent role/policy (see nexusagent.tools.registry.policy),
    not via config. Default agent uses role="full", policy="permissive" (all tools available).
    """

    default_model: str = Field(default="gemini-2.5-flash")
    primary_provider: str = Field(
        default="gemini", description="LLM provider: 'gemini' or 'openrouter'"
    )
    # Primary model for Gemini provider (used when provider is "gemini")
    gemini_model: str = Field(default="gemini-2.5-flash")
    # Gemini API key (optional, defaults to GEMINI_API_KEY env var if not set)
    gemini_api_key: str | None = Field(
        default=None, description="Gemini API key (overrides GEMINI_API_KEY env var)"
    )
    openrouter_default_model: str = Field(default="google/gemini-2.5-flash-preview")
    openrouter_override_model: str | None = None
    max_tool_output_chars: int = Field(default=400, ge=100)
    max_conversation_history: int = Field(default=40, ge=4)
    compaction_enabled: bool = Field(default=True)
    yolo: bool = Field(default=False)
    memory_workspace: str | None = Field(
        default=None,
        description="Path to the workspace-scoped memory directory, overrides default memory location when set",
    )
    # Memory extraction
    memory_model: str = Field(
        default="",
        description="Model for memory extraction; empty string uses the current agent model",
    )
    # Git-backed memory
    memory_git_enabled: bool = Field(
        default=True, description="Enable git-backed memory persistence"
    )
    memory_git_auto_commit: bool = Field(
        default=True, description="Auto-commit memory changes after each write"
    )
    # Two-tier compaction
    compaction_tier2_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Fraction of context window to trigger tier-2 compaction (summarization)",
    )
    compaction_tier2_fresh_tail: int = Field(
        default=32,
        ge=1,
        description="Number of recent messages to preserve untouched during tier-2 compaction",
    )
    compaction_tier2_model: str = Field(
        default="",
        description="Model for tier-2 LLM summarization; empty string uses the current agent model",
    )
    # Dream cycle
    dream_cycle_interval: int = Field(
        default=20, ge=1, description="Number of turns between automatic dream cycle consolidations"
    )
    # NATS distributed memory
    nats_memory_enabled: bool = Field(
        default=True, description="Enable NATS-based distributed memory sharing across workers"
    )
    nats_memory_subject_prefix: str = Field(
        default="nexus.memory", description="NATS subject prefix for memory events"
    )
    nats_memory_filter_own_events: bool = Field(
        default=True, description="Filter out own session's memory events when receiving from NATS"
    )
    # LLM memory extraction
    llm_extraction_enabled: bool = Field(
        default=True, description="Enable LLM-powered memory extraction (replaces regex-based)"
    )
    llm_extraction_model: str = Field(
        default="gemini-2.5-flash",
        description="Model for LLM extraction; empty string uses the current agent model",
    )
    llm_extraction_min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for LLM-extracted facts",
    )
    # Image input settings
    max_image_size_mb: int = Field(default=10, ge=1, le=50)
    supported_image_types: list[str] = Field(
        default_factory=lambda: [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]
    )
    # LLM request resilience — without these, create_deep_agent's bare model
    # string goes through init_chat_model() with provider defaults, which for
    # several providers (including OpenRouter's OpenAI-compatible client) is
    # NO timeout at all. A slow/hanging free-tier endpoint then blocks the
    # entire turn indefinitely with no exception ever raised, leaving the
    # session stalled with nothing surfaced to the user.
    llm_request_timeout: float = Field(
        default=90.0,
        gt=0,
        description="Max seconds to wait for an agent LLM response before raising TimeoutError",
    )
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        description="Number of automatic retries on transient LLM request failures",
    )


class PromptConfig(BaseModel):
    """Configuration for the NEXUS.md prompt system."""

    # Path to the base prompt file (defaults to ~/.nexusagent/NEXUS.md)
    base_prompt_file: str = Field(default="NEXUS.md")
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
    """Logging configuration for level and format string."""

    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class BudgetConfig(BaseModel):
    """LLM token budget configuration.

    Controls spend limits, alert thresholds, and quota cooldown behavior.
    All values are in USD unless noted.
    """

    enabled: bool = Field(
        default=True,
        description="Enable budget guard. If False, all budget checks pass.",
    )
    daily_budget_usd: float = Field(
        default=10.0,
        ge=0.0,
        description="Daily spend limit in USD. 0 = disabled. "
                    "Sensible default for new users (~1M tokens/day on gemini-2.5-flash).",
    )
    monthly_budget_usd: float = Field(
        default=100.0,
        ge=0.0,
        description="Monthly spend limit in USD. 0 = disabled. "
                    "Sensible default for new users (~10M tokens/month on gemini-2.5-flash).",
    )
    alert_thresholds: list[float] = Field(
        default_factory=lambda: [0.5, 0.8, 0.95],
        description="Alert thresholds as fraction of budget (0.0-1.0). "
                    "Default: 50%, 80%, 95%. Alerts logged at WARNING level.",
    )
    quota_cooldown_seconds: float = Field(
        default=3600.0,
        gt=0,
        description="Cooldown period after quota exhaustion (seconds). "
                    "Default: 1 hour (3600s).",
    )


class HooksConfig(BaseModel):
    """Configuration for the hooks system."""

    hooks_enabled: bool = Field(default=True)
    hooks_dir: str = Field(default="~/.nexusagent/hooks")


class TrustConfig(BaseModel):
    """Configuration for the trust subsystem (anomaly scoring, trust levels)."""
    enabled: bool = True
    anomaly_threshold: float = 0.60
    min_score: float = 0.0
    single_signal_boost_threshold: float = 0.70
    single_signal_boost_multiplier: float = 1.5
    pattern_weight: float = 0.40
    entropy_weight: float = 0.25
    length_weight: float = 0.20
    density_weight: float = 0.15


class TestModeConfig(BaseModel):
    """Test mode configuration to prevent accidental real API calls."""

    block_real_api: bool = Field(
        default=True,
        description="When true and NEXUS_TEST_MODE=1, blocks real LLM API calls"
    )


class ConfigSchema(BaseModel):
    """Top-level configuration schema aggregating all sub-configurations."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    test_mode: TestModeConfig = Field(default_factory=TestModeConfig)
    # Trust subsystem configuration
    trust: TrustConfig = Field(default_factory=TrustConfig)
    # MCP server configuration
    mcp_servers: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of MCP servers: [{'name': ..., 'url': ..., 'transport': ...}]",
    )
    # Back-compat: top-level log_level maps to logging.level
    log_level: str = Field(default="INFO")


def get_nexus_home() -> Path:
    """Return the NexusAgent home directory (~/.nexusagent/), creating it if needed."""
    home = Path.home() / ".nexusagent"
    home.mkdir(parents=True, exist_ok=True)
    # Ensure data subdirectory exists for database
    (home / "data").mkdir(parents=True, exist_ok=True)
    return home


def get_project_root() -> Path:
    """Return the repository root directory (four levels up from this file)."""
    # The config file is located at <root>/config/nexusagent.yaml
    # The file this function is in is <root>/src/nexusagent/infrastructure/config.py
    # To get to <root> from here: infrastructure -> nexusagent -> src -> (root)
    return Path(__file__).parent.parent.parent.parent.absolute()


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts. Override values win; nested dicts are merged recursively."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_file: str | None = None) -> ConfigSchema:
    """Load and validate configuration from defaults, project file, user file, and env vars.

    Resolution order (later overrides earlier):
        1. Pydantic model defaults
        2. Project config: ``config/nexusagent.yaml`` (repo defaults)
        3. User config: ``~/.nexusagent/config/nexusagent.yaml`` (user overrides)
        4. ``NEXUS_*`` environment variables (double underscore = nested key)

    Args:
        config_file: Optional explicit path to a YAML config file. If provided,
            it replaces both project and user config files. ``~`` is expanded.

    Returns:
        A validated ``ConfigSchema`` instance.
    """
    # Resolve config file paths
    project_root = get_project_root()
    project_config = project_root / "config" / "nexusagent.yaml"
    user_config = Path("~/.nexusagent/config/nexusagent.yaml").expanduser()

    # Load and merge: project defaults < user overrides < explicit file
    raw_data: dict = {}

    # Layer 1: Project config (committed defaults)
    if project_config.exists():
        try:
            with open(project_config) as f:
                raw_data = yaml.safe_load(f) or {}
            logger.debug("Loaded project config from %s", project_config)
        except Exception as e:
            logger.warning("Failed to load project config: %s", e)

    # Layer 2: User config (user overrides)
    if user_config.exists():
        try:
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
            # Deep merge user overrides on top of project defaults
            raw_data = _deep_merge(raw_data, user_data)
            logger.debug("Loaded user config from %s", user_config)
        except Exception as e:
            logger.warning("Failed to load user config: %s", e)

    # Layer 3: Explicit config file (if provided, replaces both)
    if config_file is not None:
        explicit_path = Path(config_file).expanduser()
        if explicit_path.exists():
            try:
                with open(explicit_path) as f:
                    raw_data = yaml.safe_load(f) or {}
                logger.debug("Loaded explicit config from %s", explicit_path)
            except Exception as e:
                logger.error("Failed to load explicit config file %s: %s", explicit_path, e)
        else:
            logger.warning("Explicit config file not found at %s", explicit_path)

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

    # Systematic overrides for each section (EXCLUDE test_mode - handled after deep merge)
    for section in [
        "server",
        "client",
        "auth",
        "agent",
        "prompt",
        "logging",
        "hooks",
        "budget",
    ]:
        section_data = raw_data.get(section, {})
        override_from_env(f"NEXUS_{section.upper()}__", section_data, section_data)
        raw_data[section] = section_data

    # Back-compat: NEXUS_LOG_LEVEL -> logging.level
    if "log_level" in raw_data and "logging" not in raw_data:
        raw_data.setdefault("logging", {})["level"] = raw_data["log_level"]

    # Layer 4: Environment variable overrides (highest priority)
    # Map known env vars to config fields
    env_overrides: dict = {}
    _env_mapping = {
        "GEMINI_API_KEY": "gemini_api_key",
        "OPENROUTER_API_KEY": None,  # Not a config field, just env var
        "EXA_API_KEY": None,
        "TAVILY_API_KEY": None,
    }
    for env_key, config_field in _env_mapping.items():
        val = os.environ.get(env_key)
        if val and config_field:
            # These fields belong to the agent section
            env_overrides.setdefault("agent", {})[config_field] = val

    # Special handling for simple boolean env vars (NEXUS_TEST_MODE=1, etc.) BEFORE general NEXUS_ override
    test_mode_env = os.environ.get("NEXUS_TEST_MODE", "").lower() in ("1", "true", "yes", "on")

    # Also load NEXUS_* env vars (existing pattern) - but filter out test_mode to handle separately
    # We need to temporarily remove NEXUS_TEST_MODE from environ to prevent it from being processed
    test_mode_value = os.environ.pop("NEXUS_TEST_MODE", None)

    # Also load NEXUS_* env vars (existing pattern)
    override_from_env("NEXUS_", raw_data, raw_data)

    # Restore NEXUS_TEST_MODE
    if test_mode_value is not None:
        os.environ["NEXUS_TEST_MODE"] = test_mode_value

    # Apply env overrides on top (deep merge)
    raw_data = _deep_merge(raw_data, env_overrides)

    # Special handling for simple boolean env vars (NEXUS_TEST_MODE=1, etc.) AFTER deep merge
    if test_mode_env:
        raw_data.setdefault("test_mode", {})["block_real_api"] = True

    # Coerce tui_responsive_enabled from string env var
    _resp = raw_data.get("client", {}).get("tui_responsive_enabled")
    if isinstance(_resp, str):
        raw_data.setdefault("client", {})["tui_responsive_enabled"] = _resp.lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

    try:
        config = ConfigSchema(**raw_data)

        # Resolve server/auth paths: expand ~, then resolve relative against nexus home
        nexus_home = get_nexus_home()
        for attr in ("db_path",):
            val = getattr(config.server, attr)
            val = str(Path(val).expanduser())
            if not Path(val).is_absolute():
                val = str(nexus_home / val)
            setattr(config.server, attr, val)
        for attr in ("master_secret_path", "keystore_path", "salt_path"):
            val = getattr(config.auth, attr)
            val = str(Path(val).expanduser())
            if not Path(val).is_absolute():
                val = str(nexus_home / val)
            setattr(config.auth, attr, val)

        # Ensure data subdirectories exist
        for path_str in (
            config.server.db_path,
            config.auth.master_secret_path,
            config.auth.keystore_path,
            config.auth.salt_path,
        ):
            Path(path_str).parent.mkdir(parents=True, exist_ok=True)

        return config
    except ValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


# Singleton settings instance
settings = load_config()


def reload_settings() -> ConfigSchema:
    """Reload settings from config files and environment variables.

    Use this after modifying config files to pick up changes without restarting.
    """
    global settings
    settings = load_config()
    return settings


def create_user_config_from_template() -> Path:
    """Create user config file (~/.nexusagent/config/nexusagent.yaml) from project template.

    Copies config/nexusagent.yaml to ~/.nexusagent/config/nexusagent.yaml if it doesn't exist.
    Returns the path to the created file.

    This is called automatically on first run if user config doesn't exist,
    or can be called explicitly via CLI/TUI command.
    """
    project_root = get_project_root()
    project_config = project_root / "config" / "nexusagent.yaml"
    user_config_dir = Path.home() / ".nexusagent" / "config"
    user_config = user_config_dir / "nexusagent.yaml"

    user_config_dir.mkdir(parents=True, exist_ok=True)

    if user_config.exists():
        logger.info(f"User config already exists at {user_config}")
        return user_config

    if not project_config.exists():
        raise FileNotFoundError(f"Project config template not found at {project_config}")

    # Copy template to user config location
    import shutil
    shutil.copy2(project_config, user_config)
    logger.info(f"Created user config from template: {user_config}")

    return user_config


def ensure_user_config_exists() -> Path:
    """Ensure user config exists, creating from template if needed.

    Returns the path to the user config file.
    """
    user_config = Path.home() / ".nexusagent" / "config" / "nexusagent.yaml"
    if not user_config.exists():
        return create_user_config_from_template()
    return user_config
