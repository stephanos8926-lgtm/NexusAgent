import os
from pathlib import Path

# Track files read in the current session
_read_files = set()

def read_file(path: str) -> str:
    """Reads the content of a file and marks it as read."""
    p = Path(path).resolve()
    # Basic security check
    if not p.exists():
        return f"Error: File {path} does not exist"
    
    _read_files.add(str(p))
    return p.read_text()

def read_multiple_files(paths: list[str]) -> dict:
    """Reads multiple files and marks them as read."""
    results = {}
    for path in paths:
        results[path] = read_file(path)
    return results

def write_file(path: str, content: str) -> str:
    """Writes content to a file with a safety check."""
    p = Path(path).resolve()
    
    # Safety check: path must have been read, or file must not exist
    if p.exists() and str(p) not in _read_files:
        raise Exception(f"File not read: {path}")
        
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Successfully wrote to {path}"

def write_multiple_files(files: dict[str, str]) -> str:
    """Writes multiple files with a safety check."""
    for path, content in files.items():
        write_file(path, content)
    return f"Successfully wrote {len(files)} files"

def list_directory(path: str, recursive: bool = False, max_depth: int = 2) -> dict:
    """Returns a nested tree structure of a directory."""
    def _build_tree(p: Path, depth: int) -> dict:
        tree = {}
        if depth > max_depth:
            return tree
            
        for item in p.iterdir():
            if item.is_dir():
                if recursive:
                    tree[item.name] = _build_tree(item, depth + 1)
                else:
                    tree[item.name] = "directory"
            else:
                tree[item.name] = "file"
        return tree
        
    p = Path(path).resolve()
    if not p.exists() or not p.is_dir():
        return {}
    return _build_tree(p, 0)
