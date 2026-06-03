# Agent B: You are depending on the load_config() function and ConfigSchema type.
from pydantic import BaseModel
import yaml
from pathlib import Path
import os

class ConfigSchema(BaseModel):
    nats_url: str
    db_path: str

def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

def load_config(config_file: str = "config/nexusagent.yaml") -> ConfigSchema:
    config_path = get_project_root() / config_file
    if not config_path.exists():
        # Fallback or strict requirement? Let's be strict for production-grade.
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f)
        
    # Extract server-specific config
    server_config = raw_config.get("server", {})
    
    # Environment variable overrides
    nats_url = os.getenv("NEXUS_NATS_URL", server_config.get("nats_url", "nats://localhost:4222"))
    db_path = os.getenv("NEXUS_DB_PATH", server_config.get("db_path", "nexus.db"))
        
    return ConfigSchema(nats_url=nats_url, db_path=db_path)
