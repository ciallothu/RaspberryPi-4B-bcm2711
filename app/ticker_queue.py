# app/ticker_queue.py
import time
from dataclasses import dataclass
from typing import Deque, Optional
from collections import deque

@dataclass
class TickerItem:
    text: str
    ttl: int = 60
    priority: int = 10
    created_ts: float = time.time()

    @property
    def expire_ts(self) -> float:
        return self.created_ts + self.ttl

class TickerQueue:
    """
    Priority: smaller number = higher priority.
    """
    def __init__(self, maxlen: int = 50):
        self.q: Deque[TickerItem] = deque(maxlen=maxlen)

    def push(self, item: TickerItem) -> None:
        self.q.append(item)
        # Keep stable ordering by (priority, created_ts)
        self.q = deque(sorted(self.q, key=lambda x: (x.priority, x.created_ts)), maxlen=self.q.maxlen)

    def _prune(self) -> None:
        now = time.time()
        self.q = deque([i for i in self.q if i.expire_ts > now], maxlen=self.q.maxlen)

    def next_text(self) -> str:
        self._prune()
        return self.q[0].text if self.q else ""
