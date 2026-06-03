# Agent B: You are depending on the NexusSDK class and its methods: submit_task, get_status.
from nexusagent.models import TaskSchema, ResultSchema
from nexusagent.auth import AuthManager
from nexusagent.bus import AgentBus
from nexusagent.config import load_config
import asyncio

class NexusSDK:
    def __init__(self):
        self.auth = AuthManager()
        self.config = load_config()
        self.bus = AgentBus(url=self.config.nats_url)

    async def submit_task(self, task: TaskSchema) -> ResultSchema:
        # Auth check
        try:
            self.auth.get_api_key("nats_service")
        except ValueError:
            return ResultSchema(success=False, error="Authentication failed")

        await self._publish_task(task)
        return ResultSchema(success=True, data=f"Task {task.id} submitted")

    async def _publish_task(self, task: TaskSchema):
        await self.bus.connect()
        await self.bus.publish("task.new", task.description)
        await self.bus.close()
        
    def get_status(self, task_id: str) -> str:
        # Status check logic (simulated for now)
        return "pending"
