from pathlib import Path

import patch_ng


def apply_patch(path: str, diff: str) -> str:
    """Applies a unified diff patch to a file."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        return f"Error: File {path} does not exist"

    # patch-ng usage
    p = patch_ng.fromstring(diff.encode("utf-8"))
    if p.apply(root=str(file_path.parent)):
        return f"Successfully applied patch to {path}"
    else:
        return f"Error: Failed to apply patch to {path}"
