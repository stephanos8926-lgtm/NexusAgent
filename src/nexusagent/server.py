import asyncio
import nats
import sys
import yaml
from pathlib import Path
from nexusagent.graph import create_graph

async def run_server_async():
    print("Starting server...", file=sys.stderr, flush=True)
    
    config_path = Path(__file__).parent.parent.parent / "config" / "nexusagent.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    prompt_path = Path(__file__).parent.parent.parent / "config" / "system_prompt.txt"
    with open(prompt_path, "r") as f:
        system_prompt = f.read()
    
    nc = await nats.connect(config["server"]["nats_url"])
    print("Connected to NATS", file=sys.stderr, flush=True)
    
    graph = create_graph(config["server"]["db_path"])
    print("Graph created", file=sys.stderr, flush=True)

    async def handle_task(msg):
        task_data = msg.data.decode()
        print(f"Received task: {task_data}", file=sys.stderr, flush=True)
        # Using the loaded system_prompt somewhere...
        config_data = {"configurable": {"thread_id": "test-thread"}}
        graph.invoke({"plan": task_data, "code": "", "system_prompt": system_prompt}, config=config_data)
        print("Task completed.", file=sys.stderr, flush=True)

    await nc.subscribe("task.new", cb=handle_task)
    print("NexusAgent Server listening on task.new...", file=sys.stderr, flush=True)
    await asyncio.Future()

def run_server():
    asyncio.run(run_server_async())

if __name__ == "__main__":
    run_server()
