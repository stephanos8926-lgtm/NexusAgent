import asyncio
import sys
import nats
from pathlib import Path
from nexusagent.graph import create_graph
from nexusagent.config import load_config

async def run_worker():
    config = load_config()
    
    prompt_path = Path(__file__).parent.parent.parent / "config" / "system_prompt.txt"
    with open(prompt_path, "r") as f:
        system_prompt = f.read()
    
    nc = await nats.connect(config.nats_url)
    print("Connected to NATS", file=sys.stderr, flush=True)
    
    graph = create_graph(config.db_path)
    print("Graph created", file=sys.stderr, flush=True)

    async def handle_task(msg):
        task_data = msg.data.decode()
        print(f"Received task: {task_data}", file=sys.stderr, flush=True)
        config_data = {"configurable": {"thread_id": "test-thread"}}
        await graph.ainvoke({"plan": task_data, "code": "", "system_prompt": system_prompt}, config=config_data)
        print("Task completed.", file=sys.stderr, flush=True)

    await nc.subscribe("task.new", cb=handle_task)
    print("NexusAgent Worker listening on task.new...", file=sys.stderr, flush=True)
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(run_worker())
