import datetime as _dt
from typing import Optional
import requests


def get_local_time(timezone: Optional[str]) -> str:
    if not timezone:
        now = _dt.datetime.utcnow()
        return now.strftime("%Y-%m-%d %I:%M %p UTC")
    try:
        resp = requests.get(f"https://worldtimeapi.org/api/timezone/{timezone}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        dt_str = data.get("datetime", "")
        if dt_str:
            # Parse ISO format: 2025-10-09T14:30:00.123456-07:00
            dt = _dt.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p %Z").strip()
        return _dt.datetime.utcnow().strftime("%Y-%m-%d %I:%M %p UTC")
    except Exception:
        return _dt.datetime.utcnow().strftime("%Y-%m-%d %I:%M %p UTC")


def get_weather_summary(latitude: Optional[float], longitude: Optional[float]) -> str:
    if latitude is None or longitude is None:
        return "Location not set. Provide LATITUDE and LONGITUDE in .env."
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude="
            f"{latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        j = resp.json()
        cur = j.get("current", {})
        t = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        wind = cur.get("wind_speed_10m")
        rh = cur.get("relative_humidity_2m")
        parts = []
        if t is not None:
            parts.append(f"{t}°C")
        if feels is not None:
            parts.append(f"feels {feels}°C")
        if rh is not None:
            parts.append(f"RH {rh}%")
        if wind is not None:
            parts.append(f"wind {wind} m/s")
        if not parts:
            return "Weather unavailable right now."
        return ", ".join(parts)
    except Exception:
        return "Weather service unavailable."


