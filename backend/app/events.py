import asyncio
from typing import Any


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[tuple[int, asyncio.Queue]] = []

    def subscribe(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append((user_id, queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers = [(uid, q) for uid, q in self._subscribers if q is not queue]

    def publish(self, event_type: str, payload: dict[str, Any], user_id: int) -> None:
        event = {"type": event_type, "payload": payload}
        for uid, queue in list(self._subscribers):
            if uid == user_id:
                queue.put_nowait(event)


broadcaster = EventBroadcaster()
