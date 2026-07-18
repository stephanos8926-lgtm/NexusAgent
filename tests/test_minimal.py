#!/usr/bin/env python3
"""Minimal connection test."""
import asyncio

import websockets

API_KEY = "nexus-2638f25daba9af9c"

async def test():
    print("🚀 Starting connection test...")
    session_id = "test-12345"
    url = f"ws://localhost:8000/sessions/{session_id}/ws"
    print(f"Connecting to {url}")

    try:
        ws = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {API_KEY}"},
            open_timeout=5
        )
        print("✅ Connected!")

        # Send a test message
        await ws.send('{"type": "user_message", "content": "Hello"}')
        print("📤 Sent message")

        # Wait for response
        response = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f"📥 Received: {response[:100]}...")

        await ws.close()
        print("✅ Test PASSED")
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test())
    exit(0 if result else 1)
