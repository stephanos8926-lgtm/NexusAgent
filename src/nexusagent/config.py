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
        
    # Potential environment variable overrides could go here.
    # For now, return the loaded config.
    return config
