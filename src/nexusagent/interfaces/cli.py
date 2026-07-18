"""NexusAgent Command Line Interface (CLI).

Provides Click-based CLI commands for interacting with the NexusAgent service,
including task submission, worker execution, session management, and hook control.
"""

# src/nexusagent/cli.py
import asyncio
import logging
import re
import tomllib
from importlib.metadata import version as pkg_version
from pathlib import Path

import click

CLIENT_VERSION = "0.1.0"


def _validate_working_dir(working_dir: str) -> None:
    """Validate working_dir doesn't escape via path traversal."""
    from pathlib import Path

    resolved = Path(working_dir).resolve()
    # Ensure the path exists and is a directory
    if not resolved.is_dir():
        raise SystemExit(f"Error: working_dir '{working_dir}' is not a valid directory")


def parse_version(v: str) -> tuple[int, int, int]:
    """Parse a semver string into a (major, minor, patch) tuple.

    Strips pre-release suffixes like '-rc1', '+build123'.
    Missing segments default to 0.
    """
    # Strip pre-release and build metadata
    clean = re.split(r"[+-]", v)[0]
    parts = clean.split(".")
    nums = [int(p) for p in parts if p.isdigit()]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def is_compatible(server_ver: str, client_ver: str) -> bool:
    """Check compatibility: same MAJOR version.

    Compatible if major versions match. Client newer than server can degrade.
    Server newer than client supports more features. Different major = breaking.
    """
    s = parse_version(server_ver)
    c = parse_version(client_ver)
    return s[0] == c[0]


async def preflight() -> bool:
    """Run preflight version check against the server.

    Returns True if server is reachable (version mismatch is a warning, not fatal).
    Returns False if server is unreachable.
    """
    from nexusagent.server.sdk import sdk

    try:
        health = await sdk.health_check()
    except Exception:
        click.echo(
            "Warning: Unable to reach server. Use --skip-version-check to bypass.",
            err=True,
        )
        return False

    server_ver = health.get("version", "unknown")
    if not is_compatible(server_ver, CLIENT_VERSION):
        click.echo(
            f"Warning: Server version {server_ver} may be incompatible "
            f"with client version {CLIENT_VERSION}.",
            err=True,
        )
    return True


def get_version() -> str:
    """Get the installed nexusagent package version.

    Tries importlib.metadata first, then falls back to reading pyproject.toml.
    """
    try:
        return pkg_version("nexusagent")
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent
        pyproject_path = base_dir / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]


@click.group()
@click.version_option(version=f"nexusagent {get_version()}")
@click.option("--check-server", is_flag=True, default=False, help="Check server version and exit.")
@click.pass_context
def main(ctx, check_server) -> None:
    """NexusAgent CLI Client."""
    ctx.ensure_object(dict)
    ctx.obj["check_server"] = check_server


@main.command()
@click.argument("task")
@click.option(
    "--skip-version-check", is_flag=True, default=False, help="Skip preflight version check."
)
def submit(task, skip_version_check):
    """Submit a coding task to the agent service.

    Example:
        nexus-client submit "Fix the auth bug in server.py"
    """
    from nexusagent.infrastructure.config import (
        settings,
    )

    # Handle --check-server
    # (check_server is accessed via the parent context in click)
    logging.basicConfig(level=settings.log_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    async def run_client() -> None:
        if not skip_version_check:
            ok = await preflight()
            if not ok:
                click.echo(
                    "Preflight failed. Use --skip-version-check to proceed anyway.",
                    err=True,
                )
                raise SystemExit(1)

        try:
            from nexusagent.server.sdk import sdk

            task_id = await sdk.submit_task({"description": task})
            logger.info(f"Task submitted successfully. Task ID: {task_id}")
        except Exception as e:
            if "NATS" in str(type(e)) or "nats" in str(type(e)).lower():
                logger.error(
                    "Error: Unable to connect to the NexusAgent service. "
                    "Please ensure the service is running and try again."
                )
            else:
                logger.error(f"Error: Failed to submit task: {e}")

    asyncio.run(run_client())


@main.command()
@click.argument("task")
@click.option("--working-dir", "-d", default=".", help="Working directory")
@click.option("--max-turns", "-t", default=20, help="Max agent turns")
@click.option("--wall-time", "-w", default=1800.0, help="Wall time limit (seconds)")
@click.option(
    "--memory-mode", "-m", default="isolated", type=click.Choice(["isolated", "scoped", "shared"])
)
@click.option("--acceptance", "-a", multiple=True, help="Acceptance criteria")
@click.option("--model", "-M", default=None, help="Model override for this agent")
@click.option("--max-depth", default=3, help="Max sub-agent nesting depth")
@click.option(
    "--summary-only", is_flag=True, default=False, help="Return only summary (not full output)"
)
@click.option(
    "--skip-version-check", is_flag=True, default=False, help="Skip preflight version check."
)
def run(
    task,
    working_dir,
    max_turns,
    wall_time,
    memory_mode,
    acceptance,
    model,
    max_depth,
    summary_only,
    skip_version_check,
):
    """Spawn an isolated worker to complete a task.

    Example:
        nexus run "Fix the auth bug in server.py" -d /project -t 20 -a "Tests pass"
        nexus run "Research X" --model gemini-3.1-flash-lite --max-depth 5 --summary-only
    """
    from nexusagent.core.worker import worker_pool
    from nexusagent.llm.models import MemoryScope, TaskContract

    # Validate working_dir is within workspace
    _validate_working_dir(working_dir)

    contract = TaskContract(
        task_id=f"cli-{task[:20]}",
        title=task[:50],
        working_dir=working_dir,
        description=task,
        max_turns=max_turns,
        max_wall_time=wall_time,
        acceptance_criteria=list(acceptance) if acceptance else ["Task completed"],
        memory_scope=MemoryScope(memory_mode),
        model=model,
        max_depth=max_depth,
        summary_only=summary_only,
    )

    async def _run():
        if not skip_version_check:
            ok = await preflight()
            if not ok:
                click.echo(
                    "Preflight failed. Use --skip-version-check to proceed anyway.",
                    err=True,
                )
                raise SystemExit(1)

        handle = await worker_pool.spawn(contract, depth=0)
        click.echo(f"Spawned worker {handle.worker_id}")

        try:
            result = await handle.wait(timeout=wall_time + 60)
            click.echo(f"Result: {result}")
        except TimeoutError:
            click.echo("Timed out. Cancelling...")
            await handle.cancel()
        except RuntimeError as e:
            click.echo(f"Failed: {e}", err=True)

    asyncio.run(_run())


@main.command("session")
@click.argument("action", type=click.Choice(["list", "resume", "fork", "rename", "delete"]))
@click.argument("session_id", required=False)
@click.option("--new-id", "-n", default=None, help="New session ID (for rename/fork)")
@click.option("--working-dir", "-d", default=None, help="Working directory (for fork)")
@click.option(
    "--status",
    "-s",
    default=None,
    type=click.Choice(["active", "idle", "closed"]),
    help="Filter by status",
)
@click.option("--limit", "-l", default=20, help="Max results")
def session_cmd(action, session_id, new_id, working_dir, status, limit):
    """Manage interactive sessions.

    Actions:
        list    — List sessions (optionally filter by status)
        resume  — Print session info (use with nexus run to reconnect)
        fork    — Copy a session to a new ID
        rename  — Rename a session
        delete  — Delete a session and its messages

    Examples:
        nexus session list
        nexus session list --status active
        nexus session resume abc123
        nexus session fork abc123 --new-id xyz789
        nexus session rename abc123 --new-id xyz789
        nexus session delete abc123
    """
    from nexusagent.infrastructure.db import get_session_repo

    session_repo = get_session_repo()

    async def _run():
        if action == "list":
            sessions = await session_repo.list_sessions(status=status, limit=limit)
            if not sessions:
                click.echo("No sessions found.")
                return
            click.echo(f"{'ID':<40} {'Status':<10} {'Working Dir':<30} {'Updated':<20}")
            click.echo("-" * 100)
            for s in sessions:
                updated = s["updated_at"][:19] if s["updated_at"] else "unknown"
                click.echo(f"{s['id']:<40} {s['status']:<10} {s['working_dir']:<30} {updated:<20}")

        elif action == "resume":
            if not session_id:
                click.echo("Error: session_id required", err=True)
                return
            s = await session_repo.get_session(session_id)
            if not s:
                click.echo(f"Session {session_id} not found.", err=True)
                return
            click.echo(f"Session: {s['id']}")
            click.echo(f"  Status: {s['status']}")
            click.echo(f"  Working Dir: {s['working_dir']}")
            click.echo(f"  Created: {s['created_at']}")
            click.echo(f"  Updated: {s['updated_at']}")

        elif action == "fork":
            if not session_id:
                click.echo("Error: session_id required", err=True)
                return
            new_id_res = await session_repo.fork_session(session_id, working_dir)
            if new_id_res:
                click.echo(f"Forked {session_id} → {new_id_res}")
            else:
                click.echo(f"Session {session_id} not found.", err=True)

        elif action == "rename":
            if not session_id or not new_id:
                click.echo("Error: session_id and --new-id required", err=True)
                return
            ok = await session_repo.rename_session(session_id, new_id)
            if ok:
                click.echo(f"Renamed {session_id} → {new_id}")
            else:
                click.echo(
                    f"Failed. Session {session_id} not found or {new_id} already exists.", err=True
                )

        elif action == "delete":
            if not session_id:
                click.echo("Error: session_id required", err=True)
                return
            ok = await session_repo.delete_session(session_id)
            if ok:
                click.echo(f"Deleted {session_id}")
            else:
                click.echo(f"Session {session_id} not found.", err=True)

    asyncio.run(_run())


@main.group("hooks")
def hooks_cmd():
    """Manage hooks (list, enable, disable)."""


@hooks_cmd.command("list")
def hooks_list():
    """List all registered hooks and their status."""
    from nexusagent.hooks import get_hook_manager

    mgr = get_hook_manager()
    hooks = mgr.list_hooks()
    if not hooks:
        click.echo("No hooks registered.")
        return
    click.echo(f"{'Name':<45} {'Event':<22} {'Status'}")
    click.echo("-" * 80)
    for h in hooks:
        status = "enabled" if h.enabled else "disabled"
        click.echo(f"{h.name:<45} {h.event.value:<22} {status}")


@hooks_cmd.command("enable")
@click.argument("hook_name")
def hooks_enable(hook_name):
    """Enable a hook by name."""
    from nexusagent.hooks import get_hook_manager

    mgr = get_hook_manager()
    try:
        mgr.enable_hook(hook_name)
        click.echo(f"Enabled hook '{hook_name}'")
    except KeyError:
        click.echo(f"Hook '{hook_name}' not found.", err=True)


@hooks_cmd.command("disable")
@click.argument("hook_name")
def hooks_disable(hook_name):
    """Disable a hook by name."""
    from nexusagent.hooks import get_hook_manager

    mgr = get_hook_manager()
    try:
        mgr.disable_hook(hook_name)
        click.echo(f"Disabled hook '{hook_name}'")
    except KeyError:
        click.echo(f"Hook '{hook_name}' not found.", err=True)


@main.group("memory")
def memory_cmd():
    """Manage and inspect memory health."""


@memory_cmd.command("health")
@click.option(
    "--workspace",
    "-w",
    default=".",
    help="Workspace directory (defaults to current directory)",
)
def memory_health(workspace):
    """Show memory health report for a workspace.

    Scans the memory bank and displays health metrics including
    duplicates, stale entries, type distribution, and top entities.

    Example:
        nexus memory health
        nexus memory health --workspace /path/to/project
    """
    from nexusagent.memory.dream import DreamCycle

    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        click.echo(f"Error: '{workspace}' is not a valid directory", err=True)
        raise SystemExit(1)

    cycle = DreamCycle(workspace_path)
    report = cycle.scan()
    patterns = cycle.find_patterns()

    # Format health score as percentage
    health_pct = int(report["health_score"] * 100)
    if health_pct >= 80:
        health_status = "GOOD"
    elif health_pct >= 50:
        health_status = "FAIR"
    else:
        health_status = "POOR"

    click.echo("=" * 60)
    click.echo("  MEMORY HEALTH REPORT")
    click.echo("=" * 60)
    click.echo(f"  Workspace: {workspace_path}")
    click.echo("")
    click.echo(f"  Total Memories:   {report['total']}")
    click.echo(f"  Total Entities:   {report.get('total_entities', 0)}")
    click.echo(f"  Health Score:      {health_pct}% [{health_status}]")
    click.echo("")
    click.echo("── Issues ──────────────────────────────────────────")
    click.echo(f"  Duplicates:        {len(report['duplicates'])}")
    click.echo(f"  Stale Entries:     {len(report['stale'])}")
    click.echo(f"  Low Quality:       {len(report['low_quality'])}")

    # Show duplicate details
    if report["duplicates"]:
        click.echo("")
        click.echo("── Duplicate Files ────────────────────────────────")
        for dup in report["duplicates"][:5]:
            click.echo(f"  {dup['duplicate']} (original: {dup['original']})")
        if len(report["duplicates"]) > 5:
            click.echo(f"  ... and {len(report['duplicates']) - 5} more")

    # Show stale details
    if report["stale"]:
        click.echo("")
        click.echo("── Stale Entries (older than 30 days) ─────────────")
        for stale in report["stale"][:5]:
            click.echo(f"  {stale['file']}: {stale['age_days']} days old")
        if len(report["stale"]) > 5:
            click.echo(f"  ... and {len(report['stale']) - 5} more")

    # Show low quality details
    if report["low_quality"]:
        click.echo("")
        click.echo("── Low Quality Entries (score < 0.2) ─────────────")
        for lq in report["low_quality"][:5]:
            click.echo(f"  {lq['file']}: score={lq['score']}")
        if len(report["low_quality"]) > 5:
            click.echo(f"  ... and {len(report['low_quality']) - 5} more")

    # Type distribution
    type_dist = patterns.get("type_distribution", {})
    if type_dist:
        click.echo("")
        click.echo("── Type Distribution ──────────────────────────────")
        for entry_type, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * min(count * 2, 30)
            click.echo(f"  {entry_type:<20} {count:>4}  {bar}")

    # Top entities by frequency
    entity_freq = patterns.get("entity_frequency", {})
    if entity_freq:
        click.echo("")
        click.echo("── Top Entities by Frequency ─────────────────────")
        top_entities = sorted(entity_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        for entity, count in top_entities:
            click.echo(f"  {entity:<25} mentioned {count} time(s)")

    click.echo("")
    click.echo("=" * 60)


@memory_cmd.command("stats")
@click.option(
    "--workspace",
    "-w",
    default=".",
    help="Workspace directory (defaults to current directory)",
)
def memory_stats(workspace):
    """Show memory statistics for a workspace.

    Displays counts by type, average confidence/freshness,
    and git commit count for the memory repo.

    Example:
        nexus memory stats
        nexus memory stats --workspace /path/to/project
    """
    import subprocess

    from nexusagent.memory.dream import DreamCycle

    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        click.echo(f"Error: '{workspace}' is not a valid directory", err=True)
        raise SystemExit(1)

    cycle = DreamCycle(workspace_path)
    report = cycle.scan()
    patterns = cycle.find_patterns()

    click.echo("=" * 60)
    click.echo("  MEMORY STATISTICS")
    click.echo("=" * 60)
    click.echo(f"  Workspace: {workspace_path}")
    click.echo("")
    click.echo(f"  Total Memory Files:  {report['total']}")
    click.echo(f"  Entity Files:        {report.get('total_entities', 0)}")

    # Type distribution
    type_dist = patterns.get("type_distribution", {})
    if type_dist:
        click.echo("")
        click.echo("── Memory Count by Type ──────────────────────────")
        total = sum(type_dist.values())
        for entry_type, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            click.echo(f"  {entry_type:<20} {count:>4}  ({pct:.1f}%)")
        click.echo(f"  {'─' * 46}")
        click.echo(f"  {'Total':<20} {total:>4}")
    elif report["total"] == 0:
        click.echo("")
        click.echo("  No memory files found.")

    # Average confidence and quality
    bank_dir = workspace_path / "bank"
    if bank_dir.exists():
        confidences = []
        quality_scores = []
        for f in bank_dir.glob("*.md"):
            try:
                content = f.read_text()
                fm = DreamCycle._parse_frontmatter(content)
                if "confidence" in fm:
                    confidences.append(float(fm["confidence"]))
                if "quality_score" in fm:
                    quality_scores.append(float(fm["quality_score"]))
            except Exception:
                continue

        click.echo("")
        click.echo("── Confidence & Quality ──────────────────────────")
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            click.echo(f"  Average Confidence:  {avg_conf:.2f}  (from {len(confidences)} entries)")
        else:
            click.echo("  Average Confidence:  N/A (no entries with confidence)")

        if quality_scores:
            avg_qs = sum(quality_scores) / len(quality_scores)
            click.echo(f"  Average Quality:     {avg_qs:.2f}  (from {len(quality_scores)} entries)")
        else:
            click.echo("  Average Quality:     N/A (no entries with quality_score)")

    # Git commit count
    click.echo("")
    click.echo("── Git History ───────────────────────────────────")
    git_dir = workspace_path / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "-C", str(workspace_path), "rev-list", "--count", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                commit_count = result.stdout.strip()
                click.echo(f"  Memory Repo Commits: {commit_count}")
            else:
                click.echo("  Memory Repo Commits: error reading git log")
        except Exception as e:
            click.echo(f"  Memory Repo Commits: error ({e})")
    else:
        click.echo("  Memory Repo Commits: N/A (no .git directory)")

    click.echo("")
    click.echo("=" * 60)


@main.command()
@click.option("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
@click.option("--port", default=8000, type=int, help="Bind port (default: 8000)")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload (dev mode)")
def server(host, port, reload):
    """Start the NexusAgent server.

    Example:
        nexus server
        nexus server --port 9000 --reload
    """
    import uvicorn

    from nexusagent.server.server import app

    click.echo(f"Starting NexusAgent server on {host}:{port}")
    if reload:
        click.echo("Auto-reload enabled (dev mode)")
    uvicorn.run(app, host=host, port=port, reload=reload)


@main.command()
def config_init():
    """Create user config file from project template.

    Copies config/nexusagent.yaml to ~/.nexusagent/config/nexusagent.yaml
    if it doesn't already exist. This is the first thing to run after
    installing NexusAgent.

    Example:
        nexus config init
    """
    from nexusagent.infrastructure.config import create_user_config_from_template
    try:
        config_path = create_user_config_from_template()
        click.echo(f"User config created at: {config_path}")
        click.echo("Edit this file to customize your NexusAgent settings.")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error creating user config: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite existing user config")
def config_reset(force):
    """Reset user config to project template defaults.

    WARNING: This overwrites your existing ~/.nexusagent/config/nexusagent.yaml
    Use --force to confirm.

    Example:
        nexus config reset --force
    """
    from nexusagent.infrastructure.config import get_project_root
    if not force:
        click.echo("Error: Use --force to confirm overwrite", err=True)
        raise SystemExit(1)

    user_config = Path.home() / ".nexusagent" / "config" / "nexusagent.yaml"
    project_root = get_project_root()
    project_config = project_root / "config" / "nexusagent.yaml"

    if not project_config.exists():
        click.echo(f"Error: Project config not found at {project_config}", err=True)
        raise SystemExit(1)

    import shutil
    shutil.copy2(project_config, user_config)
    click.echo(f"User config reset to template: {user_config}")


if __name__ == "__main__":
    main()
