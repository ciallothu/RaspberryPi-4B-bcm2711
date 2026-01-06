#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Desk Pet Panel (Raspberry Pi + 2inch SPI LCD 240x320)
- Driver: lcd2_tytion (LCD_2inch.py + lcdconfig.py)
- Page cycle: clock/pet, weather(QWeather), status
- Weather fetch via QWeather API
- Ticker scroll (quotes/reminders/alerts placeholder)
- Network probe (simple connect test)
"""

import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread

# Ensure the project root is on sys.path when running as a script (e.g. `python app/main.py`).
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from drivers.LCD_2inch import LCD_2inch
from ticker_queue import TickerItem, TickerQueue

from config_loader import load_config
from app.models import Snapshot
from app.services.quote_service import QuoteService
from app.services.weather_service import WeatherService
from app.ui.pages import render_clock_page, render_status_page, render_weather_page
from app.ui.pet_display import PetRenderer, load_pet_sprites
from app.ui.ticker_display import Ticker

CONFIG = load_config(os.path.join(os.path.dirname(__file__), "config.yaml"))

# -----------------------------
# Helpers
# -----------------------------

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
# Global shared state
# -----------------------------

_lock = Lock()
_online = False
_ip = "-"
_stop = False


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


def build_snapshot(weather_service: WeatherService) -> Snapshot:
    with _lock:
        online = _online
        ip = _ip
    return Snapshot(
        now=datetime.now(),
        ip=ip,
        cpu_temp=get_cpu_temp_c(),
        load1=get_load1(),
        online=online,
        weather=weather_service.snapshot(),
    )


# -----------------------------
# Main loop
# -----------------------------

def _handle_signal(signum, frame):
    global _stop
    _stop = True


def main():
    global _stop
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # start background workers
    weather_service = WeatherService(CONFIG)
    weather_service.start()
    Thread(target=network_worker, daemon=True).start()

    lcd = LCD_2inch()
    lcd.Init()
    lcd.clear()
    lcd.bl_DutyCycle(CONFIG["display"]["brightness"])

    pages = ["clock", "weather", "status"]
    page_idx = 0
    page_start = time.monotonic()
    ticker_q = TickerQueue()

    ticker = Ticker(height=CONFIG["ui"]["ticker_height"])
    quote_service = QuoteService(refresh_seconds=600, priority=20)

    base_dir = os.path.join(os.path.dirname(__file__), "ui", "assets", "sprites")
    pet_sprites = load_pet_sprites(base_dir, fps=CONFIG["display"]["fps_idle"])
    pet_renderer = PetRenderer(pet_sprites)

    try:
        while not _stop:
            snap = build_snapshot(weather_service)
            # 1) Quote: fetch periodically
            quote_service.tick(ticker_q)

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

            if not snap.online:
                t = "ALERT: network offline. check uplink/AP/DNS."
            elif snap.weather.ok and snap.weather.stale:
                t = "WARN: weather stale. check QWeather host/key or connectivity."

            ticker.set_text(t)
            ticker.step(CONFIG["ui"]["ticker_speed_px_per_s"])

            # auto page rotate
            if time.monotonic() - page_start >= CONFIG["display"]["page_cycle_seconds"]:
                page_start = time.monotonic()
                page_idx = (page_idx + 1) % len(pages)

            p = pages[page_idx]
            frame_renderers = {
                "clock": lambda: render_clock_page(snap, ticker, pet_renderer, CONFIG["display"]),
                "weather": lambda: render_weather_page(snap, ticker, CONFIG["display"]),
                "status": lambda: render_status_page(snap, ticker, CONFIG["display"]),
            }
            frame = frame_renderers[p]()
            lcd.ShowImage(frame)
            time.sleep(1.0)

    finally:
        _stop = True
        try:
            lcd.bl_DutyCycle(0)
        except Exception:
            pass
        try:
            lcd.module_exit()
        except Exception:
            pass
        weather_service.stop()


if __name__ == "__main__":
    main()
