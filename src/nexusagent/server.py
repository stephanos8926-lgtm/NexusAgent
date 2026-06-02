# src/nexusagent/server.py
import asyncio
import nats
from nexusagent.graph import create_graph

async def run_server():
    # 1. Connect to NATS
    nc = await nats.connect("nats://localhost:4222")
    
    # 2. Setup the graph
    graph = create_graph("nexus.db")

    async def handle_task(msg):
        task_data = msg.data.decode()
        print(f"Received task: {task_data}")
        # Run the graph
        await graph.ainvoke({"plan": task_data, "code": ""})
        print("Task completed.")

    # 3. Subscribe to the task topic
    await nc.subscribe("task.new", cb=handle_task)
    print("NexusAgent Server listening on task.new...")

    # Keep alive
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(run_server())
