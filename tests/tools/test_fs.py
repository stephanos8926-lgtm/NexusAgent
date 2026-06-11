from pathlib import Path

import pytest

from nexusagent.tools.fs import (
    list_directory,
    read_file,
    read_multiple_files,
    set_workspace_root,
    write_file,
    write_multiple_files,
)


# Set up a temporary directory for tests
@pytest.fixture
def temp_workspace(tmp_path):
    from nexusagent.tools.fs import _WORKSPACE_ROOT as _old_workspace
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file1.txt").write_text("hello")
    (tmp_path / "file2.txt").write_text("world")
    set_workspace_root(str(tmp_path))
    yield tmp_path
    set_workspace_root(str(_old_workspace) if _old_workspace else str(Path.cwd()))


def test_fs_tools():
    """Basic read/write test — uses CWD as workspace."""
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=os.getcwd()) as tmp:
        tmp.write("hello")
        tmp_path = tmp.name
    try:
        assert read_file(tmp_path) == "hello"
        write_file(tmp_path, "world")
        assert read_file(tmp_path) == "world"
    finally:
        os.remove(tmp_path)
        set_workspace_root(os.getcwd())


def test_list_directory_recursive_true(temp_workspace):
    tree = list_directory(str(temp_workspace), recursive=True)
    assert "subdir" in tree
    assert "file1.txt" in tree["subdir"]
    assert "file2.txt" in tree


def test_list_directory_recursive_false(temp_workspace):
    tree = list_directory(str(temp_workspace), recursive=False)
    assert "subdir" in tree
    assert "file1.txt" not in tree["subdir"]
    assert "file2.txt" in tree


def test_read_multiple_files(temp_workspace):
    files = {
        "file1": str(temp_workspace / "subdir" / "file1.txt"),
        "file2": str(temp_workspace / "file2.txt"),
    }
    contents = read_multiple_files(list(files.values()))
    assert contents[files["file1"]] == "hello"
    assert contents[files["file2"]] == "world"


def test_safety_check(temp_workspace):
    new_file = str(temp_workspace / "file3.txt")
    write_file(new_file, "content")
    assert Path(new_file).read_text() == "content"


def test_write_after_read_success(temp_workspace):
    file_path = str(temp_workspace / "file2.txt")
    read_file(file_path)
    write_file(file_path, "new content")
    assert Path(file_path).read_text() == "new content"


def test_write_multiple_files_with_safety(temp_workspace):
    files = {
        str(temp_workspace / "new1.txt"): "c1",
        str(temp_workspace / "new2.txt"): "c2",
    }
    write_multiple_files(files)
    assert Path(str(temp_workspace / "new1.txt")).read_text() == "c1"
    assert Path(str(temp_workspace / "new2.txt")).read_text() == "c2"
