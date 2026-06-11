# tests/tools/test_fs.py
import os
import tempfile

from nexusagent.tools.fs import read_file, write_file, set_workspace_root


def test_fs_tools():
    # Create temp file inside the workspace (CWD) so it passes the path jail
    with tempfile.NamedTemporaryFile(
        mode="w+", delete=False, dir=os.getcwd()
    ) as tmp:
        tmp.write("hello")
        tmp_path = tmp.name

    try:
        assert read_file(tmp_path) == "hello"

        write_file(tmp_path, "world")
        assert read_file(tmp_path) == "world"
    finally:
        os.remove(tmp_path)
        # Reset workspace root to default (CWD-based)
        set_workspace_root(os.getcwd())
