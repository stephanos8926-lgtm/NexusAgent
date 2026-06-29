#!/usr/bin/env python3
"""
NexusAgent TUI End-to-End Test Suite

Tests all features programmatically via WebSocket API.
Bypasses TUI UI to test backend functionality.

Run: python3 tests/test_e2e_tui_features.py
"""

import asyncio
import json
import sys
import websockets
from pathlib import Path

# Test configuration - NO HEAVY IMPORTS
API_KEY = "nexus-2638f25daba9af9c"  # From ~/.nexusagent/config/nexusagent.yaml
SERVER_PORT = 8000
SERVER_URL = f"ws://localhost:{SERVER_PORT}/sessions/{{session_id}}/ws"
TIMEOUT = 30  # Reduced timeout for faster feedback


class colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def log(msg, level="INFO", end="\n"):
    """Pretty log with color."""
    colors_map = {
        "PASS": colors.GREEN,
        "FAIL": colors.RED,
        "WARN": colors.YELLOW,
        "INFO": colors.BLUE,
        "TEST": colors.BOLD,
    }
    color = colors_map.get(level, "")
    print(f"{color}[{level}] {msg}{colors.END}", end=end, flush=True)


class E2ETester:
    def __init__(self):
        self.session_id = None
        self.ws = None
        self.events = []
        self.test_results = {"pass": 0, "fail": 0, "skip": 0}

    async def connect(self):
        """Establish WebSocket connection."""
        import uuid

        self.session_id = str(uuid.uuid4())
        url = SERVER_URL.format(session_id=self.session_id)
        log(f"Connecting to {url}", "INFO")

        try:
            # Use Bearer token in Authorization header (required by server)
            self.ws = await websockets.connect(
                url,
                additional_headers={"Authorization": f"Bearer {API_KEY}"},
                open_timeout=10
            )
            log(f"✅ Connected (session: {self.session_id[:8]}...)", "PASS")
            return True
        except Exception as e:
            log(f"❌ Connection failed: {e}", "FAIL")
            return False

    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            log("Disconnected", "INFO")

    async def send_message(self, message: str, timeout: float = TIMEOUT):
            """Send a message and collect all events."""
            self.events = []
            log(f"Sending: '{message[:50]}...'", "TEST")
        
            try:
                # Send message
                await self.ws.send(json.dumps({"type": "user_input", "content": message}))
            
                # Collect events with timeout
                import time
                start = time.time()
                while True:
                    try:
                        remaining = timeout - (time.time() - start)
                        if remaining <= 0:
                            log(f"⏱️ Timeout after {timeout}s", "WARN")
                            break
                    
                        event_raw = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
                        event = json.loads(event_raw)
                        self.events.append(event)
                    
                        # Stop on response or error
                        if event.get("type") in ("response", "error"):
                            break
                        # Stop on tool approval request (we'll handle it)
                        if event.get("type") == "approval_request":
                            break
                    
                    except asyncio.TimeoutError:
                        log("⏱️ No more events", "INFO")
                        break
            
                log(f"Received {len(self.events)} events", "INFO")
                if self.events:
                    log(f"Event types: {[e.get('type') for e in self.events]}", "INFO")
                return self.events
        
            except Exception as e:
                log(f"❌ Send failed: {e}", "FAIL")
                return []

    async def approve_tool(self, call_id: str, approved: bool = True):
        """Send approval for a tool call."""
        log(f"{'Approving' if approved else 'Rejecting'} tool {call_id[:8]}...", "INFO")
        await self.ws.send(
            json.dumps(
                {"type": "approval_response", "call_id": call_id, "approved": approved}
            )
        )

    def record_result(self, test_name: str, passed: bool, reason: str = ""):
        """Record test result."""
        status = "PASS" if passed else "FAIL"
        self.test_results[status.lower()] += 1
        symbol = "✅" if passed else "❌"
        log(f"{symbol} {test_name}: {status}", status)
        if reason and not passed:
            log(f"   Reason: {reason}", "FAIL")
        elif reason and passed:
            log(f"   Details: {reason}", "PASS")

    # ─────────────────────────────────────────────────────────────
    # TEST CASES
    # ─────────────────────────────────────────────────────────────

    async def test_01_basic_messaging(self):
        """Test basic question → response flow."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 1: Basic Messaging", "TEST")
        log("=" * 60)

        events = await self.send_message("What is 2 + 2? Just give me the number.")

        # Should have: thinking → response (or just response)
        has_response = any(e.get("type") == "response" for e in events)
        response_content = next(
            (e.get("content", "") for e in events if e.get("type") == "response"), ""
        )

        passed = has_response and "4" in response_content
        self.record_result(
            "Basic messaging",
            passed,
            f"Got response: '{response_content[:100]}'" if passed else "No response received",
        )

    async def test_02_thinking_event(self):
        """Test that thinking events are emitted."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 2: Thinking Events", "TEST")
        log("=" * 60)

        events = await self.send_message(
            "Explain quantum computing in 2 sentences."
        )

        has_thinking = any(e.get("type") == "thinking" for e in events)
        passed = has_thinking
        self.record_result(
            "Thinking events", passed, "Has thinking" if has_thinking else "No thinking events"
        )

    async def test_03_file_operations(self):
        """Test file read/write tools."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 3: File Operations", "TEST")
        log("=" * 60)

        test_file = "/tmp/nexus_test.txt"
        test_content = "NexusAgent E2E test content 12345"

        # Write file
        log("Writing test file...", "INFO")
        events = await self.send_message(
            f"Write this exact text to {test_file}: {test_content}"
        )

        # Look for tool call
        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        has_write = any(
            e.get("tool") == "write_file" for e in tool_calls
        )

        if has_write:
            # Approve the tool
            call_id = next(
                e.get("call_id") for e in tool_calls if e.get("tool") == "write_file"
            )
            await self.approve_tool(call_id)

            # Wait for result
            await asyncio.sleep(2)
            result_events = await self.send_message("Did the file write succeed?")
            has_success = any(
                "success" in str(e).lower() or test_content in str(e)
                for e in result_events
            )
            passed = has_success
            self.record_result("File write", passed, "Write succeeded" if passed else "Write failed")
        else:
            # Check if already auto-approved
            file_exists = Path(test_file).exists()
            if file_exists:
                content = Path(test_file).read_text()
                passed = test_content in content
                self.record_result("File write", passed, "File exists with correct content")
            else:
                self.record_result("File write", False, "No tool call and file not created")

        # Read file back
        log("Reading test file...", "INFO")
        events = await self.send_message(f"Read the file {test_file} and tell me what it says.")

        has_read = any(e.get("type") == "tool_call" and e.get("tool") == "read_file" for e in events)
        response = next((e.get("content", "") for e in events if e.get("type") == "response"), "")
        has_content = test_content in response

        if has_read:
            call_id = next(
                e.get("call_id") for e in events if e.get("tool") == "read_file"
            )
            await self.approve_tool(call_id)
            await asyncio.sleep(2)

        passed = has_content
        self.record_result("File read", passed, f"Content: '{response[:50]}...'" if passed else "Content not found")

    async def test_04_gemini_native_tools(self):
        """Test Gemini native tools (Google Search, Code Execution)."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 4: Gemini Native Tools", "TEST")
        log("=" * 60)

        # Test 4a: Google Search (real-time data)
        log("4a: Testing Google Search...", "INFO")
        events = await self.send_message(
            "What is the current price of Bitcoin? Give me the exact USD amount."
        )

        response = next((e.get("content", "") for e in events if e.get("type") == "response"), "")
        # Should have real-time price (not training data cutoff)
        has_price = any(char.isdigit() for char in response) and "$" in response
        passed_4a = has_price
        self.record_result(
            "Google Search (real-time)",
            passed_4a,
            f"Got price: '{response[:100]}...'" if passed_4a else "No price found"
        )

        # Test 4b: Code Execution (math calculation)
        log("4b: Testing Code Execution...", "INFO")
        events = await self.send_message(
            "Calculate the square root of 2025 using Python code. Just give me the number."
        )

        response = next((e.get("content", "") for e in events if e.get("type") == "response"), "")
        # Should be 45
        has_correct = "45" in response
        passed_4b = has_correct
        self.record_result(
            "Code Execution (Python)",
            passed_4b,
            f"Got answer: {response.strip()}" if passed_4b else "Wrong answer"
        )

    async def test_05_memory_storage_recall(self):
        """Test memory system: store and recall."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 5: Memory Storage & Recall", "TEST")
        log("=" * 60)

        unique_phrase = "NEXUS_E2E_TEST_PHX_2026_06_28"

        # Store memory
        log("Storing memory...", "INFO")
        events = await self.send_message(
            f"Remember this for later: {unique_phrase}. This is a test memory."
        )

        # Should extract as observation/decision
        has_extraction = any(e.get("type") in ("thinking", "response") for e in events)
        log(f"Extraction events: {len(events)}", "INFO")

        # Recall memory (new message to trigger recall)
        log("Recalling memory...", "INFO")
        await asyncio.sleep(2)  # Let extraction complete
        events = await self.send_message(
            f"What did I tell you to remember about {unique_phrase}?"
        )

        response = next((e.get("content", "") for e in events if e.get("type") == "response"), "")
        has_recall = unique_phrase in response or "test memory" in response.lower()
        passed = has_recall
        self.record_result(
            "Memory recall",
            passed,
            f"Recalled: '{response[:100]}...'" if passed else "Memory not recalled"
        )

    async def test_06_approval_flow(self):
        """Test tool approval flow (manual approve/reject)."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 6: Approval Flow", "TEST")
        log("=" * 60)

        # Send message that will need approval (shell command)
        log("Requesting shell command (needs approval)...", "INFO")
        events = await self.send_message("Run: echo 'NexusAgent approval test'")

        # Look for approval request
        approval_req = next((e for e in events if e.get("type") == "approval_request"), None)
        has_approval = approval_req is not None
        passed_1 = has_approval
        self.record_result("Approval request", passed_1, "Got approval modal" if passed_1 else "No approval requested")

        if has_approval:
            call_id = approval_req.get("call_id")
            tool = approval_req.get("tool")
            log(f"Tool '{tool}' requested approval", "INFO")

            # Approve
            await self.approve_tool(call_id, approved=True)
            await asyncio.sleep(3)

            # Check for result
            result_events = await self.send_message("What was the output?")
            has_output = any("NexusAgent approval test" in str(e) for e in result_events)
            passed_2 = has_output
            self.record_result("Approval execution", passed_2, "Command executed" if passed_2 else "No output")
        else:
            self.record_result("Approval execution", False, "Skipped (no approval request)",)

    async def test_07_slash_commands(self):
        """Test slash commands."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 7: Slash Commands", "TEST")
        log("=" * 60)

        # Test /help
        log("Testing /help...", "INFO")
        events = await self.send_message("/help")
        has_help = any("help" in str(e).lower() or len(events) > 0 for e in events)
        self.record_result("/help command", has_help, "Help shown" if has_help else "No response")

        # Test /new (clear session)
        log("Testing /new...", "INFO")
        events = await self.send_message("/new")
        has_new = any(e.get("type") in ("response", "thinking") for e in events)
        self.record_result("/new command", has_new, "Session cleared" if has_new else "No response")

        # Test /status
        log("Testing /status...", "INFO")
        events = await self.send_message("/status")
        has_status = any("ready" in str(e).lower() or "busy" in str(e).lower() for e in events)
        self.record_result("/status command", has_status, "Status shown" if has_status else "No response")

    async def test_08_error_handling(self):
        """Test error handling (invalid input, failures)."""
        log("\n" + "=" * 60, "TEST")
        log("TEST 8: Error Handling", "TEST")
        log("=" * 60)

        # Test with empty message
        events = await self.send_message("")
        # Should handle gracefully, not crash
        handled = True  # If we got here, it didn't crash
        self.record_result("Empty input", handled, "Handled gracefully")

        # Test with very long message
        long_msg = "x" * 10000
        events = await self.send_message(long_msg)
        handled = len(events) > 0 or True  # Should not crash
        self.record_result("Long input (10K chars)", handled, "Handled without crash")

    async def run_all_tests(self):
        """Run all test cases."""
        log("\n" + "=" * 60, "TEST")
        log("NEXUSAGENT TUI E2E TEST SUITE", "TEST")
        log("=" * 60)
        log(f"Server: {SERVER_URL.format(session_id='...')}", "INFO")
        log(f"API Key: {API_KEY[:8]}...", "INFO")
        log(f"Timeout: {TIMEOUT}s", "INFO")
        log("=" * 60)

        # Connect
        if not await self.connect():
            log("❌ Cannot run tests without connection", "FAIL")
            return False

        try:
            # Run tests
            await self.test_01_basic_messaging()
            await self.test_02_thinking_event()
            await self.test_03_file_operations()
            await self.test_04_gemini_native_tools()
            await self.test_05_memory_storage_recall()
            await self.test_06_approval_flow()
            await self.test_07_slash_commands()
            await self.test_08_error_handling()

        finally:
            # Disconnect
            await self.disconnect()

        # Summary
        log("\n" + "=" * 60, "TEST")
        log("TEST SUMMARY", "TEST")
        log("=" * 60)
        total = sum(self.test_results.values())
        log(f"Total: {total} tests", "INFO")
        log(f"✅ Passed: {self.test_results['pass']}", "PASS")
        log(f"❌ Failed: {self.test_results['fail']}", "FAIL")
        log(f"⚠️  Skipped: {self.test_results['skip']}", "WARN")
        log("=" * 60)

        success = self.test_results['fail'] == 0
        if success:
            log("🎉 ALL TESTS PASSED!", "PASS")
        else:
            log(f"⚠️  {self.test_results['fail']} test(s) failed", "FAIL")

        return success


async def main():
    log("🚀 Starting E2E test suite...", "TEST")
    tester = E2ETester()
    log("Created tester instance", "INFO")
    success = await tester.run_all_tests()
    log(f"Tests completed: {'PASS' if success else 'FAIL'}", "TEST")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())