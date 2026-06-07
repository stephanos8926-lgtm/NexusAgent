# src/nexusagent/cli.py
import argparse
import asyncio
import logging
import tomllib
from importlib.metadata import version as pkg_version
from pathlib import Path

def get_version() -> str:
    try:
        return pkg_version("nexusagent")
    except Exception:
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        pyproject_path = BASE_DIR / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]

def main() -> None:
    parser = argparse.ArgumentParser(description="NexusAgent CLI Client")
    parser.add_argument("task", help="The coding task for the agent")
    parser.add_argument("--version", action="version", version=f"nexusagent {get_version()}")
    args = parser.parse_args()

    # Setup logging for CLI (only when not just printing version)
    from nexusagent.config import settings
    logging.basicConfig(level=settings.log_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    async def run_client() -> None:
        try:
            # Use the SDK instead of raw bus for consistency
            from nexusagent.sdk import sdk
            task_id = await sdk.submit_task({"description": args.task})
            logger.info(f"Task submitted successfully. Task ID: {task_id}")
        except Exception as e:
            # Check if it's a NATS connection error
            if "NATS" in str(type(e)) or "nats" in str(type(e)).lower():
                logger.error("Error: Unable to connect to the NexusAgent service. Please ensure the service is running and try again.")
            else:
                logger.error(f"Error: Failed to submit task: {e}")

    asyncio.run(run_client())

if __name__ == "__main__":
    main()