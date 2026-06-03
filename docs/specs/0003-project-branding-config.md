# Technical Specification: Project Branding and Configuration Management

## 1. Introduction
This document specifies the technical implementation details for centralizing project metadata, branding elements, and securely managing critical configuration parameters, including dedicated security slots. This system aims to enable easy rebranding, maintain consistency across the application, and establish a robust approach to managing sensitive data.

**Goals:**
- Implement a single, Pydantic-based `BrandingConfig` to consolidate all project identity and contact information.
- Provide a flexible mechanism for loading branding elements, prioritizing environment variables.
- Define and securely manage three dedicated "security slots" for public keys or identifiers.
- Ensure `BrandingConfig` is easily accessible across server and client components.

**Non-Goals:**
- Full secrets management solution (e.g., integration with Vault or AWS Secrets Manager) beyond securely loading values from environment variables (future phase).
- A dynamic, runtime UI for configuration editing.
- Complex conditional branding logic based on runtime context (e.g., client-specific logos based on user).

## 2. Technical Design

### 2.1. `src/nexusagent/config/branding.py` - `BrandingConfig` Definition
A new file will be created to define the `BrandingConfig` using Pydantic's `BaseModel` for strong typing and validation. `SecretStr` will be used for sensitive fields to ensure they are not accidentally logged or printed.

```python
# src/nexusagent/config/branding.py (New file)
from pydantic import BaseModel, Field, HttpUrl, EmailStr, SecretStr
from typing import Optional

class BrandingConfig(BaseModel):
    project_name_full: str = "NexusAgent Orchestration Framework"
    project_name_short: str = "NexusAgent"
    project_subtitle: str = "The Intelligent Automation Platform"
    project_description: str = "A robust framework for deploying multi-agent AI systems, offering modular components for NATS orchestration, secure key management, and flexible client interfaces."
    full_descriptive_summary: str = "This is a detailed summary of the NexusAgent platform, outlining its architecture, core functionalities, and value proposition for enterprise automation and AI integration."
    website_url: HttpUrl = HttpUrl("https://www.nexusagent.dev")
    github_url: HttpUrl = HttpUrl("https://github.com/NexusAgent/nexusagent")
    maintainers_email: EmailStr = EmailStr("maintainers@nexusagent.dev")
    tech_support_email: EmailStr = EmailStr("support@nexusagent.dev")
    company_website_url: HttpUrl = HttpUrl("https://www.your-company.com")
    official_contact_info: str = "Your Company, 123 Main St, City, Country, ZIP. Phone: +1-555-123-4567"
    version_code_string: str = "1.0.0-beta.1" # Full semver string
    version_code: str = "1.0.0" # Major.Minor.Patch
    additional_notes: Optional[str] = None
    
    # Dedicated security slots (public keys/identifiers), loaded only from environment variables
    # Using SecretStr ensures these values are not easily exposed.
    security_slot_1: Optional[SecretStr] = Field(default=None, env="NEXUS_SECURITY_SLOT_1") # E.g., Public key for build signature verification
    security_slot_2: Optional[SecretStr] = Field(default=None, env="NEXUS_SECURITY_SLOT_2") # E.g., Public key for release package bundle verification
    security_slot_3: Optional[SecretStr] = Field(default=None, env="NEXUS_SECURITY_SLOT_3") # E.g., Public key/ID for update server communication

    class Config:
        # Enable Pydantic to read environment variables with the 'NEXUS_' prefix for default values
        env_prefix = "NEXUS_"
        case_sensitive = False # Be flexible with env var case
        extra = "ignore" # Ignore extra env vars not defined in the model

```

### 2.2. Configuration Loading Mechanism (`src/nexusagent/config.py`)
The existing `config.py` will be enhanced to instantiate `BrandingConfig` and make it globally available (e.g., via a singleton pattern or dependency injection). The loading process will implicitly prioritize environment variables (due to `BaseModel.Config.env_prefix`) and then fall back to default values.

```python
# src/nexusagent/config.py (modifications)
from pydantic import BaseModel
import yaml
from pathlib import Path
import os
from src.nexusagent.config.branding import BrandingConfig # Import the new BrandingConfig

# Existing ConfigSchema for operational parameters (if needed, keep separate or merge)
class AppConfigSchema(BaseModel):
    nats_url: str
    db_path: str
    # Add telemetry config reference
    telemetry: TelemetryConfig # Nested telemetry config from its own module
    

def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_configs()
        return cls._instance

    def _load_configs(self):
        # Load BrandingConfig, environment variables will take precedence due to Pydantic BaseSettings
        self.branding = BrandingConfig()

        # Load application-specific configuration (can still be from YAML with env overrides)
        config_path = get_project_root() / "config" / "nexusagent.yaml"
        raw_config = {}
        if config_path.exists():
            with open(config_path, "r") as f:
                raw_config = yaml.safe_load(f)
        
        # Apply environment variable overrides for AppConfigSchema components if they're simple
        nats_url = os.getenv("NEXUS_NATS_URL", raw_config.get("server", {}).get("nats_url", "nats://localhost:4222"))
        db_path = os.getenv("NEXUS_DB_PATH", raw_config.get("server", {}).get("db_path", "nexus.db"))

        # Initialize TelemetryConfig as well, allowing it to read its own environment variables
        from src.nexustele.config import TelemetryConfig # Import within method to avoid circular dep
        self.telemetry_config = TelemetryConfig() # Pydantic will auto-load from env/defaults

        # Create the AppConfigSchema instance (can compose other configs)
        self.app_config = AppConfigSchema(
            nats_url=nats_url,
            db_path=db_path,
            telemetry=self.telemetry_config # Inject the telemetry config
        )

    def get_branding(self) -> BrandingConfig:
        return self.branding

    def get_app_config(self) -> AppConfigSchema:
        return self.app_config

# Global instance for easy access (if not using full DI in all contexts)
config_manager = ConfigManager()

def load_config(): # Existing function for backward compatibility
    return config_manager.get_app_config()
```

### 2.3. Secure Slots Implementation

- **Environment Variables:** The `security_slot_1`, `2`, `3` will *only* be configured via dedicated environment variables (`NEXUS_SECURITY_SLOT_1`, `NEXUS_SECURITY_SLOT_2`, `NEXUS_SECURITY_SLOT_3`). These variables will **never** be hardcoded in `.yaml` files or have default plaintext values in `src/nexusagent/config/branding.py`.
- **Access:** Accessed via `config_manager.get_branding().security_slot_X.get_secret_value()`.
- **Usage:** These slots are intended for public keys or identifiers (e.g., a PGP public key for verifying build artifacts, a SHA-256 hash of an update server's SSL certificate fingerprint, or an ID for a trusted hardware enclave). Their specific cryptographic or verification use will be handled by dedicated security modules.
- **Protection:** `SecretStr` prevents accidental printing in logs or shell output.

### 2.4. Integration with Application Components

- **SDK (`src/nexusagent/clients/sdk.py`):** The `NexusSDK` will be initialized with an instance of `ConfigManager`, providing access to branding information and operational config. E.g., `sdk.get_branding().project_name_short`.
- **FastAPI Server (`src/nexusagent/platform/server/app.py`):** Use `Depends(get_config_manager)` for injecting `ConfigManager` instances into routes or directly access `config_manager.get_branding()` for global information.
- **TUI/Web UI Clients (`src/nexusagent/clients/tui.py`, `src/nexusagent/clients/web_ui.py`):** These clients will use `config_manager.get_branding()` to dynamically display the project name, subtitle, and other branding elements.

### 2.5. API Exposure of Branding Information

- A new endpoint `/info` or `/about` will be added to the FastAPI server (`src/nexusagent/platform/server/app.py`) to expose *non-sensitive* branding and version information.
- This endpoint will return a subset of the `BrandingConfig` (excluding `SecretStr` fields) as a JSON response.

**Example API Endpoint:**
```python
# src/nexusagent/platform/server/app.py (modifications)
# ... imports ...
from fastapi import FastAPI, Depends, Request
# ... other imports
from src.nexusagent.config import config_manager, ConfigManager # Import ConfigManager and its instance
from src.nexusagent.config.branding import BrandingConfig

app = FastAPI()
# ... middleware and other setup ...

# Dependency for injecting the ConfigManager
def get_config_manager() -> ConfigManager:
    return configManager

# API endpoint to expose branding info (excluding secrets)
@app.get("/about", response_model=BrandingConfig) # Response model ensures type safety
async def get_about_info(config: ConfigManager = Depends(get_config_manager)):
    # Return a copy to ensure original SecretStr objects are not exposed directly
    # Pydantic's .dict() or .json() will handle SecretStr redaction by default.
    return config.get_branding().model_dump(exclude_unset=True, exclude={'security_slot_1', 'security_slot_2', 'security_slot_3'})

# ... existing API routes ...
```

## 3. Naming Conventions
- All `BrandingConfig` fields will be `snake_case`.
- Environment variables for security slots will use `NEXUS_SECURITY_SLOT_X`.
- API endpoints will be `kebab-case` (`/about`).

## 4. Testing Strategy

*   **Unit Tests (`tests/unit/config/`):**
    *   Verify `BrandingConfig` default values.
    *   Test `BrandingConfig`'s ability to load values from environment variables (mock `os.environ`).
    *   Assert that `SecretStr` fields correctly obfuscate values when `.get_secret_value()` is not called.
    *   Test `ConfigManager` singleton pattern.
    *   Verify `ConfigManager` correctly loads `BrandingConfig` and `AppConfigSchema`.
*   **Integration Tests (`tests/integration/`):**
    *   FastAPI `/about` endpoint: Test that it returns correct branding info and *excludes* security slots.
    *   SDK: Verify SDK components correctly access branding information.
*   **E2E Tests:** Ensure that configured branding elements are correctly displayed in CLI, TUI, and Web UI (if applicable), and that the `/about` endpoint is functional.

## 5. Phased Rollout
This specification covers **Phase 4: Project Branding and Configuration Management**. The next steps involve implementation and subsequent testing, followed by documentation updates.
