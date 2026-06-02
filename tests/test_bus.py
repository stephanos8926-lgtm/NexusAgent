import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from nexusagent.bus import AgentBus

@pytest.mark.asyncio
async def test_bus_connection():
    bus = AgentBus()
    assert bus.url == "nats://localhost:4222"
