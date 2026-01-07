import json
import os
from copy import deepcopy
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "display": {
        "w": 240,
        "h": 320,
        "width": 240,
        "height": 320,
        "brightness": 80,
        "page_cycle_seconds": 10,
        "fps_idle": 1,
        "fps_pet": 8,
    },
    "network": {
        "connect_test_host": "1.1.1.1",
        "connect_test_port": 53,
        "connect_timeout": 1.5,
        "refresh_seconds": 5,
    },
    "qweather": {
        "host": "YOUR_HOST.qweatherapi.com",
        "api_key": "0123456789ABCDEF",
        "lang": "zh",
        "unit": "m",
        "timeout_seconds": 2.0,
        "refresh_seconds": 900,
        "lookup": {
            "location_text": "Beijing",
            "range": "cn",
            "number": 1,
        },
    },
    "ui": {
        "ticker_height": 24,
        "ticker_speed_px_per_s": 40,
    },
    "paths": {
        "state_dir": os.path.expanduser("~/.cache/deskpet-panel"),
        "geo_cache": "qweather_geo.json",
        "weather_cache": "weather_now.json",
    },
}


def _merge_section(dst: Dict[str, Any], key: str, overrides: Dict[str, Any]) -> None:
    base = deepcopy(DEFAULT_CONFIG.get(key, {}))
    if overrides:
        base.update(overrides)
    dst[key] = base


def _normalize_display(cfg: Dict[str, Any]) -> None:
    disp = cfg.get("display", {})
    # backfill width/height aliases
    w = disp.get("w") or disp.get("width")
    h = disp.get("h") or disp.get("height")
    disp["w"] = w or DEFAULT_CONFIG["display"]["w"]
    disp["h"] = h or DEFAULT_CONFIG["display"]["h"]
    disp.setdefault("width", disp["w"])
    disp.setdefault("height", disp["h"])
    # legacy fps keys
    if "fps_idle" not in disp and "fps_static" in disp:
        disp["fps_idle"] = disp["fps_static"]
    cfg["display"] = disp


def _normalize_network(cfg: Dict[str, Any]) -> None:
    net = cfg.get("network", {})
    # legacy key mapping
    if "connect_test_host" not in net and "test_host" in net:
        net["connect_test_host"] = net["test_host"]
    if "connect_test_port" not in net and "test_port" in net:
        net["connect_test_port"] = net["test_port"]
    cfg["network"] = net


def _normalize_qweather(cfg: Dict[str, Any]) -> None:
    qw = cfg.get("qweather", {})
    # allow flat location_text to map into lookup
    if "lookup" not in qw:
        qw["lookup"] = {}
    if "location_text" in qw:
        qw["lookup"].setdefault("location_text", qw["location_text"])
    cfg["qweather"] = qw


def _normalize_ui(cfg: Dict[str, Any]) -> None:
    ui = cfg.get("ui", {})
    # pull ticker speed from legacy ticker section if present
    ticker = cfg.get("ticker", {})
    if "ticker_speed_px_per_s" not in ui and "speed_px_per_s" in ticker:
        ui["ticker_speed_px_per_s"] = ticker["speed_px_per_s"]
    cfg["ui"] = ui


def _normalize_paths(cfg: Dict[str, Any]) -> None:
    paths = cfg.get("paths", {})
    if "state_dir" in paths:
        paths["state_dir"] = os.path.expanduser(paths["state_dir"])
    cfg["paths"] = paths


def load_config(path: str) -> dict:
    raw: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except Exception:
            # fallback: minimal JSON-compatible YAML
            with open(path, "r", encoding="utf-8") as f:
                raw = json.loads(f.read())

    cfg: Dict[str, Any] = {}
    # start with user-provided sections and fill defaults later
    _merge_section(cfg, "display", raw.get("display", {}))
    _merge_section(cfg, "network", raw.get("network", {}))
    _merge_section(cfg, "qweather", raw.get("qweather", {}))
    _merge_section(cfg, "ui", raw.get("ui", {}))
    _merge_section(cfg, "paths", raw.get("paths", {}))

    # normalize legacy/alias keys
    _normalize_display(cfg)
    _normalize_network(cfg)
    _normalize_qweather(cfg)
    _normalize_ui(cfg)
    _normalize_paths(cfg)

    return cfg
