import pytest
from unittest.mock import MagicMock
from nexusagent.sdk import NexusSDK
from nexusagent.models import ResultSchema

@pytest.fixture
def mock_sdk():
    """Provides a mocked NexusSDK that allows simulating backend responses."""
    mock_sdk = MagicMock(spec=NexusSDK)
    return mock_sdk
