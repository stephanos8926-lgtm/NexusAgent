import nats
import asyncio

class AgentBus:
    def __init__(self, url="nats://localhost:4222"):
        self.url = url
        self.nc = None

    async def connect(self):
        self.nc = await nats.connect(self.url)

    async def publish(self, subject, message):
        await self.nc.publish(subject, message.encode())

    async def close(self):
        await self.nc.close()
