import requests
from datetime import datetime

def fetch_quote():
    try:
        r = requests.get("https://v1.hitokoto.cn/?encode=text", timeout=2)
        return r.text.strip()
    except Exception:
        return None

def fish_reminder(fish_times):
    now = datetime.now().strftime("%H:%M")
    if now in fish_times:
        return "摸鱼提醒：起来活动 3 分钟 🐟"
    return None

def alert_from_snapshot(snap):
    if not snap.online:
        return "⚠ 网络断开"
    if snap.weather.ok and snap.weather.stale:
        return "⚠ 天气数据过期"
    return None
