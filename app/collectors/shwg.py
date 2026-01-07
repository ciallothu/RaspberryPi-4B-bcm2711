from __future__ import annotations

from typing import Optional

import requests

from app.models import LunarInfo


def fetch_quote(key: str, quote_type: int = 5, timeout_s: float = 2.0) -> str | None:
    if not key:
        return None
    try:
        url = "https://api.shwgij.com/api/randtext/get"
        params = {"key": key, "type": str(quote_type), "m": ""}
        r = requests.get(url, params=params, timeout=timeout_s)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 200:
            return None
        payload = data.get("data", {})
        text = str(payload.get("text", "")).strip()
        cn = str(payload.get("cn", "")).strip()
        if text and cn:
            return f"{text} {cn}".strip()
        return text or cn or None
    except Exception:
        return None


def fetch_lunar(key: str, timeout_s: float = 2.0) -> Optional[LunarInfo]:
    if not key:
        return None
    try:
        url = "https://api.shwgij.com/api/lunars/lunarpro"
        params = {"key": key}
        r = requests.get(url, params=params, timeout=timeout_s)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 200:
            return None
        payload = data.get("data", {})
        return LunarInfo(
            solar=str(payload.get("Solar", "-")),
            lunar=str(payload.get("Lunar", "-")),
            week=str(payload.get("Week", "-")),
            ganzhi_year=str(payload.get("GanZhiYear", "-")),
            ganzhi_month=str(payload.get("GanZhiMonth", "-")),
            ganzhi_day=str(payload.get("GanZhiDay", "-")),
            constellation=str(payload.get("Constellation", "-")),
            yi=str(payload.get("YiDay", "-")),
            ji=str(payload.get("JiDay", "-")),
        )
    except Exception:
        return None
