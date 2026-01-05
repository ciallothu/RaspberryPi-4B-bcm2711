import time
from collections import deque

class TickerItem:
    def __init__(self, text: str, ttl: int = 60, priority: int = 10):
        self.text = text
        self.expire = time.time() + ttl
        self.priority = priority

class TickerQueue:
    def __init__(self):
        self.q = deque()

    def push(self, item: TickerItem):
        self.q.append(item)
        self.q = deque(sorted(self.q, key=lambda x: x.priority))

    def next_text(self) -> str:
        now = time.time()
        self.q = deque([i for i in self.q if i.expire > now])
        if not self.q:
            return ""
        return self.q[0].text
