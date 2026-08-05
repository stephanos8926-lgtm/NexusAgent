# SPDX-License-Identifier: MIT

"""Tests for agent compatibility, specifically asynchronous execution of tools via ainvoke."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.core.agent import Agent, run_agent_task


@pytest.mark.asyncio
async def test_agent_ainvoke_called():
    """Verify that run_agent_task invokes the agent asynchronously using ainvoke."""
    mock_inner = MagicMock()
    mock_inner.ainvoke = AsyncMock(return_value="mock task result")

    # Patch create_deep_agent to return our mocked agent
    with patch("nexusagent.core.agent.create_deep_agent", return_value=mock_inner):
        # Patch _ensure_mcp_tools_loaded and _check_test_mode to avoid network/test blocks
        with patch("nexusagent.core.agent._ensure_mcp_tools_loaded"):
            with patch("nexusagent.core.agent._check_test_mode"):
                state = {"task": "do something async", "working_dir": "."}
                result = await run_agent_task(state)

                # Assert that the task succeeded and returned the mocked result
                assert result["success"] is True
                assert result["result"] == "mock task result"

                # Assert ainvoke was indeed called instead of synchronous invoke
                mock_inner.ainvoke.assert_called_once()
                mock_inner.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_agent_instance_ainvoke():
    """Verify that Agent instance exposes ainvoke."""
    mock_inner = MagicMock()
    mock_inner.ainvoke = AsyncMock(return_value="hello")

    with patch("nexusagent.core.agent.create_deep_agent", return_value=mock_inner):
        with patch("nexusagent.core.agent._ensure_mcp_tools_loaded"):
            with patch("nexusagent.core.agent._check_test_mode"):
                agent = await Agent.create(role="minimal")
                res = await agent.ainvoke({"messages": []})
                assert res == "hello"
                mock_inner.ainvoke.assert_called_once()
