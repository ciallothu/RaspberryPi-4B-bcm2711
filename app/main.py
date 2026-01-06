#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Desk Pet Panel (Raspberry Pi + 2inch SPI LCD 240x320)
- Driver: lcd2_tytion (LCD_2inch.py + lcdconfig.py)
- Features in this main.py:
  * Page cycle: clock/pet, weather(QWeather), status
  * QWeather via API KEY header X-QW-Api-Key (host is configurable)
  * Weather cache + stale indicator
  * Ticker scroll (quotes/reminders/alerts placeholder)
  * Network probe (simple connect test)
"""

import os
import json
import time
import signal
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from threading import Thread, Lock

import requests
from PIL import Image, ImageDraw, ImageFont

from drivers.LCD_2inch import LCD_2inch
from ticker_queue import TickerQueue, TickerItem
from collectors.quotes import fetch_quote
from ui.sprite import Sprite
from ui.weather_icons import ICON_MAP

from config_loader import load_config

CONFIG = load_config(os.path.join(os.path.dirname(__file__), "config.yaml"))

pet_normal = None
pet_alert = None
pet_normal = Sprite(...)
pet_alert = Sprite(...)


# -----------------------------
# Helpers
# -----------------------------

def ensure_state_dir() -> str:
    d = CONFIG["paths"]["state_dir"]
    os.makedirs(d, exist_ok=True)
    return d

def state_path(filename: str) -> str:
    return os.path.join(ensure_state_dir(), filename)

def run_cmd(args) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return ""

def get_ip_addr() -> str:
    out = run_cmd(["hostname", "-I"])
    if not out:
        return "-"
    return out.split()[0]

def get_cpu_temp_c() -> str:
    for p in ("/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            v = float(raw)
            if v > 1000:
                v /= 1000.0
            return f"{v:.0f}C"
        except Exception:
            pass
    return "-"

def get_load1() -> str:
    try:
        l1, _, _ = os.getloadavg()
        return f"{l1:.2f}"
    except Exception:
        return "-"

def net_ok(host: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except Exception:
        return False


# -----------------------------
# QWeather client (API KEY + API Host)
# -----------------------------

class QWeatherClient:
    """
    QWeather request composition:
    - URL: https://{api_host}{endpoint}?...
    - Auth (API KEY): header "X-QW-Api-Key: <key>"  :contentReference[oaicite:1]{index=1}
    - Geo City Lookup endpoint: /geo/v2/city/lookup :contentReference[oaicite:2]{index=2}
    - Real-time weather endpoint: /v7/weather/now     :contentReference[oaicite:3]{index=3}
    """
    def __init__(self, host: str, api_key: str, timeout_s: float):
        self.host = host.strip()
        self.api_key = api_key.strip()
        self.timeout_s = timeout_s

    def _headers(self) -> dict:
        return {"X-QW-Api-Key": self.api_key}

    def _get(self, path: str, params: dict) -> dict:
        if not self.host or "YOUR_HOST" in self.host:
            raise RuntimeError("QWeather host not configured (set qweather.host from Console API Host).")
        url = f"https://{self.host}{path}"
        r = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def city_lookup(self, location_text: str, lang: str, range_: str = "cn", number: int = 1) -> dict:
        params = {
            "location": location_text,
            "lang": lang,
            "range": range_,
            "number": number,
        }
        return self._get("/geo/v2/city/lookup", params)

    def weather_now(self, location_id: str, lang: str, unit: str) -> dict:
        params = {"location": location_id, "lang": lang, "unit": unit}
        return self._get("/v7/weather/now", params)


# -----------------------------
# Data model
# -----------------------------

@dataclass
class WeatherNow:
    ok: bool = False
    stale: bool = True
    location_name: str = "-"
    temp_c: str = "-"
    text: str = "-"
    icon: str = "-"
    obs_time: str = "-"
    update_time: str = "-"
    last_ok_ts: float = 0.0
    err: str = ""


@dataclass
class Snapshot:
    now: datetime
    ip: str
    cpu_temp: str
    load1: str
    online: bool
    weather: WeatherNow


# -----------------------------
# Global shared state
# -----------------------------

_lock = Lock()
_weather = WeatherNow()
_online = False
_ip = "-"
_stop = False


# -----------------------------
# Cache helpers
# -----------------------------

def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path: str, obj: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


# -----------------------------
# Background workers
# -----------------------------

def network_worker():
    global _online, _ip
    cfg = CONFIG["network"]
    while not _stop:
        ok = net_ok(cfg["connect_test_host"], cfg["connect_test_port"], cfg["connect_timeout"])
        ip = get_ip_addr()
        with _lock:
            _online = ok
            _ip = ip
        time.sleep(cfg["refresh_seconds"])


def weather_worker():
    global _weather
    qcfg = CONFIG["qweather"]
    client = QWeatherClient(qcfg["host"], qcfg["api_key"], qcfg["timeout_seconds"])

    geo_cache_p = state_path(CONFIG["paths"]["geo_cache"])
    weather_cache_p = state_path(CONFIG["paths"]["weather_cache"])

    geo_cache = load_json(geo_cache_p)
    weather_cache = load_json(weather_cache_p)

    # Initialize from cache if present
    if weather_cache:
        with _lock:
            _weather = WeatherNow(
                ok=True,
                stale=True,
                location_name=weather_cache.get("location_name", "-"),
                temp_c=weather_cache.get("temp_c", "-"),
                text=weather_cache.get("text", "-"),
                icon=weather_cache.get("icon", "-"),
                obs_time=weather_cache.get("obs_time", "-"),
                update_time=weather_cache.get("update_time", "-"),
                last_ok_ts=weather_cache.get("last_ok_ts", 0.0),
                err="(cache)"
            )

    backoff = 5
    while not _stop:
        try:
            # 1) get location_id (cache it)
            location_id = geo_cache.get("location_id")
            location_name = geo_cache.get("location_name", qcfg["lookup"]["location_text"])

            if not location_id:
                geo = client.city_lookup(
                    location_text=qcfg["lookup"]["location_text"],
                    lang=qcfg["lang"],
                    range_=qcfg["lookup"]["range"],
                    number=qcfg["lookup"]["number"],
                )
                if geo.get("code") != "200" or not geo.get("location"):
                    raise RuntimeError(f"Geo lookup failed: {geo.get('code')}")
                loc0 = geo["location"][0]
                location_id = loc0["id"]
                location_name = loc0.get("name", location_name)
                geo_cache = {"location_id": location_id, "location_name": location_name, "ts": time.time()}
                save_json(geo_cache_p, geo_cache)

            # 2) weather now
            wnow = client.weather_now(location_id=location_id, lang=qcfg["lang"], unit=qcfg["unit"])
            if wnow.get("code") != "200":
                raise RuntimeError(f"Weather now failed: {wnow.get('code')}")

            now_obj = wnow.get("now", {})
            upd_time = wnow.get("updateTime", "")

            new_w = WeatherNow(
                ok=True,
                stale=False,
                location_name=location_name,
                temp_c=str(now_obj.get("temp", "-")),
                text=str(now_obj.get("text", "-")),
                icon=str(now_obj.get("icon", "-")),
                obs_time=str(now_obj.get("obsTime", "-")),
                update_time=str(upd_time),
                last_ok_ts=time.time(),
                err=""
            )

            # persist cache
            save_json(weather_cache_p, {
                "location_id": location_id,
                "location_name": location_name,
                "temp_c": new_w.temp_c,
                "text": new_w.text,
                "icon": new_w.icon,
                "obs_time": new_w.obs_time,
                "update_time": new_w.update_time,
                "last_ok_ts": new_w.last_ok_ts,
            })

            with _lock:
                _weather = new_w

            backoff = 5
            time.sleep(qcfg["refresh_seconds"])

        except Exception as e:
            # mark stale but keep last data if any
            with _lock:
                cur = _weather
                _weather = WeatherNow(
                    ok=cur.ok,
                    stale=True,
                    location_name=cur.location_name,
                    temp_c=cur.temp_c,
                    text=cur.text,
                    icon=cur.icon,
                    obs_time=cur.obs_time,
                    update_time=cur.update_time,
                    last_ok_ts=cur.last_ok_ts,
                    err=str(e)[:60]
                )
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


# -----------------------------
# Rendering utilities
# -----------------------------

def load_font(size: int) -> ImageFont.ImageFont:
    # Prefer the font shipped in the driver zip (arialbd.ttf)
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "drivers", "fonts", "arialbd.ttf"),
        os.path.join(base, "ui", "assets", "fonts", "arialbd.ttf"),
        os.path.join(base, "fonts", "arialbd.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def draw_pet(draw: ImageDraw.ImageDraw, x: int, y: int, online: bool, alert: bool) -> None:
    w, h = 72, 72
    draw.rectangle([x, y, x + w, y + h], outline=(255, 255, 255), width=2)

    if alert:
        # angry / alert face
        draw.line([x+16, y+24, x+30, y+28], fill=(255, 255, 255), width=2)
        draw.line([x+44, y+28, x+58, y+24], fill=(255, 255, 255), width=2)
        draw.rectangle([x+20, y+30, x+26, y+36], fill=(255, 255, 255))
        draw.rectangle([x+46, y+30, x+52, y+36], fill=(255, 255, 255))
        draw.arc([x+20, y+44, x+52, y+66], start=200, end=340, fill=(255, 255, 255), width=2)
        return

    if online:
        draw.rectangle([x+18, y+24, x+26, y+32], fill=(255, 255, 255))
        draw.rectangle([x+46, y+24, x+54, y+32], fill=(255, 255, 255))
        draw.arc([x+18, y+34, x+54, y+62], start=10, end=170, fill=(255, 255, 255), width=2)
    else:
        draw.line([x+18, y+24, x+28, y+34], fill=(255, 255, 255), width=2)
        draw.line([x+28, y+24, x+18, y+34], fill=(255, 255, 255), width=2)
        draw.line([x+46, y+24, x+56, y+34], fill=(255, 255, 255), width=2)
        draw.line([x+56, y+24, x+46, y+34], fill=(255, 255, 255), width=2)
        draw.line([x+22, y+54, x+50, y+54], fill=(255, 255, 255), width=2)

def status_bar(draw: ImageDraw.ImageDraw, snap: Snapshot, font: ImageFont.ImageFont):
    w = CONFIG["display"]["w"]
    net = "OK" if snap.online else "OFF"
    wflag = "W" if (snap.weather.ok and not snap.weather.stale) else "w"
    s = f"NET:{net}  {wflag}  IP:{snap.ip}"
    draw.text((6, 4), s, font=font, fill=(255, 255, 255))
    # right side temp/load
    s2 = f"T:{snap.cpu_temp} L:{snap.load1}"
    tw = draw.textlength(s2, font=font)
    draw.text((w - tw - 6, 4), s2, font=font, fill=(255, 255, 255))

class Ticker:
    def __init__(self):
        self.offset = 0.0
        self.last_t = time.monotonic()
        self.text = "INIT"
        self._cached_width = None

    def set_text(self, text: str):
        if text != self.text:
            self.text = text
            self._cached_width = None
            self.offset = 0.0

    def step(self, speed_px_per_s: float):
        now = time.monotonic()
        dt = now - self.last_t
        self.last_t = now
        self.offset += speed_px_per_s * dt

    def draw(self, img: Image.Image, font: ImageFont.ImageFont):
        draw = ImageDraw.Draw(img)
        w, h = img.size
        th = CONFIG["ui"]["ticker_height"]
        y0 = h - th
        draw.rectangle([0, y0, w, h], fill=(0, 0, 0))

        # measure once
        if self._cached_width is None:
            self._cached_width = draw.textlength(self.text, font=font)

        gap = 30
        total = self._cached_width + gap
        if total <= 0:
            return

        # loop offset
        off = self.offset % total
        x = int(w - off)

        # draw repeated to cover whole line
        while x < w:
            draw.text((x, y0 + 6), self.text, font=font, fill=(255, 255, 255))
            x += int(total)

# app/main.py
def render_clock_page(
    snap: Snapshot,
    ticker: Ticker,
    pet_normal: "Sprite | None",
    pet_alert: "Sprite | None",
) -> Image.Image:
    w, h = CONFIG["display"]["w"], CONFIG["display"]["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)
    font_big = load_font(54)

    status_bar(draw, snap, font_small)

    # time
    t_str = snap.now.strftime("%H:%M")
    draw.text((10, 40), t_str, font=font_big, fill=(255, 255, 255))

    # date
    d_str = snap.now.strftime("%Y-%m-%d %a")
    draw.text((12, 110), d_str, font=font_mid, fill=(255, 255, 255))

    # quick weather hint
    if snap.weather.ok:
        wline = f"{snap.weather.location_name} {snap.weather.temp_c}° {snap.weather.text}"
        if snap.weather.stale:
            wline += " ~"
        draw.text((12, 148), wline[:22], font=font_mid, fill=(255, 255, 255))
    else:
        draw.text((12, 148), "Weather: -", font=font_mid, fill=(255, 255, 255))

    # ===== desk pet sprite =====
    alert_mode = (not snap.online) or (snap.weather.ok and snap.weather.stale)

    sprite = pet_alert if alert_mode else pet_normal
    if sprite is not None:
        frame = sprite.frame(time.time())
        if frame is not None:
            img.paste(frame, (w - 80, h - 110), frame)

    return img


def render_weather_page(snap: Snapshot, ticker: Ticker) -> Image.Image:
    w, h = CONFIG["display"]["w"], CONFIG["display"]["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)
    font_big = load_font(48)

    status_bar(draw, snap, font_small)
    icon_code = snap.weather.icon
    icon_name = ICON_MAP.get(icon_code, "unknown.png")
    icon_path = os.path.join(os.path.dirname(__file__), "ui", "assets", "icons", icon_name)

    try:
        icon = Image.open(icon_path).convert("RGBA")
        # Put icon on left area
        img.paste(icon, (10, 90), icon)
    except Exception:
        pass
    title = "WEATHER"
    draw.text((10, 36), title, font=font_mid, fill=(255, 255, 255))

    if snap.weather.ok:
        draw.text((10, 80), f"{snap.weather.location_name}", font=font_mid, fill=(255, 255, 255))
        draw.text((10, 130), f"{snap.weather.temp_c}°", font=font_big, fill=(255, 255, 255))
        draw.text((120, 146), f"{snap.weather.text}", font=font_mid, fill=(255, 255, 255))

        meta = f"obs:{snap.weather.obs_time[-14:]} upd:{snap.weather.update_time[-14:]}"
        if snap.weather.stale:
            meta = "STALE " + meta
        draw.text((10, 210), meta[:32], font=font_small, fill=(255, 255, 255))
        if snap.weather.err:
            draw.text((10, 230), f"err:{snap.weather.err}"[:32], font=font_small, fill=(255, 255, 255))
    else:
        draw.text((10, 120), "Weather unavailable", font=font_mid, fill=(255, 255, 255))
        if snap.weather.err:
            draw.text((10, 150), f"{snap.weather.err}"[:32], font=font_small, fill=(255, 255, 255))

    ticker.draw(img, font_small)
    return img

def render_status_page(snap: Snapshot, ticker: Ticker) -> Image.Image:
    w, h = CONFIG["display"]["w"], CONFIG["display"]["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)

    status_bar(draw, snap, font_small)

    draw.text((10, 36), "STATUS", font=font_mid, fill=(255, 255, 255))

    lines = [
        f"CPU temp: {snap.cpu_temp}",
        f"Load1:    {snap.load1}",
        f"IP:       {snap.ip}",
        f"Network:  {'ONLINE' if snap.online else 'OFFLINE'}",
    ]
    y = 80
    for ln in lines:
        draw.text((10, y), ln, font=font_mid, fill=(255, 255, 255))
        y += 34

    if snap.weather.ok:
        draw.text((10, y + 10), f"W: {snap.weather.temp_c}° {snap.weather.text}" + (" ~" if snap.weather.stale else ""),
                  font=font_mid, fill=(255, 255, 255))

    ticker.draw(img, font_small)
    return img


# -----------------------------
# Main loop
# -----------------------------

def _handle_signal(signum, frame):
    global _stop
    _stop = True

def build_snapshot() -> Snapshot:
    with _lock:
        online = _online
        ip = _ip
        w = _weather
    return Snapshot(
        now=datetime.now(),
        ip=ip,
        cpu_temp=get_cpu_temp_c(),
        load1=get_load1(),
        online=online,
        weather=w
    )

def main():
    global _stop
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    ensure_state_dir()

    # start background workers
    Thread(target=network_worker, daemon=True).start()
    Thread(target=weather_worker, daemon=True).start()

    lcd = LCD_2inch()
    lcd.Init()
    lcd.clear()
    lcd.bl_DutyCycle(CONFIG["display"]["brightness"])

    pages = ["clock", "weather", "status"]
    page_idx = 0
    page_start = time.monotonic()
    ticker_q = TickerQueue()

    BASE_DIR = os.path.dirname(__file__)
    pet_normal = Sprite(os.path.join(BASE_DIR, "ui", "assets", "sprites", "normal"), fps=CONFIG["display"]["fps_idle"])
    pet_alert  = Sprite(os.path.join(BASE_DIR, "ui", "assets", "sprites", "alert"),  fps=CONFIG["display"]["fps_idle"])

    last_quote_ts = 0.0
    ticker = Ticker()

    try:
        while not _stop:
            snap = build_snapshot()
            now_mono = time.monotonic()

            # 1) Quote: fetch at most once per 10 minutes
            if now_mono - last_quote_ts > 600:
                last_quote_ts = now_mono
                q = fetch_quote()
                if q:
                    ticker_q.push(TickerItem(q, ttl=600, priority=20))

            # 2) Alerts
            alert = None
            if not snap.online:
                alert = "⚠ 网络离线"
            elif snap.weather.ok and snap.weather.stale:
                alert = "⚠ 天气数据过期（stale）"

            if alert:
                ticker_q.push(TickerItem(alert, ttl=30, priority=1))

            # 3) Apply ticker text (fallback if empty)
            t = ticker_q.next_text()
            if not t:
                t = "TIP: 继续完善 sprites/icons，并接入日历与服务器状态。"
            ticker.set_text(t)
            # ticker content policy (simple but useful):
            if not snap.online:
                ticker.set_text("ALERT: network offline. check uplink/AP/DNS.")
            elif snap.weather.ok and snap.weather.stale:
                ticker.set_text("WARN: weather stale. check QWeather host/key or connectivity.")
            else:
                # default rotating line
                ticker.set_text("TIP: add sprites, calendar, server health, and fish reminders next.")

            ticker.step(CONFIG["ui"]["ticker_speed_px_per_s"])

            # auto page rotate
            if time.monotonic() - page_start >= CONFIG["display"]["page_cycle_seconds"]:
                page_start = time.monotonic()
                page_idx = (page_idx + 1) % len(pages)

            p = pages[page_idx]
            if p == "clock":
                frame = render_clock_page(snap, ticker)
                lcd.ShowImage(frame)
                time.sleep(1.0)  # static pace
            elif p == "weather":
                frame = render_weather_page(snap, ticker)
                lcd.ShowImage(frame)
                time.sleep(1.0)
            else:
                frame = render_status_page(snap, ticker)
                lcd.ShowImage(frame)
                time.sleep(1.0)

    finally:
        try:
            lcd.bl_DutyCycle(0)
        except Exception:
            pass
        try:
            lcd.module_exit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
