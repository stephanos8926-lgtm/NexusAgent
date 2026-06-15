# tests/test_nats_durable.py
"""
Unit tests for JetStream durable consumer support in AgentBus.subscribe_durable().

These tests verify the method signature, parameter defaults, error paths,
and mock-based stream/consumer setup without requiring a live NATS server.
"""

import asyncio
import inspect
from unittest.mock import AsyncMock

import pytest

from nexusagent.infrastructure.bus import AgentBus


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_msg(data: bytes = b'{"hello":"world"}') -> AsyncMock:
    """Return a mock NATS message that supports awaitable ack/nack."""
    msg = AsyncMock()
    msg.data = data
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()
    return msg


def _make_mock_js() -> tuple[AgentBus, AsyncMock]:
    """Create an AgentBus whose .nc and .js are mocked."""
    bus = AgentBus.__new__(AgentBus)
    bus.url = "nats://mock:4222"
    bus.nc = AsyncMock()
    bus.js = AsyncMock()
    bus.kv = None
    bus._subscriptions = []
    return bus, bus.js


# ─── Signature & existence tests ───────────────────────────────────────────────


class TestSubscribeDurableSignature:
    def test_method_exists(self) -> None:
        assert hasattr(AgentBus, "subscribe_durable")

    def test_is_async(self) -> None:
        assert inspect.iscoroutinefunction(AgentBus.subscribe_durable)

    def test_default_parameters(self) -> None:
        sig = inspect.signature(AgentBus.subscribe_durable)
        params = sig.parameters
        assert params["stream"].default == "nexus_tasks"
        assert params["durable"].default == "nexus_worker"
        assert params["batch_size"].default == 10
        assert params["batch_timeout"].default == 5.0

    def test_subject_and_callback_are_positional(self) -> None:
        sig = inspect.signature(AgentBus.subscribe_durable)
        params = sig.parameters
        # subject and callback must be positional (no default)
        assert params["subject"].default is inspect.Parameter.empty
        assert params["callback"].default is inspect.Parameter.empty

    def test_stream_durable_batch_are_keyword_only(self) -> None:
        sig = inspect.signature(AgentBus.subscribe_durable)
        params = sig.parameters
        # Must be keyword-only (follow *)
        assert params["stream"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["durable"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["batch_size"].kind == inspect.Parameter.KEYWORD_ONLY


# ─── Precondition test ──────────────────────────────────────────────────────────


class TestSubscribeDurablePreconditions:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self) -> None:
        bus = AgentBus.__new__(AgentBus)
        bus.nc = None
        bus.js = None
        with pytest.raises(RuntimeError, match="not connected"):
            await bus.subscribe_durable("nexus.task.>", AsyncMock())


# ─── Stream & consumer setup tests ─────────────────────────────────────────────


class TestSubscribeDurableSetup:
    @pytest.mark.asyncio
    async def test_creates_stream_and_consumer(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()
        psub = AsyncMock()
        psub.fetch = AsyncMock(side_effect=[[], asyncio.CancelledError()])
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock()
        await bus.subscribe_durable("nexus.task.>", callback)

        js.add_stream.assert_awaited_once_with(
            name="nexus_tasks",
            subjects=["nexus.task.>"],
        )
        js.add_consumer.assert_awaited_once()
        js.pull_subscribe.assert_awaited_once_with(
            "nexus.task.>", durable="nexus_worker", stream="nexus_tasks"
        )

    @pytest.mark.asyncio
    async def test_stream_already_exists(self) -> None:
        bus, js = _make_mock_js()
        import nats.errors

        err = nats.errors.Error("stream name already in use")
        js.add_stream = AsyncMock(side_effect=err)
        js.add_consumer = AsyncMock()
        psub = AsyncMock()
        psub.fetch = AsyncMock(side_effect=[[], asyncio.CancelledError()])
        js.pull_subscribe = AsyncMock(return_value=psub)

        # Must not raise
        callback = AsyncMock()
        await bus.subscribe_durable("nexus.task.>", callback)

    @pytest.mark.asyncio
    async def test_consumer_already_exists(self) -> None:
        bus, js = _make_mock_js()
        import nats.errors

        err = nats.errors.Error("consumer already exists")
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock(side_effect=err)
        psub = AsyncMock()
        psub.fetch = AsyncMock(side_effect=[[], asyncio.CancelledError()])
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock()
        await bus.subscribe_durable("nexus.task.>", callback)

    @pytest.mark.asyncio
    async def test_custom_stream_and_durable(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()
        psub = AsyncMock()
        psub.fetch = AsyncMock(side_effect=[[], asyncio.CancelledError()])
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock()
        await bus.subscribe_durable(
            "custom.>",
            callback,
            stream="custom_stream",
            durable="custom_worker",
            batch_size=5,
            batch_timeout=2.0,
        )

        js.add_stream.assert_awaited_once_with(
            name="custom_stream",
            subjects=["custom.>"],
        )
        js.add_consumer.assert_awaited_once()
        js.pull_subscribe.assert_awaited_once_with(
            "custom.>", durable="custom_worker", stream="custom_stream"
        )


# ─── Batch fetch & ack/nack tests ──────────────────────────────────────────────


class TestSubscribeDurableBatchProcessing:
    @pytest.mark.asyncio
    async def test_processes_batch_then_acks(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()

        psub = AsyncMock()
        msg1 = _make_mock_msg()
        msg2 = _make_mock_msg()

        # CancelledError ends the loop cleanly after one batch
        psub.fetch = AsyncMock(
            side_effect=[[msg1, msg2], asyncio.CancelledError()],
        )
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock()
        # Call with a custom batch_timeout so fetch returns quickly
        await bus.subscribe_durable("nexus.task.>", callback, batch_timeout=0.01)
        # Yield to let the background task process the batch
        await asyncio.sleep(0.2)

        assert callback.await_count == 2
        msg1.ack.assert_awaited_once()
        msg2.ack.assert_awaited_once()
        msg1.nack.assert_not_awaited()
        msg2.nack.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nacks_on_callback_exception(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()

        psub = AsyncMock()
        msg_fail = _make_mock_msg()
        msg_ok = _make_mock_msg()

        _call_count = 0

        async def _raises_on_first(_msg: object) -> None:
            nonlocal _call_count
            _call_count += 1
            if _call_count == 1:
                raise RuntimeError("boom")

        psub.fetch = AsyncMock(
            side_effect=[[msg_fail, msg_ok], asyncio.CancelledError()],
        )
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock(side_effect=_raises_on_first)
        await bus.subscribe_durable("nexus.task.>", callback, batch_timeout=0.01)
        # Yield to let the background task process the batch
        await asyncio.sleep(0.2)

        msg_fail.nack.assert_awaited_once()
        msg_fail.ack.assert_not_awaited()
        # msg_ok should have been acked (second call succeeds)
        msg_ok.ack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_batch_no_callback(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()

        psub = AsyncMock()
        psub.fetch = AsyncMock(
            side_effect=[[], asyncio.CancelledError()],
        )
        js.pull_subscribe = AsyncMock(return_value=psub)

        callback = AsyncMock()
        await bus.subscribe_durable("nexus.task.>", callback, batch_timeout=0.01)
        await asyncio.sleep(0.1)

        # No messages → callback never called
        callback.assert_not_awaited()


# ─── Subscription tracking tests ───────────────────────────────────────────────


class TestSubscribeDurableTracking:
    @pytest.mark.asyncio
    async def test_tracks_psub_in_subscriptions(self) -> None:
        bus, js = _make_mock_js()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()
        psub = AsyncMock()
        psub.fetch = AsyncMock(side_effect=[[], asyncio.CancelledError()])
        js.pull_subscribe = AsyncMock(return_value=psub)

        await bus.subscribe_durable("nexus.task.>", AsyncMock())

        # psub should be in _subscriptions
        assert psub in bus._subscriptions


# ─── Existing subscribe() preserved ────────────────────────────────────────────


class TestExistingSubscribePreserved:
    def test_subscribe_still_exists(self) -> None:
        assert hasattr(AgentBus, "subscribe")
        assert inspect.iscoroutinefunction(AgentBus.subscribe)
