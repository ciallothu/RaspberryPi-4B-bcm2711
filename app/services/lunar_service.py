import time
from typing import Optional

from app.collectors.shwg import fetch_lunar
from app.models import LunarInfo


class LunarService:
    def __init__(self, api_key: str, refresh_seconds: float = 3600.0):
        self.api_key = api_key
        self.refresh_seconds = refresh_seconds
        self._last_fetch = 0.0
        self._lunar: Optional[LunarInfo] = None

    def tick(self) -> None:
        now = time.monotonic()
        if now - self._last_fetch <= self.refresh_seconds:
            return
        self._last_fetch = now
        lunar = fetch_lunar(self.api_key)
        if lunar:
            self._lunar = lunar

    def snapshot(self) -> Optional[LunarInfo]:
        return self._lunar
