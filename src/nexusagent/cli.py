# src/nexusagent/cli.py
import argparse
import asyncio
from nexusagent.bus import AgentBus

async def run_cli():
    parser = argparse.ArgumentParser(description="NexusAgent CLI")
    parser.add_argument("task", help="The coding task for the agent")
    args = parser.parse_args()
    
    bus = AgentBus()
    await bus.connect()
    # Publish the task to the NATS bus
    await bus.publish("task.new", args.task)
    print(f"Task submitted: {args.task}")
    await bus.close()

if __name__ == "__main__":
    asyncio.run(run_cli())
