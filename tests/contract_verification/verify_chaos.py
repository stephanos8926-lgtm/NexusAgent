import unittest
import uuid
from dataclasses import dataclass


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
        if task is None:
            raise ValueError("None input")
        if not task.description:
            return TaskResponse(success=False, error="Empty description")
        if len(task.description) > 1000:
            return TaskResponse(success=False, error="Description too long")
        return TaskResponse(success=True, data="Chaos Success")


def ui_handle_submit(text, sdk):
    if text is None:
        raise ValueError("None input")
    if not text:
        return "Error: Task definition empty", "ERROR"
    task_id = str(uuid.uuid4())[:8]
    task = TaskSchema(id=task_id, description=text)
    result = sdk.submit_task(task)
    if result.success:
        return f"[{task_id}] {result.data}", "ACTIVE"
    else:
        return f"Critical Failure: {result.error}", "ERROR"


class TestChaosContract(unittest.TestCase):
    def setUp(self):
        self.sdk = MockSDK()

    def test_empty_string(self):
        res, stat = ui_handle_submit("", self.sdk)
        self.assertEqual(stat, "ERROR")
        self.assertIn("empty", res)
        print("✓ Empty String Handled")

    def test_extremely_long_string(self):
        long_text = "A" * 1001
        res, stat = ui_handle_submit(long_text, self.sdk)
        self.assertEqual(stat, "ERROR")
        self.assertIn("too long", res)
        print("✓ Overlong Input Handled")

    def test_none_input(self):
        with self.assertRaises(ValueError):
            ui_handle_submit(None, self.sdk)
        print("✓ None Input Handled (as expected exception)")


if __name__ == "__main__":
    unittest.main()
