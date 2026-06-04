
def test_mock_sdk_fixture(mock_sdk):
    assert mock_sdk is not None
    # Verify it's a mock of NexusSDK
    assert hasattr(mock_sdk, 'submit_task')
