import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.interfaces.tui import NexusApp
from nexusagent.interfaces.tui.input import on_chat_input_submitted
from nexusagent.widgets.messages import AppMessage


@pytest.mark.asyncio
async def test_input_length_limit():
    """Verify that inputs larger than 32KB are rejected."""
    app = NexusApp.__new__(NexusApp)
    app._busy = False
    app._pending_inputs = []
    app._pending_inputs_max = 100
    app._mount_with_limit = MagicMock()
    app.chat_input = MagicMock()

    # Create a message of 33,000 characters
    long_msg = "a" * 33000
    event = MagicMock()
    event.text = long_msg
    event.input = MagicMock()

    await on_chat_input_submitted(app, event)

    # _mount_with_limit should be called with an AppMessage indicating the error
    app._mount_with_limit.assert_called_once()
    arg = app._mount_with_limit.call_args[0][0]
    assert isinstance(arg, AppMessage)
    assert "too long" in arg._message.lower()


@pytest.mark.asyncio
async def test_queue_size_limit():
    """Verify that queueing is rejected when _pending_inputs_max is reached."""
    app = NexusApp.__new__(NexusApp)
    app._busy = True  # Must be busy to queue
    app._pending_inputs = ["message"] * 10
    app._pending_inputs_max = 10  # Set low max
    app._mount_with_limit = MagicMock()
    app.chat_input = MagicMock()

    event = MagicMock()
    event.text = "eleventh message"
    event.input = MagicMock()

    await on_chat_input_submitted(app, event)

    # It should be rejected as "Queue full"
    app._mount_with_limit.assert_called_once()
    arg = app._mount_with_limit.call_args[0][0]
    assert isinstance(arg, AppMessage)
    assert "queue full" in arg._message.lower()
