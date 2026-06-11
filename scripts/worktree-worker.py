#!/usr/bin/env python3
"""
worktree-worker.py — Isolated Worktree Worker CLI

Creates and manages git worktrees for parallel task execution.
Each worktree gets its own branch, working directory, and optional
isolated Hermes configuration.

Usage:
    python3 worktree-worker.py create --name <name> [--task <task>] [--base-branch <branch>]
    python3 worktree-worker.py list [--json]
    python3 worktree-worker.py collect --name <name>
    python3 worktree-worker.py destroy --name <name> [--force]
    python3 worktree-worker.py remote --name <name> --server <server> --task <task> [--repo <path>]
    python3 worktree-worker.py status --name <name>
    python3 worktree-worker.py sync --server <server>
    python3 worktree-worker.py doctor
    python3 worktree-worker.py init --name <name> [--model <model>]

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
        if result.stderr.strip():
            print(f"    stderr: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def load_state() -> dict:
    """Load the worktree state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"  ✗ Failed to parse state file {STATE_FILE}: {e}", file=sys.stderr)
            print(f"  → Fix the file or delete it to start fresh.", file=sys.stderr)
            sys.exit(1)
    return {"worktrees": {}}


def save_state(state: dict):
    """Save the worktree state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_worktree_path(name: str) -> Path:
    return WORKTREE_BASE / name


def worktree_exists(name: str) -> bool:
    return get_worktree_path(name).exists()


def check_git_repo():
    """Ensure we're in a git repository, with a clear error message if not."""
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists() and not git_dir.is_file():
        print("  ✗ Not in a git repository.", file=sys.stderr)
        print(f"  → Current directory: {REPO_ROOT}", file=sys.stderr)
        print("  → Run this command from the NexusAgent repo root.", file=sys.stderr)
        sys.exit(1)


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
            else:
                print(f"  ⚠ No main .hermes/config.yaml found to copy as template")

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
        if getattr(args, 'json', False):
            print(json.dumps({"worktrees": [], "count": 0}, indent=2))
        else:
            print("  No worktrees found.")
            print(f"  → Create one: python3 {sys.argv[0]} create --name <name>")
        return

    # Build structured data
    entries = []
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

        entries.append({
            "name": name,
            "branch": branch,
            "status": status,
            "path": info["path"],
            "task": info.get("task", ""),
            "created": info.get("created", ""),
            "exists": exists,
        })

    # JSON output mode
    if getattr(args, 'json', False):
        output = {
            "worktrees": entries,
            "count": len(entries),
            "generated_at": datetime.now().isoformat(),
        }
        print(json.dumps(output, indent=2))
        return

    # Human-readable table
    print(f"\n  {'Name':<30} {'Branch':<30} {'Status':<12} {'Path'}")
    print(f"  {'─' * 30} {'─' * 30} {'─' * 12} {'─' * 30}")

    for entry in entries:
        print(f"  {entry['name']:<30} {entry['branch']:<30} {entry['status']:<12} {entry['path']}")

    print()


def cmd_collect(args):
    """Collect results from a worktree — show git log, diff summary, and task output."""
    name = args.name

    if not worktree_exists(name):
        print(f"  ✗ Worktree '{name}' not found at {get_worktree_path(name)}", file=sys.stderr)
        print(f"  → Run 'list' to see available worktrees.", file=sys.stderr)
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
        print(f"  ✗ Worktree '{name}' not found at {get_worktree_path(name)}", file=sys.stderr)
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
        print(f"  ✗ SSH dispatch failed", file=sys.stderr)
        if result.stderr.strip():
            print(f"    stderr: {result.stderr.strip()}", file=sys.stderr)
        print(f"  → Check SSH connectivity: ssh {server} 'echo ok'", file=sys.stderr)
        print(f"  → Verify the repo path exists on the remote: {repo}", file=sys.stderr)
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
        print(f"  ✗ Worktree '{name}' not found at {get_worktree_path(name)}", file=sys.stderr)
        print(f"  → Run 'list' to see available worktrees.", file=sys.stderr)
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


def cmd_sync(args):
    """Sync worktree state between local and remote server."""
    server = args.server
    repo = args.repo or "/home/sysop/Workspaces/NexusAgent"

    print(f"  → Syncing worktree state with {server}...")
    print(f"    Remote repo: {repo}")
    print()

    # Step 1: Fetch remote worktree list
    print("  ── Fetching remote worktrees ──")
    result = run(f"ssh {server} 'cd {repo} && git worktree list'", check=False)
    if result.returncode != 0:
        print(f"  ✗ Failed to connect to {server}", file=sys.stderr)
        print(f"  → Check SSH: ssh {server} 'echo ok'", file=sys.stderr)
        sys.exit(1)

    remote_worktrees = result.stdout.strip()
    if remote_worktrees:
        for line in remote_worktrees.split("\n"):
            print(f"    {line}")
    else:
        print("    (no remote worktrees)")

    # Step 2: Fetch remote state file
    print("\n  ── Fetching remote state ──")
    result = run(f"ssh {server} 'cat {repo}/.hermes/worktree-state.json 2>/dev/null || echo \"{{\"' ", check=False)
    try:
        remote_state = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        print("    (no valid remote state found)")
        remote_state = {"worktrees": {}}

    # Step 3: Merge states
    local_state = load_state()
    local_worktrees = local_state.get("worktrees", {})
    remote_worktrees_dict = remote_state.get("worktrees", {})

    merged = dict(local_worktrees)
    added = []
    updated = []
    for name, info in remote_worktrees_dict.items():
        if name not in merged:
            merged[name] = info
            added.append(name)
        else:
            # Keep the newer entry
            remote_created = info.get("created", "")
            local_created = merged[name].get("created", "")
            if remote_created > local_created:
                merged[name] = info
                updated.append(name)

    local_state["worktrees"] = merged
    save_state(local_state)

    if added:
        print(f"  → Added from remote: {', '.join(added)}")
    if updated:
        print(f"  → Updated from remote: {', '.join(updated)}")
    if not added and not updated:
        print("  → Local state is already in sync")

    # Step 4: Push local state to remote
    print("\n  ── Pushing local state to remote ──")
    state_json = json.dumps(local_state)
    result = run(f"ssh {server} 'cat > {repo}/.hermes/worktree-state.json << \'EOF\'\n{state_json}\nEOF\n'", check=False)
    if result.returncode != 0:
        print(f"  ✗ Failed to push state to {server}", file=sys.stderr)
        print(f"  → Check write permissions on remote: {repo}/.hermes/", file=sys.stderr)
        sys.exit(1)

    print(f"  ✓ Sync complete — {len(merged)} worktrees tracked locally")


def cmd_doctor(args):
    """Diagnose common worktree issues."""
    print("\n═══ Worktree Doctor ═══\n")
    issues = 0
    warnings = 0

    # Check 1: Git repository
    print("  ── Check: Git Repository ──")
    git_dir = REPO_ROOT / ".git"
    if git_dir.exists() or git_dir.is_file():
        print("    ✓ In a git repository")
    else:
        print("    ✗ NOT in a git repository")
        print(f"      CWD: {REPO_ROOT}")
        issues += 1

    # Check 2: Git worktree list
    print("\n  ── Check: Git Worktrees ──")
    result = run("git worktree list", check=False)
    if result.returncode == 0:
        worktree_lines = [l for l in result.stdout.strip().split("\n") if l]
        print(f"    ✓ {len(worktree_lines)} worktree(s) registered")
        for line in worktree_lines:
            print(f"      {line}")
    else:
        print("    ✗ Failed to list worktrees")
        issues += 1

    # Check 3: Branch status
    print("\n  ── Check: Branch Status ──")
    result = run("git branch -a", check=False)
    if result.returncode == 0:
        branches = [l.strip().strip("* ").strip() for l in result.stdout.strip().split("\n") if l.strip()]
        print(f"    ✓ {len(branches)} branch(es) found")
        # Show worktree branches
        state = load_state()
        for name, info in state.get("worktrees", {}).items():
            branch = info.get("branch", "?")
            branch_result = run(f"git rev-parse --verify {branch}", check=False)
            if branch_result.returncode == 0:
                print(f"      ✓ {branch} (exists)")
            else:
                print(f"      ✗ {branch} (MISSING)")
                issues += 1
    else:
        print("    ✗ Failed to list branches")
        issues += 1

    # Check 4: Uncommitted changes in worktrees
    print("\n  ── Check: Uncommitted Changes ──")
    state = load_state()
    worktrees = state.get("worktrees", {})
    if not worktrees:
        print("    (no worktrees tracked)")
    else:
        for name, info in worktrees.items():
            path = Path(info["path"])
            if not path.exists():
                print(f"      ✗ {name}: path does not exist ({path})")
                issues += 1
                continue
            dirty = run("git status --porcelain", cwd=str(path), check=False).stdout.strip()
            if dirty:
                changed_count = len(dirty.split("\n"))
                print(f"      ⚠ {name}: {changed_count} uncommitted change(s)")
                warnings += 1
            else:
                print(f"      ✓ {name}: clean")

    # Check 5: Remote connectivity
    print("\n  ── Check: Remote Connectivity ──")
    result = run("git remote -v", check=False)
    if result.returncode == 0:
        remotes = result.stdout.strip().split("\n")
        remotes = [r for r in remotes if r.strip()]
        if remotes:
            for r in remotes:
                parts = r.split("\t")
                if len(parts) >= 1:
                    remote_name = parts[0].split()[0]
                    ls_result = run(f"git ls-remote --heads {remote_name}", check=False)
                    if ls_result.returncode == 0:
                        head_count = len([l for l in ls_result.stdout.strip().split("\n") if l.strip()])
                        print(f"      ✓ {remote_name}: reachable ({head_count} heads)")
                    else:
                        print(f"      ⚠ {remote_name}: UNREACHABLE")
                        warnings += 1
        else:
            print("      (no remotes configured)")
            warnings += 1
    else:
        print("    ✗ Failed to check remotes")
        issues += 1

    # Check 6: State file integrity
    print("\n  ── Check: State File ──")
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            count = len(data.get("worktrees", {}))
            print(f"    ✓ State file valid ({count} worktrees tracked)")
        except json.JSONDecodeError as e:
            print(f"    ✗ State file corrupted: {e}")
            issues += 1
    else:
        print("    (no state file yet — will be created on first worktree)")

    # Check 7: Disk usage
    print("\n  ── Check: Disk Usage ──")
    if worktrees:
        for name, info in worktrees.items():
            path = Path(info["path"])
            if path.exists():
                du_result = run(f"du -sh {path}", check=False)
                if du_result.returncode == 0:
                    size = du_result.stdout.strip().split()[0]
                    print(f"      {name}: {size}")
    else:
        print("    (no worktrees to check)")

    # Summary
    print(f"\n═══ Summary ═══")
    if issues == 0 and warnings == 0:
        print("  ✓ All checks passed — system healthy")
    else:
        if issues:
            print(f"  ✗ {issues} issue(s) found — needs attention")
        if warnings:
            print(f"  ⚠ {warnings} warning(s) — review recommended")
    print()


def cmd_init(args):
    """Initialize a new worktree with proper configuration."""
    name = args.name
    model = args.model or "openrouter/owl-alpha"
    base_branch = args.base_branch or "master"
    task = args.task or ""

    print(f"  → Initializing worktree '{name}'...")
    print(f"    Model: {model}")
    print(f"    Base branch: {base_branch}")

    if worktree_exists(name):
        print(f"  ✗ Worktree '{name}' already exists at {get_worktree_path(name)}")
        print(f"  → Use 'destroy' first if you want to recreate it.")
        sys.exit(1)

    worktree_path = get_worktree_path(name)
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)

    # Create the worktree
    run(f"git worktree add {worktree_path} -b {name} {base_branch}")
    print(f"  ✓ Worktree created at {worktree_path}")

    # Write task description
    if task:
        task_file = worktree_path / "WORKTREE_TASK.md"
        task_file.write_text(
            f"# Worktree Task: {name}\n\n"
            f"**Created:** {datetime.now().isoformat()}\n"
            f"**Branch:** {name}\n"
            f"**Base:** {base_branch}\n"
            f"**Model:** {model}\n\n"
            f"## Task\n\n{task}\n"
        )
        print(f"  ✓ Task written to WORKTREE_TASK.md")

    # Create isolated Hermes config with model
    hermes_dir = worktree_path / ".hermes"
    hermes_dir.mkdir(exist_ok=True)
    config_file = hermes_dir / "config.yaml"

    # Try to copy from main config as template, or create minimal
    main_config = REPO_ROOT / ".hermes" / "config.yaml"
    if main_config.exists():
        config_content = main_config.read_text()
        # Update model if present in config
        if "model:" in config_content:
            lines = config_content.split("\n")
            new_lines = []
            for line in lines:
                if line.strip().startswith("model:"):
                    new_lines.append(f"model: {model}")
                else:
                    new_lines.append(line)
            config_content = "\n".join(new_lines)
        config_file.write_text(config_content)
    else:
        # Create minimal config
        config_file.write_text(
            f"# Hermes config for worktree: {name}\n"
            f"model: {model}\n"
            f"worktree: {name}\n"
        )
    print(f"  ✓ Hermes config created (model: {model})")

    # Create a NEXUS.md marker for the worktree
    nexus_file = worktree_path / "NEXUS_WORKTREE.md"
    nexus_file.write_text(
        f"# Worktree: {name}\n\n"
        f"- **Model:** {model}\n"
        f"- **Branch:** {name}\n"
        f"- **Base:** {base_branch}\n"
        f"- **Created:** {datetime.now().isoformat()}\n"
        f"- **Status:** active\n"
    )
    print(f"  ✓ Worktree marker created (NEXUS_WORKTREE.md)")

    # Update state
    state = load_state()
    state["worktrees"][name] = {
        "name": name,
        "path": str(worktree_path),
        "branch": name,
        "base_branch": base_branch,
        "model": model,
        "created": datetime.now().isoformat(),
        "task": task,
        "status": "active",
    }
    save_state(state)

    print(f"\n  ✓ Worktree '{name}' initialized and ready")
    print(f"  → cd {worktree_path}")
    print(f"  → Start working with model: {model}")


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
  %(prog)s list --json
  %(prog)s status --name fix-streaming
  %(prog)s collect --name fix-streaming
  %(prog)s destroy --name fix-streaming
  %(prog)s remote --name heavy-research --server rapidwebs-01 --task "Deep research"
  %(prog)s sync --server rapidwebs-01
  %(prog)s doctor
  %(prog)s init --name worker-foo --model openrouter/owl-alpha
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
    p_list = subparsers.add_parser("list", help="List all worktrees")
    p_list.add_argument("--json", action="store_true", help="Output as JSON for machine readability")

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

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync worktree state with a remote server")
    p_sync.add_argument("--server", required=True, help="SSH server alias to sync with")
    p_sync.add_argument("--repo", default="/home/sysop/Workspaces/NexusAgent", help="Remote repo path")

    # doctor
    subparsers.add_parser("doctor", help="Diagnose common worktree issues")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a worktree with full configuration")
    p_init.add_argument("--name", required=True, help="Worktree name")
    p_init.add_argument("--model", default="openrouter/owl-alpha", help="Model to use (default: openrouter/owl-alpha)")
    p_init.add_argument("--base-branch", default="master", help="Base branch (default: master)")
    p_init.add_argument("--task", default="", help="Task description")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure we're in a git repo
    check_git_repo()

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "collect": cmd_collect,
        "destroy": cmd_destroy,
        "remote": cmd_remote,
        "status": cmd_status,
        "sync": cmd_sync,
        "doctor": cmd_doctor,
        "init": cmd_init,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
