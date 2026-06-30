"""File patching tool for NexusAgent.

Applies unified diff patches to files using the patch-ng library.
Used by the agent to apply code changes from diff/patch format.
"""

from pathlib import Path

import patch_ng

from nexusagent.tools.fs_base import _get_workspace_root


def apply_patch(path: str, diff: str) -> str:
    """Applies a unified diff patch to a file."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        return f"Error: File {path} does not exist"

    # Workspace jail: ensure the file is within the workspace root
    workspace = _get_workspace_root()
    try:
        file_path.relative_to(workspace)
    except ValueError:
        return f"Error: SAFETY: Path '{path}' resolves to '{file_path}' which is outside the workspace root '{workspace}'"

    # patch-ng usage
    p = patch_ng.fromstring(diff.encode("utf-8"))
    if p.apply(root=str(file_path.parent)):
        return f"Successfully applied patch to {path}"
    else:
        return f"Error: Failed to apply patch to {path}"
