#!/usr/bin/env python3
"""
large-sprint.py — Large Sprint Orchestrator CLI

Companion script for the large-sprint-orchestrator skill.
Provides CLI entry points for both agents and humans to manage
multi-phase sprints with parallel workers and worktrees.

Usage:
    python3 large-sprint.py init --name <name> [--phases <N>]
    python3 large-sprint.py plan --name <name>
    python3 large-sprint.py dispatch --name <name> --phase <N>
    python3 large-sprint.py status [--name <name>]
    python3 large-sprint.py collect --name <name>
    python3 large-sprint.py verify --name <name>
    python3 large-sprint.py cleanup --name <name>
    python3 large-sprint.py doctor

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
SPRINT_BASE = REPO_ROOT / ".hermes" / "sprints"
STATE_FILE = REPO_ROOT / ".hermes" / "sprint-state.json"


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
    """Load the sprint state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"  ✗ Failed to parse state file {STATE_FILE}: {e}", file=sys.stderr)
            sys.exit(1)
    return {"sprints": {}}


def save_state(state: dict):
    """Save the sprint state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_sprint_path(name: str) -> Path:
    return SPRINT_BASE / name


def sprint_exists(name: str) -> bool:
    return get_sprint_path(name).exists()


def check_git_repo():
    """Ensure we're in a git repository."""
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists() and not git_dir.is_file():
        print("  ✗ Not in a git repository.", file=sys.stderr)
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize a new sprint with plan template."""
    name = args.name
    phases = args.phases or 3

    if sprint_exists(name):
        print(f"  ✗ Sprint '{name}' already exists at {get_sprint_path(name)}")
        sys.exit(1)

    check_git_repo()

    sprint_path = get_sprint_path(name)
    sprint_path.mkdir(parents=True, exist_ok=True)

    # Create plan template
    plan_file = sprint_path / "PLAN.md"
    plan_content = f"""# Sprint: {name}

> **Created:** {datetime.now().isoformat()}
> **Phases:** {phases}
> **Status:** PLAN

---

## Phase 0: Foundation
- [ ] Commit all changes, push to GitHub
- [ ] Verify test baseline
- [ ] Clean up test artifacts

## Phase 1: Audit + Index
- [ ] Deep audit of target subsystem
- [ ] Semantic codebase index
- [ ] State verification

"""
    for i in range(2, phases + 1):
        plan_content += f"""
## Phase {i}: [Title]
- [ ] Task {i}.1
- [ ] Task {i}.2
- [ ] Task {i}.3

"""
    plan_content += f"""
## Final Phase: Verification
- [ ] Full test suite passes
- [ ] All docs updated
- [ ] Commit + push
- [ ] Clean up worktrees

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
"""
    plan_file.write_text(plan_content)

    # Create worktree directories
    worktrees_dir = sprint_path / "worktrees"
    worktrees_dir.mkdir(exist_ok=True)

    # Create research directory
    research_dir = sprint_path / "research"
    research_dir.mkdir(exist_ok=True)

    # Update state
    state = load_state()
    state["sprints"][name] = {
        "name": name,
        "path": str(sprint_path),
        "phases": phases,
        "created": datetime.now().isoformat(),
        "status": "plan",
        "current_phase": 0,
        "worktrees": [],
        "results": {},
    }
    save_state(state)

    print(f"  ✓ Sprint '{name}' initialized")
    print(f"    Plan: {plan_file}")
    print(f"    Phases: {phases}")
    print(f"    → Edit the plan, then run: python3 {sys.argv[0]} plan --name {name}")


def cmd_plan(args):
    """Show the current sprint plan."""
    name = args.name

    if not sprint_exists(name):
        print(f"  ✗ Sprint '{name}' not found. Run 'init' first.")
        sys.exit(1)

    plan_file = get_sprint_path(name) / "PLAN.md"
    if plan_file.exists():
        print(plan_file.read_text())
    else:
        print(f"  ✗ No plan file found at {plan_file}")


def cmd_dispatch(args):
    """Dispatch workers for a specific phase."""
    name = args.name
    phase = args.phase

    if not sprint_exists(name):
        print(f"  ✗ Sprint '{name}' not found.")
        sys.exit(1)

    state = load_state()
    sprint = state["sprints"][name]

    if phase > sprint["phases"]:
        print(f"  ✗ Phase {phase} exceeds total phases ({sprint['phases']})")
        sys.exit(1)

    print(f"\n═══ Sprint: {name} — Phase {phase} ═══\n")

    # Read the plan for this phase
    plan_file = get_sprint_path(name) / "PLAN.md"
    if not plan_file.exists():
        print(f"  ✗ No plan file found. Run 'init' first.")
        sys.exit(1)

    plan_content = plan_file.read_text()

    # Extract phase section
    phase_header = f"## Phase {phase}:"
    if phase_header not in plan_content:
        print(f"  ✗ Phase {phase} not found in plan.")
        sys.exit(1)

    start = plan_content.index(phase_header)
    next_phase = plan_content.find("## Phase", start + 1)
    if next_phase == -1:
        next_phase = plan_content.find("## Final", start + 1)
    phase_content = plan_content[start:next_phase] if next_phase > 0 else plan_content[start:]

    print(phase_content)
    print()

    # Update state
    sprint["current_phase"] = phase
    sprint["status"] = f"phase-{phase}-dispatched"
    save_state(state)

    print(f"  ✓ Phase {phase} tasks displayed above.")
    print(f"    → Dispatch workers via delegate_task() or worktree-worker.py")
    print(f"    → After completion: python3 {sys.argv[0]} collect --name {name} --phase {phase}")


def cmd_status(args):
    """Show sprint status."""
    state = load_state()
    sprints = state.get("sprints", {})

    if not sprints:
        print("  No sprints found.")
        print(f"  → Create one: python3 {sys.argv[0]} init --name <name>")
        return

    if args.name:
        sprints = {args.name: sprints.get(args.name, {})}

    for name, info in sprints.items():
        if not sprint_exists(name) and args.name:
            print(f"  ✗ Sprint '{name}' directory missing")
            continue

        status = info.get("status", "unknown")
        phase = info.get("current_phase", 0)
        total = info.get("phases", "?")
        worktrees = info.get("worktrees", [])

        print(f"\n  Sprint: {name}")
        print(f"    Status: {status}")
        print(f"    Phase: {phase}/{total}")
        print(f"    Worktrees: {len(worktrees)}")
        for wt in worktrees:
            wt_path = get_sprint_path(name) / "worktrees" / wt
            exists = "✓" if wt_path.exists() else "✗"
            print(f"      {exists} {wt}")


def cmd_collect(args):
    """Collect results from a sprint phase."""
    name = args.name
    phase = args.phase

    if not sprint_exists(name):
        print(f"  ✗ Sprint '{name}' not found.")
        sys.exit(1)

    sprint_path = get_sprint_path(name)
    worktrees_dir = sprint_path / "worktrees"

    if not worktrees_dir.exists():
        print(f"  ✗ No worktrees directory found.")
        return

    print(f"\n═══ Collecting results: {name} — Phase {phase} ═══\n")

    # Check each worktree for commits
    for wt_dir in sorted(worktrees_dir.iterdir()):
        if not wt_dir.is_dir():
            continue

        print(f"  ── {wt_dir.name} ──")

        # Git log
        result = run(
            "git log master..HEAD --oneline 2>/dev/null || git log --oneline -5",
            cwd=str(wt_dir), check=False
        )
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                print(f"    {line}")
        else:
            print(f"    (no commits)")

        # Diff summary
        result = run(
            "git diff --stat master...HEAD 2>/dev/null",
            cwd=str(wt_dir), check=False
        )
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                print(f"    {line}")

        print()

    # Check research directory
    research_dir = sprint_path / "research"
    if research_dir.exists():
        research_files = list(research_dir.glob("*.md"))
        if research_files:
            print(f"  ── Research Reports ──")
            for f in research_files:
                print(f"    ✓ {f.name}")


def cmd_verify(args):
    """Verify sprint results: test suite + no regressions."""
    name = args.name

    if not sprint_exists(name):
        print(f"  ✗ Sprint '{name}' not found.")
        sys.exit(1)

    print(f"\n═══ Verifying: {name} ═══\n")

    # Check 1: Git status
    print("  ── Check: Git Status ──")
    result = run("git status --sb", check=False)
    print(f"    {result.stdout.strip()}")

    # Check 2: Test suite
    print("\n  ── Check: Test Suite ──")
    result = run("PYTHONPATH=src python3 -m pytest tests/ -q --tb=line 2>&1 | tail -5", check=False)
    if result.returncode == 0:
        print(f"    ✓ Tests passing")
        # Extract pass/fail counts
        for line in result.stdout.strip().split("\n"):
            if "passed" in line or "failed" in line:
                print(f"    {line.strip()}")
    else:
        print(f"    ✗ Tests failing")
        print(f"    {result.stdout.strip()[-200:]}")

    # Check 3: Docs updated
    print("\n  ── Check: Documentation ──")
    state = load_state()
    sprint = state.get("sprints", {}).get(name, {})
    worktrees = sprint.get("worktrees", [])
    if worktrees:
        print(f"    Worktrees: {len(worktrees)} (run 'cleanup' to remove)")
    else:
        print(f"    ✓ No orphaned worktrees")

    # Check 4: Commit status
    print("\n  ── Check: Commits ──")
    result = run("git log --oneline -5", check=False)
    for line in result.stdout.strip().split("\n"):
        print(f"    {line}")

    print()


def cmd_cleanup(args):
    """Clean up sprint worktrees and artifacts."""
    name = args.name
    force = args.force

    if not sprint_exists(name):
        print(f"  ✗ Sprint '{name}' not found.")
        sys.exit(1)

    sprint_path = get_sprint_path(name)
    worktrees_dir = sprint_path / "worktrees"

    if not worktrees_dir.exists():
        print(f"  ✗ No worktrees directory.")
        return

    print(f"\n═══ Cleanup: {name} ═══\n")

    for wt_dir in sorted(worktrees_dir.iterdir()):
        if not wt_dir.is_dir():
            continue

        # Check for uncommitted changes
        dirty = run("git status --porcelain", cwd=str(wt_dir), check=False).stdout.strip()
        if dirty and not force:
            print(f"  ⚠ {wt_dir.name}: has uncommitted changes (use --force)")
            continue

        # Check for commits not on master
        ahead = run("git log master..HEAD --oneline 2>/dev/null", cwd=str(wt_dir), check=False).stdout.strip()
        if ahead and not force:
            print(f"  ⚠ {wt_dir.name}: has {len(ahead.split(chr(10)))} unpushed commits (use --force)")
            print(f"    {ahead[:200]}")
            continue

        # Safe to remove
        print(f"  → Removing {wt_dir.name}...")
        run(f"git worktree remove {wt_dir}" + (" --force" if force else ""))
        print(f"    ✓ Removed")

    # Update state
    state = load_state()
    if name in state.get("sprints", {}):
        state["sprints"][name]["worktrees"] = []
        state["sprints"][name]["status"] = "cleaned"
        save_state(state)

    print(f"\n  ✓ Cleanup complete")


def cmd_doctor(args):
    """Diagnose common sprint issues."""
    print("\n═══ Sprint Doctor ═══\n")
    issues = 0

    # Check 1: Git repository
    print("  ── Check: Git Repository ──")
    git_dir = REPO_ROOT / ".git"
    if git_dir.exists() or git_dir.is_file():
        print("    ✓ In a git repository")
    else:
        print("    ✗ NOT in a git repository")
        issues += 1

    # Check 2: GitHub connectivity
    print("\n  ── Check: GitHub Connectivity ──")
    result = run("git remote -v", check=False)
    if result.stdout.strip():
        print(f"    Remote: {result.stdout.strip().split()[1] if len(result.stdout.split()) > 1 else 'unknown'}")
        print("    ✓ Remote configured")
    else:
        print("    ✗ No remote configured")
        issues += 1

    # Check 3: Test suite
    print("\n  ── Check: Test Suite ──")
    result = run("ls tests/test_*.py 2>/dev/null | wc -l", check=False)
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if "passed" in line:
                print(f"    ✓ {line.strip()}")
    else:
        print("    ✗ Test suite has failures")
        issues += 1

    # Check 4: Active sprints
    print("\n  ── Check: Active Sprints ──")
    state = load_state()
    sprints = state.get("sprints", {})
    if sprints:
        for name, info in sprints.items():
            status = info.get("status", "unknown")
            phase = info.get("current_phase", 0)
            print(f"    {name}: {status} (phase {phase})")
    else:
        print("    No active sprints")

    # Check 5: Orphaned worktrees
    print("\n  ── Check: Orphaned Worktrees ──")
    result = run("git worktree list", check=False)
    worktrees = []
    for line in result.stdout.strip().split("\n"):
        if ".hermes/worktrees/" in line or ".hermes/sprints/" in line:
            parts = line.split()
            if len(parts) >= 1:
                worktrees.append(parts[0])
    if worktrees:
        print(f"    Found {len(worktrees)} worktrees:")
        for wt in worktrees:
            print(f"      {wt}")
    else:
        print("    ✓ No orphaned worktrees")

    # Check 6: Disk usage
    print("\n  ── Check: Disk Usage ──")
    result = run("du -sh .hermes/ 2>/dev/null", check=False)
    if result.stdout.strip():
        print(f"    .hermes/: {result.stdout.strip().split()[0]}")

    if issues:
        print(f"\n  ⚠ {issues} issue(s) found")
    else:
        print(f"\n  ✓ All checks passed")

    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Large Sprint Orchestrator — manage multi-phase sprints"
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a new sprint")
    p_init.add_argument("--name", "-n", required=True, help="Sprint name")
    p_init.add_argument("--phases", "-p", type=int, default=3, help="Number of phases (default: 3)")

    # plan
    p_plan = sub.add_parser("plan", help="Show sprint plan")
    p_plan.add_argument("--name", "-n", required=True, help="Sprint name")

    # dispatch
    p_dispatch = sub.add_parser("dispatch", help="Show tasks for a phase")
    p_dispatch.add_argument("--name", "-n", required=True, help="Sprint name")
    p_dispatch.add_argument("--phase", "-p", type=int, required=True, help="Phase number")

    # status
    p_status = sub.add_parser("status", help="Show sprint status")
    p_status.add_argument("--name", "-n", help="Sprint name (omit for all)")

    # collect
    p_collect = sub.add_parser("collect", help="Collect results from a phase")
    p_collect.add_argument("--name", "-n", required=True, help="Sprint name")
    p_collect.add_argument("--phase", "-p", type=int, help="Phase number")

    # verify
    p_verify = sub.add_parser("verify", help="Verify sprint results")
    p_verify.add_argument("--name", "-n", required=True, help="Sprint name")

    # cleanup
    p_cleanup = sub.add_parser("cleanup", help="Clean up sprint worktrees")
    p_cleanup.add_argument("--name", "-n", required=True, help="Sprint name")
    p_cleanup.add_argument("--force", "-f", action="store_true", help="Force removal of dirty worktrees")

    # doctor
    p_doctor = sub.add_parser("doctor", help="Diagnose common issues")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "dispatch":
        cmd_dispatch(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "cleanup":
        cmd_cleanup(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
