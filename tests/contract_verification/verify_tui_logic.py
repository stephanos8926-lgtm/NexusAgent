import unittest
import uuid
from dataclasses import dataclass


# --- MOCK CONTRACTS (Same as in verify_logic.py for consistency) ---
@dataclass
class TaskSchema:
    id: str
    description: str


@dataclass
class TaskResponse:
    success: bool
    data: str | None = None
    error: str | None = None


class MockSDK:
    def submit_task(self, task):
        if "fail" in task.description.lower():
            return TaskResponse(success=False, error="Simulated TUI Failure")
        return TaskResponse(success=True, data="TUI Success")


# --- TUI LOGIC EXTRACTED ---
# We simulate the on_input_submitted logic from NexusApp
def tui_handle_input(value, sdk):
    task_id = str(uuid.uuid4())[:8]
    task = TaskSchema(id=task_id, description=value)
    result = sdk.submit_task(task)

    if result.success:
        return True, f"Task {task_id} submitted: {value}"
    else:
        return False, result.error


# --- TESTS ---
class TestTUIContract(unittest.TestCase):
    def setUp(self):
        self.sdk = MockSDK()

    def test_tui_success_handshake(self):
        success, msg = tui_handle_input("Do TUI task", self.sdk)
        self.assertTrue(success)
        self.assertIn("submitted", msg)
        print("✓ TUI Success Path Verified")

    def test_tui_error_handshake(self):
        success, msg = tui_handle_input("Please fail", self.sdk)
        self.assertFalse(success)
        self.assertEqual(msg, "Simulated TUI Failure")
        print("✓ TUI Error Path Verified")


if __name__ == "__main__":
    unittest.main()
