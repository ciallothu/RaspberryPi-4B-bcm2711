# app/collectors/quotes.py
from __future__ import annotations
import requests

def fetch_quote(timeout_s: float = 2.0) -> str | None:
    """
    Use a simple public quote endpoint.
    If unavailable, return None.
    """
    try:
        r = requests.get("https://v1.hitokoto.cn/?encode=text", timeout=timeout_s)
        r.raise_for_status()
        t = r.text.strip()
        return t if t else None
    except Exception:
        return None
