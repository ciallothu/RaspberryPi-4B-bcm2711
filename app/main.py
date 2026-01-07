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

import argparse
import importlib.metadata
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
import psutil

from app.models import LunarInfo, Snapshot, WeatherNow, WeatherSnapshot
from app.services.quote_service import QuoteService
from app.services.weather_service import WeatherService
from app.services.lunar_service import LunarService
from app.ui.pages import (
    render_clock_page,
    render_dashboard_page,
    render_lunar_page,
    render_quote_page,
    render_status_page,
    render_video_page,
    render_weather_page,
    render_weekly_weather_page,
)
from app.ui.ticker_display import Ticker
from app.ui.video.player import VideoPlayer

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


def get_gpu_temp_c() -> str:
    out = run_cmd(["/usr/bin/vcgencmd", "measure_temp"])
    if not out:
        return "-"
    try:
        return out.split("=")[1].replace("'C", "C")
    except Exception:
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


def build_snapshot(weather_service: WeatherService, lunar_service: LunarService) -> Snapshot:
    with _lock:
        online = _online
        ip = _ip
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return Snapshot(
        now=datetime.now(),
        ip=ip,
        cpu_temp=get_cpu_temp_c(),
        gpu_temp=get_gpu_temp_c(),
        load1=get_load1(),
        cpu_percent=psutil.cpu_percent(interval=None),
        mem_percent=mem.percent,
        disk_percent=disk.percent,
        online=online,
        weather=weather_service.snapshot(),
        lunar=lunar_service.snapshot(),
    )


# -----------------------------
# Main loop
# -----------------------------

def _handle_signal(signum, frame):
    global _stop
    _stop = True


def _app_version() -> str:
    try:
        return importlib.metadata.version("bcm2711-deskpet-panel")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desk Pet Panel")
    parser.add_argument("-help", action="help", help="show this help message and exit")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "-vivian", dest="video_only", action="store_true", help="vivian video")
    group.add_argument("-w", dest="weather_only", action="store_true", help="weather only")
    group.add_argument("-q", dest="quotes_only", action="store_true", help="quotes only")
    group.add_argument("-clock", dest="clock_only", action="store_true", help="flip clock")
    group.add_argument("-d", "-dashboard", dest="dashboard_only", action="store_true", help="dashboard")
    group.add_argument("-l", "-luner", dest="lunar_only", action="store_true", help="lunar calendar")
    return parser.parse_args()


def _video_only_loop(lcd: LCD_2inch, video_player: VideoPlayer) -> None:
    dummy_snap = Snapshot(
        now=datetime.now(),
        ip="-",
        cpu_temp="-",
        gpu_temp="-",
        load1="-",
        cpu_percent=0.0,
        mem_percent=0.0,
        disk_percent=0.0,
        online=False,
        weather=WeatherSnapshot(now=WeatherNow(), daily=[]),
        lunar=None,
    )
    ticker = Ticker(height=CONFIG["ui"]["ticker_height"])
    while not _stop:
        frame = render_video_page(dummy_snap, ticker, video_player, CONFIG["display"])
        lcd.ShowImage(frame)
        time.sleep(video_player.frame_interval)


def main():
    global _stop
    args = _parse_args()
    if not any((args.video_only, args.weather_only, args.quotes_only, args.clock_only, args.dashboard_only, args.lunar_only)):
        version = _app_version()
        print(f"Desk Pet Panel {version}")
        print("Options:")
        print("  -h, -help  help")
        print("  -v, -vivian  vivian")
        print("  -w  weather")
        print("  -q  quotes")
        print("  -clock  flip clock")
        print("  -d, -dashboard  dashboard")
        print("  -l, -luner  lunar")
        return
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    lcd = LCD_2inch()
    lcd.Init()
    lcd.clear()
    lcd.bl_DutyCycle(CONFIG["display"]["brightness"])

    pages = ["dashboard", "clock", "weather", "weekly", "quotes", "lunar"]
    page_idx = 0
    page_start = time.monotonic()
    ticker_q = TickerQueue()

    video_dir = os.path.join(os.path.dirname(__file__), "ui", "pictures")
    video_player = VideoPlayer(
        video_dir,
        size=(CONFIG["display"]["w"], CONFIG["display"]["h"]),
        fps=CONFIG["display"].get("fps_video", 10),
    )
    if args.video_only:
        if not video_player.available:
            print("No video frames found under app/ui/pictures.")
            return
        try:
            _video_only_loop(lcd, video_player)
        finally:
            try:
                lcd.bl_DutyCycle(0)
            except Exception:
                pass
            try:
                lcd.module_exit()
            except Exception:
                pass
        return
    elif args.weather_only:
        pages = ["weekly"]
    elif args.quotes_only:
        pages = ["quotes"]
    elif args.clock_only:
        pages = ["clock"]
    elif args.dashboard_only:
        pages = ["dashboard"]
    elif args.lunar_only:
        pages = ["lunar"]
    elif video_player.available:
        pages.insert(0, "video")

    # start background workers
    weather_service = WeatherService(CONFIG)
    weather_service.start()
    Thread(target=network_worker, daemon=True).start()

    ticker = Ticker(height=CONFIG["ui"]["ticker_height"])
    shwg_cfg = CONFIG.get("shwg", {})
    quote_service = QuoteService(
        api_key=shwg_cfg.get("api_key", ""),
        quote_type=shwg_cfg.get("quote_type", 5),
        refresh_seconds=shwg_cfg.get("quote_refresh_seconds", 900),
        priority=20,
    )
    lunar_service = LunarService(
        api_key=shwg_cfg.get("api_key", ""),
        refresh_seconds=shwg_cfg.get("lunar_refresh_seconds", 3600),
    )

    try:
        while not _stop:
            lunar_service.tick()
            snap = build_snapshot(weather_service, lunar_service)
            # 1) Quote: fetch periodically
            quote_service.tick(ticker_q)

            # 2) Alerts
            alert = None
            if not snap.online:
                alert = "⚠ 网络离线"
            elif snap.weather.now.ok and snap.weather.now.stale:
                alert = "⚠ 天气数据过期（stale）"

            if alert:
                ticker_q.push(TickerItem(alert, ttl=30, priority=1))

            # 3) Apply ticker text (fallback if empty)
            t = ticker_q.next_text()
            if not t:
                t = "TIP: 继续完善 sprites/icons，并接入日历与服务器状态。"

            if not snap.online:
                t = "ALERT: network offline. check uplink/AP/DNS."
            elif snap.weather.now.ok and snap.weather.now.stale:
                t = "WARN: weather stale. check QWeather host/key or connectivity."

            ticker.set_text(t)
            ticker.step(CONFIG["ui"]["ticker_speed_px_per_s"])

            # auto page rotate
            if time.monotonic() - page_start >= CONFIG["display"]["page_cycle_seconds"]:
                page_start = time.monotonic()
                page_idx = (page_idx + 1) % len(pages)

            p = pages[page_idx]
            frame_renderers = {
                "dashboard": lambda: render_dashboard_page(snap, ticker, CONFIG["display"]),
                "clock": lambda: render_clock_page(snap, ticker, CONFIG["display"]),
                "quotes": lambda: render_quote_page(snap, ticker, CONFIG["display"]),
                "weather": lambda: render_weather_page(snap, ticker, CONFIG["display"]),
                "weekly": lambda: render_weekly_weather_page(snap, ticker, CONFIG["display"]),
                "status": lambda: render_status_page(snap, ticker, CONFIG["display"]),
                "video": lambda: render_video_page(snap, ticker, video_player, CONFIG["display"]),
                "lunar": lambda: render_lunar_page(snap, ticker, CONFIG["display"]),
            }
            frame = frame_renderers[p]()
            lcd.ShowImage(frame)
            if p == "video" and video_player.available:
                time.sleep(video_player.frame_interval)
            else:
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
