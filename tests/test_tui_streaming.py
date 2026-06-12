"""Tests for the conversational TUI."""

from nexusagent.interfaces.tui import ApprovalModal, ErrorModal, NexusApp


class TestTuiCompose:
    """Verify the app can be instantiated and composed without errors."""

    def test_tui_compose(self):
        """Creating a NexusApp instance should not raise."""
        app = NexusApp()
        assert app is not None

    def test_error_modal_creation(self):
        """Creating an ErrorModal should not raise."""
        modal = ErrorModal("test error")
        assert modal.error_message == "test error"


class TestApprovalModal:
    """Verify the ApprovalModal works as expected."""

    def test_approval_modal_creation(self):
        """Creating an ApprovalModal should not raise."""
        modal = ApprovalModal("bash", {"cmd": "ls -la"})
        assert modal.tool_name == "bash"
        assert modal.tool_args == {"cmd": "ls -la"}
