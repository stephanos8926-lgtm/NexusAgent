from unittest.mock import MagicMock

import pytest

from nexusagent.sdk import NexusSDK


@pytest.fixture
def mock_sdk():
    """Provides a mocked NexusSDK that allows simulating backend responses."""
    mock_sdk = MagicMock(spec=NexusSDK)
    return mock_sdk
