"""
Git operations tool for NexusAgent.

Provides git status, diff, log, branch, commit, and stash operations.
All operations are read-only by default; write operations require explicit flags.
"""

import subprocess


def _run_git(args: str, workdir: str | None = None, timeout: int = 30) -> str:
    """Run a git command and return output."""
    cmd = f"git {args}"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
        if result.returncode != 0:
            return f"Git error (exit {result.returncode}): {result.stderr.strip()}"
        return result.stdout.strip() if result.stdout.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Git command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def git_status(workdir: str | None = None) -> str:
    """
    Show working tree status.

    Returns: Short-format status showing modified, added, deleted, untracked files.
    """
    return _run_git("status --short", workdir=workdir)


def git_diff(
    file_path: str | None = None,
    cached: bool = False,
    workdir: str | None = None,
) -> str:
    """
    Show changes between working tree and index (or HEAD).

    Args:
        file_path: Optional specific file to diff
        cached: If True, show staged changes instead of working tree changes
        workdir: Repository working directory

    Returns: Unified diff output
    """
    args = "diff"
    if cached:
        args += " --cached"
    if file_path:
        args += f" -- {file_path}"
    return _run_git(args, workdir=workdir)


def git_log(
    count: int = 10,
    file_path: str | None = None,
    oneline: bool = True,
    workdir: str | None = None,
) -> str:
    """
    Show commit history.

    Args:
        count: Number of commits to show
        file_path: Optional specific file to show history for
        oneline: If True, show one commit per line
        workdir: Repository working directory

    Returns: Commit log output
    """
    args = f"log -n {count}"
    if oneline:
        args += " --oneline"
    if file_path:
        args += f" -- {file_path}"
    return _run_git(args, workdir=workdir)


def git_branch(workdir: str | None = None) -> str:
    """
    List branches. Current branch is marked with *.

    Returns: Branch list output
    """
    return _run_git("branch -v", workdir=workdir)


def git_show(commit: str = "HEAD", workdir: str | None = None) -> str:
    """
    Show a commit's details and diff.

    Args:
        commit: Commit hash, branch name, or ref (default: HEAD)
        workdir: Repository working directory

    Returns: Commit details + diff
    """
    return _run_git(f"show {commit} --stat", workdir=workdir)


def git_stash_list(workdir: str | None = None) -> str:
    """List stashed changes."""
    return _run_git("stash list", workdir=workdir)


def git_stash_push(message: str | None = None, workdir: str | None = None) -> str:
    """
    Stash current changes. Write operation.

    Args:
        message: Optional stash message
        workdir: Repository working directory

    Returns: Stash result
    """
    args = "stash push"
    if message:
        args += f" -m {message}"
    return _run_git(args, workdir=workdir)


def git_stash_pop(workdir: str | None = None) -> str:
    """Pop the most recent stash. Write operation."""
    return _run_git("stash pop", workdir=workdir)


def git_commit(message: str, files: list[str] | None = None, workdir: str | None = None) -> str:
    """
    Stage and commit changes. Write operation.

    Args:
        message: Commit message
        files: Optional list of specific files to commit (default: all staged)
        workdir: Repository working directory

    Returns: Commit result
    """
    if files:
        for f in files:
            _run_git(f"add {f}", workdir=workdir)
    else:
        _run_git("add -A", workdir=workdir)

    return _run_git(f"commit -m {message}", workdir=workdir)


def git_checkout_branch(branch: str, create: bool = False, workdir: str | None = None) -> str:
    """
    Checkout a branch. Write operation.

    Args:
        branch: Branch name
        create: If True, create the branch first (-b flag)
        workdir: Repository working directory

    Returns: Checkout result
    """
    args = f"checkout {'-b ' if create else ''}{branch}"
    return _run_git(args, workdir=workdir)
