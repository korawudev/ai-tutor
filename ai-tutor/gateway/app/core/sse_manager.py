"""SSE 流管理器"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Set, Optional, Any
from uuid import UUID

from sse_starlette.sse import EventSourceResponse


class SSEManager:
    """
    SSE 连接管理器
    
    管理所有 Thread 的 SSE 连接，支持:
    - 按 Thread 订阅
    - 广播事件到 Thread
    - 连接生命周期管理
    """
    
    def __init__(self):
        # thread_id -> set of queues
        self._connections: Dict[UUID, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, thread_id: UUID) -> asyncio.Queue:
        """
        连接到 Thread 的 SSE 流
        
        Args:
            thread_id: Thread ID
        
        Returns:
            用于接收事件的 Queue
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        async with self._lock:
            if thread_id not in self._connections:
                self._connections[thread_id] = set()
            self._connections[thread_id].add(queue)
        
        return queue
    
    async def disconnect(self, thread_id: UUID, queue: asyncio.Queue):
        """
        断开 SSE 连接
        
        Args:
            thread_id: Thread ID
            queue: 连接的 Queue
        """
        async with self._lock:
            if thread_id in self._connections:
                self._connections[thread_id].discard(queue)
                if not self._connections[thread_id]:
                    del self._connections[thread_id]
    
    async def emit(self, thread_id: UUID, event: str, data: dict, run_id: Optional[UUID] = None):
        """
        发送事件到 Thread 的所有连接
        
        Args:
            thread_id: Thread ID
            event: 事件类型
            data: 事件数据
            run_id: Run ID (可选)
        """
        message = {
            "event": event,
            "data": json.dumps(data, default=str),
            "run_id": str(run_id) if run_id else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with self._lock:
            if thread_id in self._connections:
                for queue in self._connections[thread_id]:
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        # 队列满了，丢弃旧消息
                        try:
                            queue.get_nowait()
                            queue.put_nowait(message)
                        except asyncio.QueueEmpty:
                            pass
    
    async def event_generator(self, thread_id: UUID):
        """
        SSE 事件生成器
        
        Args:
            thread_id: Thread ID
        
        Yields:
            SSE 事件
        """
        queue = await self.connect(thread_id)
        
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # 格式化为 SSE
                    event = message.get("event", "message")
                    data = message.get("data", "{}")
                    
                    yield {
                        "event": event,
                        "data": data,
                        "id": message.get("run_id"),
                        "retry": 5000
                    }
                    
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})
                    }
        finally:
            await self.disconnect(thread_id, queue)


# 全局实例
sse_manager = SSEManager()
