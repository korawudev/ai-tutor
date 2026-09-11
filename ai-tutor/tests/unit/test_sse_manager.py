"""Unit tests for SSE manager."""

import asyncio
from uuid import uuid4

import pytest

from gateway.app.core.sse_manager import SSEManager


@pytest.fixture
def sse():
    return SSEManager()


class TestSSEManager:
    @pytest.mark.asyncio
    async def test_connect_returns_queue(self, sse):
        thread_id = uuid4()
        queue = await sse.connect(thread_id)
        assert isinstance(queue, asyncio.Queue)
        await sse.disconnect(thread_id, queue)

    @pytest.mark.asyncio
    async def test_disconnect_removes_queue(self, sse):
        thread_id = uuid4()
        queue = await sse.connect(thread_id)
        assert thread_id in sse._connections
        await sse.disconnect(thread_id, queue)
        assert thread_id not in sse._connections

    @pytest.mark.asyncio
    async def test_emit_delivers_message(self, sse):
        thread_id = uuid4()
        queue = await sse.connect(thread_id)

        await sse.emit(thread_id, "test_event", {"key": "value"})

        message = queue.get_nowait()
        assert message["event"] == "test_event"
        assert "key" in message["data"]
        await sse.disconnect(thread_id, queue)

    @pytest.mark.asyncio
    async def test_emit_with_run_id(self, sse):
        thread_id = uuid4()
        run_id = uuid4()
        queue = await sse.connect(thread_id)

        await sse.emit(thread_id, "test_event", {"key": "value"}, run_id=run_id)

        message = queue.get_nowait()
        assert message["run_id"] == str(run_id)
        await sse.disconnect(thread_id, queue)

    @pytest.mark.asyncio
    async def test_emit_no_connections(self, sse):
        thread_id = uuid4()
        await sse.emit(thread_id, "test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, sse):
        thread_id = uuid4()
        queue = asyncio.Queue()
        await sse.disconnect(thread_id, queue)

    @pytest.mark.asyncio
    async def test_event_generator_yields_message(self, sse):
        thread_id = uuid4()

        async def emit_later():
            await asyncio.sleep(0.05)
            await sse.emit(thread_id, "msg", {"data": "test"})

        asyncio.create_task(emit_later())

        events = []
        async for event in sse.event_generator(thread_id):
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) >= 1
        assert events[0]["event"] == "msg"
