from dataclasses import dataclass
from datetime import datetime


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
