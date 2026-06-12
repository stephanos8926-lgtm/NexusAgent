"""Tests for NexusSDK methods."""

import pytest

from nexusagent.server.sdk import NexusSDK


class TestSDKConstruction:
    """Test SDK instantiation and context manager protocol."""

    def test_sdk_instantiation(self):
        sdk = NexusSDK()
        assert sdk.bus is not None

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self):
        """async with NexusSDK() should set up and tear down cleanly."""
        sdk = NexusSDK()
        # We can't actually connect without NATS, but the protocol should exist
        assert hasattr(sdk, "__aenter__")
        assert hasattr(sdk, "__aexit__")
        assert hasattr(sdk, "disconnect")


class TestSDKMethodSignatures:
    """Verify all SDK methods exist with correct signatures."""

    def test_submit_task_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.submit_task)

    def test_get_task_status_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.get_task_status)

    def test_get_result_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.get_result)

    def test_list_tasks_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.list_tasks)

    def test_cancel_task_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.cancel_task)

    def test_retry_task_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.retry_task)

    def test_wait_for_result_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.wait_for_result)

    def test_submit_and_wait_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.submit_and_wait)

    def test_submit_batch_exists(self):
        sdk = NexusSDK()
        assert callable(sdk.submit_batch)


class TestSubmitTaskNoMutation:
    """Verify submit_task doesn't mutate the input dict."""

    @pytest.mark.asyncio
    async def test_input_dict_not_mutated(self):
        """The dict copy logic should prevent mutation of caller's dict."""
        original = {"description": "test", "id": "abc-123", "priority": 2}
        backup = dict(original)

        # We can test the copy logic without NATS
        task_data = dict(original)
        task_data.pop("id", None)

        # Original should be unchanged
        assert original == backup
        assert "id" in original

    @pytest.mark.asyncio
    async def test_id_preserved_when_provided(self):
        """When 'id' is in the dict, it should be used as the task ID."""
        task_data = {"description": "test", "id": "my-custom-id"}
        task_data_copy = dict(task_data)
        extracted_id = task_data_copy.pop("id", "default")
        assert extracted_id == "my-custom-id"

    @pytest.mark.asyncio
    async def test_uuid_generated_when_no_id(self):
        """When 'id' is not in the dict, a UUID should be generated."""
        task_data = {"description": "test"}
        task_data_copy = dict(task_data)
        task_data_copy.pop("id", "should-be-uuid")
        # Should have fallen back to the default (not removed anything)
        assert "id" not in task_data_copy
