import asyncio
import nats

async def main():
    nc = await nats.connect("nats://localhost:4222")
    print("Connected!")
    await nc.close()

asyncio.run(main())
