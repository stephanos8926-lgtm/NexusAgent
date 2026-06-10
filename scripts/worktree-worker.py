#!/usr/bin/env python3
"""
worktree-worker.py — Isolated Worktree Worker CLI

Creates and manages git worktrees for parallel task execution.
Each worktree gets its own branch, working directory, and optional
isolated Hermes configuration.

Usage:
    python3 worktree-worker.py create --name <name> [--task <task>] [--base-branch <branch>]
    python3 worktree-worker.py list
    python3 worktree-worker.py collect --name <name>
    python3 worktree-worker.py destroy --name <name> [--force]
    python3 worktree-worker.py remote --name <name> --server <server> --task <task> [--repo <path>]
    python3 worktree-worker.py status --name <name>

Author: OWL (Lucien) for NexusAgent
License: MIT
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────────

REPO_ROOT = Path.cwd()
WORKTREE_BASE = REPO_ROOT / ".hermes" / "worktrees"
STATE_FILE = REPO_ROOT / ".hermes" / "worktree-state.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd: str, cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    result = subprocess.run(
        cmd, shell=True, cwd=str(cwd or REPO_ROOT),
        capture_output=True, text=True
    )
    if check and result.returncode != 0:
        print(f"  ✗ Command failed: {cmd}", file=sys.stderr)
        print(f"    stderr: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def load_state() -> dict:
    """Load the worktree state file."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"worktrees": {}}


def save_state(state: dict):
    """Save the worktree state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_worktree_path(name: str) -> Path:
    return WORKTREE_BASE / name


def worktree_exists(name: str) -> bool:
    return get_worktree_path(name).exists()


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_create(args):
    """Create a new git worktree with an optional task description."""
    name = args.name
    base_branch = args.base_branch or "master"
    branch_name = args.branch or name

    if worktree_exists(name):
        print(f"  ✗ Worktree '{name}' already exists at {get_worktree_path(name)}")
        print(f"  → Use 'collect' to get results or 'destroy' to clean up first.")
        sys.exit(1)

    worktree_path = get_worktree_path(name)
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)

    print(f"  → Creating worktree '{name}'...")
    print(f"    Branch: {branch_name}")
    print(f"    Path:   {worktree_path}")

    # Create worktree with new branch from base
    run(f"git worktree add {worktree_path} -b {branch_name} {base_branch}")

    # Write task description if provided
    if args.task:
        task_file = worktree_path / "WORKTREE_TASK.md"
        task_file.write_text(
            f"# Worktree Task: {name}\n\n"
            f"**Created:** {datetime.now().isoformat()}\n"
            f"**Branch:** {branch_name}\n"
            f"**Base:** {base_branch}\n\n"
            f"## Task\n\n{args.task}\n"
        )
        print(f"    Task written to WORKTREE_TASK.md")

    # Create isolated Hermes config if requested
    if args.isolated_hermes:
        hermes_dir = worktree_path / ".hermes"
        hermes_dir.mkdir(exist_ok=True)
        config_file = hermes_dir / "config.yaml"
        if not config_file.exists():
            # Copy from main repo's config as template
            main_config = REPO_ROOT / ".hermes" / "config.yaml"
            if main_config.exists():
                config_file.write_text(main_config.read_text())
                print(f"    Isolated Hermes config created")

    # Update state
    state = load_state()
    state["worktrees"][name] = {
        "name": name,
        "path": str(worktree_path),
        "branch": branch_name,
        "base_branch": base_branch,
        "created": datetime.now().isoformat(),
        "task": args.task or "",
        "status": "active",
    }
    save_state(state)

    print(f"  ✓ Worktree '{name}' ready")
    print(f"  → cd {worktree_path}")


def cmd_list(args):
    """List all worktrees and their status."""
    state = load_state()
    worktrees = state.get("worktrees", {})

    if not worktrees:
        print("  No worktrees found.")
        print(f"  → Create one: python3 {sys.argv[0]} create --name <name>")
        return

    # Also get git's view
    result = run("git worktree list", check=False)

    print(f"\n  {'Name':<30} {'Branch':<30} {'Status':<12} {'Path'}")
    print(f"  {'─' * 30} {'─' * 30} {'─' * 12} {'─' * 30}")

    for name, info in worktrees.items():
        path = Path(info["path"])
        exists = path.exists()
        status = info.get("status", "unknown")
        branch = info.get("branch", "?")

        if not exists:
            status = "missing"

        # Check for uncommitted changes
        if exists:
            dirty = run("git status --porcelain", cwd=str(path), check=False).stdout.strip()
            if dirty:
                status = "dirty"

        print(f"  {name:<30} {branch:<30} {status:<12} {info['path']}")

    print()


def cmd_collect(args):
    """Collect results from a worktree — show git log, diff summary, and task output."""
    name = args.name

    if not worktree_exists(name):
        print(f"  ✗ Worktree '{name}' not found")
        sys.exit(1)

    worktree_path = get_worktree_path(name)

    print(f"\n═══ Worktree: {name} ═══\n")

    # Git log (commits on this branch not on master)
    print("  ── Commits ──")
    result = run(f"git log master..HEAD --oneline 2>/dev/null || git log --oneline -10", cwd=str(worktree_path), check=False)
    for line in result.stdout.strip().split("\n"):
        if line:
            print(f"    {line}")

    # Diff summary
    print("\n  ── Changes ──")
    result = run("git diff --stat master...HEAD 2>/dev/null || git diff --stat HEAD~5..HEAD 2>/dev/null", cwd=str(worktree_path), check=False)
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"    {line}")
    else:
        print("    No changes detected")

    # Task file
    task_file = worktree_path / "WORKTREE_TASK.md"
    if task_file.exists():
        print(f"\n  ── Task ──")
        content = task_file.read_text()
        # Skip header, show task section
        in_task = False
        for line in content.split("\n"):
            if line.startswith("## Task"):
                in_task = True
                continue
            if in_task:
                print(f"    {line}")

    # Check for result files
    result_files = list(worktree_path.glob("*.md")) + list(worktree_path.glob("REPORT*")) + list(worktree_path.glob("docs/*.md"))
    result_files = [f for f in result_files if f.name not in ("README.md", "WORKTREE_TASK.md", "NEXUS.md")]
    if result_files:
        print(f"\n  ── Generated Files ──")
        for f in result_files:
            print(f"    {f.relative_to(worktree_path)}")

    print()


def cmd_destroy(args):
    """Remove a worktree and its branch."""
    name = args.name
    force = args.force

    state = load_state()
    info = state.get("worktrees", {}).get(name, {})
    branch = info.get("branch", name)

    if not worktree_exists(name):
        print(f"  ✗ Worktree '{name}' not found at {get_worktree_path(name)}")
        # Clean up state anyway
        if name in state.get("worktrees", {}):
            del state["worktrees"][name]
            save_state(state)
            print(f"  → Cleaned up stale state entry")
        sys.exit(1)

    worktree_path = get_worktree_path(name)

    # Check for uncommitted changes
    dirty = run("git status --porcelain", cwd=str(worktree_path), check=False).stdout.strip()
    if dirty and not force:
        print(f"  ✗ Worktree '{name}' has uncommitted changes")
        print(f"  → Use --force to discard, or commit/push first")
        print(f"  → cd {worktree_path} && git status")
        sys.exit(1)

    print(f"  → Removing worktree '{name}'...")
    run(f"git worktree remove {worktree_path}" + (" --force" if force else ""))

    # Delete the branch (only if it's not checked out elsewhere)
    if branch:
        result = run(f"git branch -d {branch}", check=False)
        if result.returncode == 0:
            print(f"  → Deleted branch '{branch}'")
        else:
            print(f"  → Branch '{branch}' not deleted (may have unmerged changes)")

    # Update state
    if name in state.get("worktrees", {}):
        del state["worktrees"][name]
    save_state(state)

    print(f"  ✓ Worktree '{name}' destroyed")


def cmd_remote(args):
    """Dispatch a worktree task to a remote server via SSH."""
    name = args.name
    server = args.server
    task = args.task
    repo = args.repo or "/home/sysop/Workspaces/NexusAgent"

    print(f"  → Dispatching to {server}...")
    print(f"    Worktree: {name}")
    print(f"    Repo: {repo}")

    # SSH command to create worktree and set up task
    ssh_cmd = (
        f"ssh {server} '"
        f"cd {repo} && "
        f"git worktree add .hermes/worktrees/{name} -b {name} master 2>/dev/null || "
        f"echo \"Worktree may already exist\" && "
        f"echo \"{task}\" > .hermes/worktrees/{name}/WORKTREE_TASK.md && "
        f"echo \"Task dispatched at $(date)\" && "
        f"git -C .hermes/worktrees/{name} status"
        f"'"
    )

    result = run(ssh_cmd, check=False)
    if result.returncode != 0:
        print(f"  ✗ SSH dispatch failed")
        print(f"    {result.stderr}")
        sys.exit(1)

    # Update state
    state = load_state()
    state["worktrees"][name] = {
        "name": name,
        "path": f"{server}:{repo}/.hermes/worktrees/{name}",
        "branch": name,
        "server": server,
        "repo": repo,
        "created": datetime.now().isoformat(),
        "task": task,
        "status": "remote-active",
    }
    save_state(state)

    print(f"  ✓ Remote worktree '{name}' created on {server}")
    print(f"  → Collect: python3 {sys.argv[0]} collect --name {name}")


def cmd_status(args):
    """Show detailed status of a specific worktree."""
    name = args.name

    if not worktree_exists(name):
        print(f"  ✗ Worktree '{name}' not found")
        sys.exit(1)

    worktree_path = get_worktree_path(name)

    print(f"\n═══ {name} ═══\n")

    # Git status
    print("  ── Git Status ──")
    result = run("git status -sb", cwd=str(worktree_path), check=False)
    for line in result.stdout.strip().split("\n"):
        print(f"    {line}")

    # Recent commits
    print("\n  ── Recent Commits ──")
    result = run("git log --oneline -5", cwd=str(worktree_path), check=False)
    for line in result.stdout.strip().split("\n"):
        print(f"    {line}")

    # Changed files
    print("\n  ── Changed Files ──")
    result = run("git diff --stat HEAD~3..HEAD 2>/dev/null || git diff --stat", cwd=str(worktree_path), check=False)
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"    {line}")
    else:
        print("    No changes")

    # Disk usage
    result = run(f"du -sh {worktree_path}", check=False)
    print(f"\n  ── Size: {result.stdout.strip().split()[0]} ──")

    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Isolated Worktree Worker — Manage parallel git worktrees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create --name fix-streaming --task "Fix TUI streaming bug" --base-branch master
  %(prog)s create --name research-tui --task "Research TUI aesthetics" --branch research/tui-aesthetics
  %(prog)s list
  %(prog)s status --name fix-streaming
  %(prog)s collect --name fix-streaming
  %(prog)s destroy --name fix-streaming
  %(prog)s remote --name heavy-research --server rapidwebs-01 --task "Deep research"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # create
    p_create = subparsers.add_parser("create", help="Create a new worktree")
    p_create.add_argument("--name", required=True, help="Worktree name (used as branch name too)")
    p_create.add_argument("--task", default="", help="Task description")
    p_create.add_argument("--base-branch", default="master", help="Base branch (default: master)")
    p_create.add_argument("--branch", default=None, help="Override branch name (default: same as --name)")
    p_create.add_argument("--isolated-hermes", action="store_true", help="Create isolated Hermes config")

    # list
    subparsers.add_parser("list", help="List all worktrees")

    # collect
    p_collect = subparsers.add_parser("collect", help="Collect results from a worktree")
    p_collect.add_argument("--name", required=True, help="Worktree name")

    # destroy
    p_destroy = subparsers.add_parser("destroy", help="Remove a worktree")
    p_destroy.add_argument("--name", required=True, help="Worktree name")
    p_destroy.add_argument("--force", action="store_true", help="Force remove even with uncommitted changes")

    # remote
    p_remote = subparsers.add_parser("remote", help="Dispatch to remote server")
    p_remote.add_argument("--name", required=True, help="Worktree name")
    p_remote.add_argument("--server", required=True, help="SSH server alias")
    p_remote.add_argument("--task", required=True, help="Task description")
    p_remote.add_argument("--repo", default="/home/sysop/Workspaces/NexusAgent", help="Remote repo path")

    # status
    p_status = subparsers.add_parser("status", help="Show worktree status")
    p_status.add_argument("--name", required=True, help="Worktree name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure we're in a git repo
    if not (REPO_ROOT / ".git").exists():
        # Check if we're in a worktree (git file instead of dir)
        git_file = REPO_ROOT / ".git"
        if not git_file.is_file():
            print("  ✗ Not in a git repository. Run from the NexusAgent repo root.")
            sys.exit(1)

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "collect": cmd_collect,
        "destroy": cmd_destroy,
        "remote": cmd_remote,
        "status": cmd_status,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
