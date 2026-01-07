import json
import os
import time
from threading import Event, Lock, Thread
from typing import Optional

import requests

from app.models import WeatherNow


class QWeatherClient:
    """
    QWeather request composition:
    - URL: https://{api_host}{endpoint}?...
    - Auth (API KEY): header "X-QW-Api-Key: <key>"
    - Geo City Lookup endpoint: /geo/v2/city/lookup
    - Real-time weather endpoint: /v7/weather/now
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


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _state_path(state_dir: str, filename: str) -> str:
    return os.path.join(_ensure_dir(state_dir), filename)


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: str, obj: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


class WeatherService:
    def __init__(self, config: dict):
        self.config = config
        self._lock = Lock()
        self._weather = WeatherNow()
        self._stop = Event()
        self._worker: Optional[Thread] = None

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=1.0)

    def snapshot(self) -> WeatherNow:
        with self._lock:
            return self._weather

    # internal
    def _worker_loop(self):
        qcfg = self.config["qweather"]
        paths = self.config["paths"]

        client = QWeatherClient(qcfg["host"], qcfg["api_key"], qcfg["timeout_seconds"])

        geo_cache_p = _state_path(paths["state_dir"], paths["geo_cache"])
        weather_cache_p = _state_path(paths["state_dir"], paths["weather_cache"])

        geo_cache = _load_json(geo_cache_p)
        weather_cache = _load_json(weather_cache_p)

        # Initialize from cache if present
        if weather_cache:
            with self._lock:
                self._weather = WeatherNow(
                    ok=True,
                    stale=True,
                    location_name=weather_cache.get("location_name", "-"),
                    temp_c=weather_cache.get("temp_c", "-"),
                    text=weather_cache.get("text", "-"),
                    icon=weather_cache.get("icon", "-"),
                    obs_time=weather_cache.get("obs_time", "-"),
                    update_time=weather_cache.get("update_time", "-"),
                    last_ok_ts=weather_cache.get("last_ok_ts", 0.0),
                    err="(cache)",
                )

        backoff = 5
        while not self._stop.is_set():
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
                    _save_json(geo_cache_p, geo_cache)

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
                    err="",
                )

                # persist cache
                _save_json(weather_cache_p, {
                    "location_id": location_id,
                    "location_name": location_name,
                    "temp_c": new_w.temp_c,
                    "text": new_w.text,
                    "icon": new_w.icon,
                    "obs_time": new_w.obs_time,
                    "update_time": new_w.update_time,
                    "last_ok_ts": new_w.last_ok_ts,
                })

                with self._lock:
                    self._weather = new_w

                backoff = 5
                self._sleep_or_stop(qcfg["refresh_seconds"])
                continue

            except Exception as e:
                # mark stale but keep last data if any
                with self._lock:
                    cur = self._weather
                    self._weather = WeatherNow(
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
                self._sleep_or_stop(backoff)
                backoff = min(backoff * 2, 300)

    def _sleep_or_stop(self, seconds: float) -> None:
        # Sleep in small increments to respond faster to stop requests
        end = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < end:
            time.sleep(0.5)
