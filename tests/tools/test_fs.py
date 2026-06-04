# tests/tools/test_fs.py
import os
import tempfile

from nexusagent.tools.fs import read_file, write_file


def test_fs_tools():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
        tmp.write("hello")
        tmp_path = tmp.name
    
    try:
        assert read_file(tmp_path) == "hello"
        
        write_file(tmp_path, "world")
        assert read_file(tmp_path) == "world"
    finally:
        os.remove(tmp_path)
