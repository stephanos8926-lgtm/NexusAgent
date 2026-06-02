import yaml
from pathlib import Path
import os

def get_project_root() -> Path:
    # Assuming this file is in src/nexusagent/
    return Path(__file__).parent.parent.parent

def load_config(config_file: str = "config/nexusagent.yaml") -> dict:
    config_path = get_project_root() / config_file
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    # Environment variable overrides
    if "NEXUS_NATS_URL" in os.environ:
        config["server"]["nats_url"] = os.environ["NEXUS_NATS_URL"]
    if "NEXUS_DB_PATH" in os.environ:
        config["server"]["db_path"] = os.environ["NEXUS_DB_PATH"]
        
    return config
