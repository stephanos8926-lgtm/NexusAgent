# src/nexusagent/cli.py
import asyncio
import logging
import tomllib
from importlib.metadata import version as pkg_version
from pathlib import Path

import click


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
def main() -> None:
    """NexusAgent CLI Client."""


@main.command()
@click.argument("task")
def submit(task):
    """Submit a coding task to the agent service.

    Example:
        nexus-client submit "Fix the auth bug in server.py"
    """
    from nexusagent.config import settings

    logging.basicConfig(level=settings.log_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    async def run_client() -> None:
        try:
            from nexusagent.sdk import sdk

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
@click.option("--memory-mode", "-m", default="isolated",
              type=click.Choice(["isolated", "scoped", "shared"]))
@click.option("--acceptance", "-a", multiple=True, help="Acceptance criteria")
def run(task, working_dir, max_turns, wall_time, memory_mode, acceptance):
    """Spawn an isolated worker to complete a task.

    Example:
        nexus run "Fix the auth bug in server.py" -d /project -t 20 -a "Tests pass"
    """
    from nexusagent.models import MemoryScope, TaskContract
    from nexusagent.worker import worker_pool

    contract = TaskContract(
        task_id=f"cli-{task[:20]}",
        title=task[:50],
        working_dir=working_dir,
        description=task,
        max_turns=max_turns,
        max_wall_time=wall_time,
        acceptance_criteria=list(acceptance) if acceptance else ["Task completed"],
        memory_scope=MemoryScope(memory_mode),
    )

    async def _run():
        handle = await worker_pool.spawn(contract)
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


if __name__ == "__main__":
    main()
