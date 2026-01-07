from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


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
class WeatherDaily:
    date: str
    text_day: str
    temp_max: str
    temp_min: str
    icon_day: str


@dataclass
class WeatherSnapshot:
    now: WeatherNow
    daily: List[WeatherDaily]


@dataclass
class LunarInfo:
    solar: str
    lunar: str
    week: str
    ganzhi_year: str
    ganzhi_month: str
    ganzhi_day: str
    constellation: str
    yi: str
    ji: str


@dataclass
class Snapshot:
    now: datetime
    ip: str
    cpu_temp: str
    gpu_temp: str
    load1: str
    cpu_percent: float
    mem_percent: float
    disk_percent: float
    online: bool
    weather: WeatherSnapshot
    lunar: Optional[LunarInfo]
