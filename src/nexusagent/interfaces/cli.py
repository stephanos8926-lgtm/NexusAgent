# src/nexusagent/cli.py
import asyncio
import logging
import re
import tomllib
from importlib.metadata import version as pkg_version
from pathlib import Path

import click


CLIENT_VERSION = "0.1.0"


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
            "Warning: Unable to reach server. "
            "Use --skip-version-check to bypass.",
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
@click.option("--skip-version-check", is_flag=True, default=False, help="Skip preflight version check.")
def submit(task, skip_version_check):
    """Submit a coding task to the agent service.

    Example:
        nexus-client submit "Fix the auth bug in server.py"
    """
    from nexusagent.infrastructure.config import settings

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
@click.option("--summary-only", is_flag=True, default=False, help="Return only summary (not full output)")
@click.option("--skip-version-check", is_flag=True, default=False, help="Skip preflight version check.")
def run(task, working_dir, max_turns, wall_time, memory_mode, acceptance, model, max_depth, summary_only, skip_version_check):
    """Spawn an isolated worker to complete a task.

    Example:
        nexus run "Fix the auth bug in server.py" -d /project -t 20 -a "Tests pass"
        nexus run "Research X" --model gemini-3.1-flash-lite --max-depth 5 --summary-only
    """
    from nexusagent.llm.models import MemoryScope, TaskContract
    from nexusagent.core.worker import worker_pool

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
@click.option("--status", "-s", default=None, type=click.Choice(["active", "idle", "closed"]), help="Filter by status")
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
    from nexusagent.infrastructure.db import session_repo

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
                click.echo(f"Failed. Session {session_id} not found or {new_id} already exists.", err=True)

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


if __name__ == "__main__":
    main()
