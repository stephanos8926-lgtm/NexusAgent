from nexusagent.tools.patch import apply_patch
import tempfile
import os

def test_apply_patch():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
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
    with open(tmp_path, 'r') as f:
        assert f.read() == "new_line1\nline2\n"
    os.remove(tmp_path)