import unittest
from unittest.mock import MagicMock

from nexusagent.models import ResultSchema as TaskResponse
from nexusagent.web_ui import handle_submit


class TestWebUIContract(unittest.TestCase):
    def setUp(self):
        self.mock_sdk = MagicMock()

    def test_success_handshake(self):
        # Mock a successful SDK response
        self.mock_sdk.submit_task.return_value = TaskResponse(
            success=True, data="Task completed successfully", error=None
        )
        
        result, status = handle_submit("Test task", sdk=self.mock_sdk)
        
        self.assertEqual(status, "ACTIVE")
        self.assertIn("Task completed successfully", result)

    def test_error_handshake(self):
        # Mock a failed SDK response
        self.mock_sdk.submit_task.return_value = TaskResponse(
            success=False, data=None, error="Internal Server Error"
        )
        
        result, status = handle_submit("Test task", sdk=self.mock_sdk)
        
        self.assertEqual(status, "ERROR")
        self.assertIn("Critical Failure: Internal Server Error", result)

    def test_empty_input(self):
        result, status = handle_submit("", sdk=self.mock_sdk)
        self.assertEqual(status, "ERROR")
        self.assertIn("Error: Task definition empty", result)

if __name__ == "__main__":
    unittest.main()
