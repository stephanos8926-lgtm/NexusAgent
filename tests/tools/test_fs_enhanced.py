from pathlib import Path

import pytest

from nexusagent.tools.fs import (
    list_directory,
    read_file,
    read_multiple_files,
    write_file,
    write_multiple_files,
)


# Set up a temporary directory for tests
@pytest.fixture
def temp_workspace(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file1.txt").write_text("hello")
    (tmp_path / "file2.txt").write_text("world")
    return tmp_path


def test_list_directory_recursive_true(temp_workspace):
    tree = list_directory(str(temp_workspace), recursive=True)
    assert "subdir" in tree
    assert "file1.txt" in tree["subdir"]
    assert "file2.txt" in tree


def test_list_directory_recursive_false(temp_workspace):
    tree = list_directory(str(temp_workspace), recursive=False)
    # With recursive=False, it should not list the contents of subdir
    assert "subdir" in tree
    # The current implementation actually DOES recurse, so this test should fail
    # if I don't update the code to respect 'recursive=False'.
    # This is TDD!
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
    # This should succeed because file3.txt is a new file
    new_file = str(temp_workspace / "file3.txt")
    write_file(new_file, "content")
    assert Path(new_file).read_text() == "content"


def test_write_after_read_success(temp_workspace):
    file_path = str(temp_workspace / "file2.txt")
    # Read first
    read_file(file_path)
    # Then write
    write_file(file_path, "new content")
    assert Path(file_path).read_text() == "new content"


def test_write_multiple_files_with_safety(temp_workspace):
    # This should succeed because these are new files
    files = {
        str(temp_workspace / "new1.txt"): "c1",
        str(temp_workspace / "new2.txt"): "c2",
    }
    write_multiple_files(files)
    assert Path(str(temp_workspace / "new1.txt")).read_text() == "c1"
    assert Path(str(temp_workspace / "new2.txt")).read_text() == "c2"
