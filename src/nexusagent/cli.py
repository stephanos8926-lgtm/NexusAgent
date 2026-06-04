# src/nexusagent/cli.py
import argparse
import asyncio
import logging

from nexusagent.sdk import sdk
from nexusagent.config import settings

# Setup logging for CLI
logging.basicConfig(level=settings.log_level, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def run_client() -> None:
    parser = argparse.ArgumentParser(description="NexusAgent CLI Client")
    parser.add_argument("task", help="The coding task for the agent")
    args = parser.parse_args()
    
    try:
        # Use the SDK instead of raw bus for consistency
        task_id = await sdk.submit_task({"description": args.task})
        logger.info(f"Task submitted successfully. Task ID: {task_id}")
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")

def main() -> None:
    asyncio.run(run_client())

if __name__ == "__main__":
    main()
