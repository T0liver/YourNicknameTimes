"""Open-Meteo forecast in Celsius, with a Hungarian summary."""

from __future__ import annotations

import json
from datetime import date
from typing import Callable
from urllib.parse import urlencode

from newspaper.sources import response_text, status_code

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
SHORT_DAYS = ("H", "K", "Sze", "Cs", "P", "Szo", "V")
UNAVAILABLE = {"summary": "Forecast unavailable", "outlook": []}
PHRASES = {
    0: "Derült",
    1: "Túlnyomóan derült",
    2: "Részben felhős",
    3: "Borult",
    45: "Köd",
    48: "Zúzmarás köd",
    51: "Enyhe szitálás",
    53: "Szitálás",
    55: "Erős szitálás",
    56: "Ónos szitálás",
    57: "Erős ónos szitálás",
    61: "Enyhe eső",
    63: "Eső",
    65: "Erős eső",
    66: "Ónos eső",
    67: "Erős ónos eső",
    71: "Enyhe havazás",
    73: "Havazás",
    75: "Erős havazás",
    77: "Hószemcsék",
    80: "Zápor",
    81: "Erős zápor",
    82: "Heves zápor",
    85: "Hózápor",
    86: "Erős hózápor",
    95: "Zivatar",
    96: "Jégesős zivatar",
    99: "Erős jégesős zivatar",
}


def coordinates(settings: dict) -> tuple[float, float] | None:
    if "latitude" not in settings or "longitude" not in settings:
        return None
    try:
        lat = float(settings["latitude"])
        lon = float(settings["longitude"])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def forecast_url(latitude: float, longitude: float, timezone: str) -> str:
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": timezone,
            "forecast_days": 5,
            "temperature_unit": "celsius",
        }
    )
    return f"{OPEN_METEO}?{query}"


def collect_weather(settings: dict, now, *, get: Callable) -> tuple[dict | None, str | None]:
    found = coordinates(settings)
    if found is None:
        return None, None
    latitude, longitude = found
    timezone = str(settings.get("timezone") or "Europe/Budapest")
    url = forecast_url(latitude, longitude, timezone)
    try:
        response = get(url, timeout=20)
        if status_code(response) >= 400:
            raise RuntimeError(f"HTTP {status_code(response)}")
        block = _block(json.loads(response_text(response)), now.date())
    except Exception:
        return dict(UNAVAILABLE), "failed"
    return block, "ok"


def _block(payload: dict, today: date) -> dict:
    daily = payload["daily"]
    dates = list(daily["time"])
    codes = list(daily["weather_code"])
    highs = list(daily["temperature_2m_max"])
    lows = list(daily["temperature_2m_min"])
    index = dates.index(today.isoformat())
    outlook = []
    for cursor in range(index + 1, min(len(dates), index + 5)):
        day = date.fromisoformat(dates[cursor])
        outlook.append(
            {
                "day": SHORT_DAYS[day.weekday()],
                "text": _phrase(codes[cursor]),
                "temps": f"{_degrees(highs[cursor])} / {_degrees(lows[cursor])}",
            }
        )
    return {
        "high": f"{_degrees(highs[index])}°",
        "low": f"{_degrees(lows[index])}°",
        "hl_label": "Max / Min",
        "summary": _phrase(codes[index]),
        "outlook": outlook,
    }


def _phrase(code) -> str:
    if code is None:
        raise ValueError("missing weather code")
    return PHRASES.get(int(code), "Változó")


def _degrees(value) -> int:
    if value is None:
        raise ValueError("missing temperature")
    return round(float(value))
