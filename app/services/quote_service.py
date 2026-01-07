import time

from ticker_queue import TickerItem, TickerQueue
from app.collectors.shwg import fetch_quote


class QuoteService:
    def __init__(self, api_key: str, quote_type: int = 5, refresh_seconds: float = 600.0, priority: int = 20):
        self.api_key = api_key
        self.quote_type = quote_type
        self.refresh_seconds = refresh_seconds
        self.priority = priority
        self._last_fetch = 0.0

    def tick(self, queue: TickerQueue) -> None:
        now = time.monotonic()
        if now - self._last_fetch <= self.refresh_seconds:
            return
        self._last_fetch = now
        quote = fetch_quote(self.api_key, quote_type=self.quote_type)
        if quote:
            queue.push(TickerItem(quote, ttl=self.refresh_seconds, priority=self.priority))
