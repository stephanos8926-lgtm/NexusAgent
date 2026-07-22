import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import os
import tempfile
from pathlib import Path

import pytest

from nexusagent.tools.fs_base import set_workspace_root, _get_workspace_root
from nexusagent.tools.patch import apply_patch


@pytest.fixture(autouse=True)
def _tmp_workspace(monkeypatch, tmp_path):
    """Reset workspace root to a tmpdir so apply_patch accepts /tmp + /var/tmp paths.

    Uses pytest's ``tmp_path`` (auto-created fresh per-test) so workspace_root
    covers ``Path(tmp_path)`` — which is /tmp on most Linux runners and may
    be /var/tmp elsewhere (Debian's ``TMPDIR=/var/tmp`` default). Also
    forces ``tempfile.tempdir`` so NamedTemporaryFile lands inside it.
    """
    set_workspace_root(str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    yield
    set_workspace_root(str(_get_workspace_root()))


def test_apply_patch():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("line1\nline2\n")
        tmp_path = tmp.name

    diff = """--- {filename}
+++ {filename}
@@ -1,2 +1,2 @@
-line1
+new_line1
 line2
""".format(filename=os.path.basename(tmp_path))

    result = apply_patch(tmp_path, diff)
    assert "Successfully" in result
    with open(tmp_path) as f:
        assert f.read() == "new_line1\nline2\n"
    os.remove(tmp_path)


def test_apply_patch_failure():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("line1\nline2\n")
        tmp_path = tmp.name

    diff = """--- {filename}
+++ {filename}
@@ -1,2 +1,2 @@
-invalid_line
+new_line1
 line2
""".format(filename=os.path.basename(tmp_path))

    result = apply_patch(tmp_path, diff)
    assert "Error" in result
    os.remove(tmp_path)
