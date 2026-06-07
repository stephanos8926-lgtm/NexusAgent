import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import os
import tempfile

from nexusagent.tools.patch import apply_patch


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
