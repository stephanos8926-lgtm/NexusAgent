import os
from pathlib import Path

def read_file(path: str) -> str:
    """Reads the content of a file."""
    p = Path(path).resolve()
    # Basic security check
    if not p.exists():
        return f"Error: File {path} does not exist"
    return p.read_text()

def write_file(path: str, content: str) -> str:
    """Writes content to a file."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Successfully wrote to {path}"
