"""Sun, moon, name day, on this day, and MNB rates. No estimated values."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable

from astral import Observer
from astral.moon import phase
from astral.sun import sun

from newspaper.db import remember_rates
from newspaper.sources import response_text, status_code

NAME_DAY_CREDIT = "froccsos/nevnapok-json"
WIKI_CREDIT = "Wikipedia (CC BY-SA)"
MNB_URL = "http://www.mnb.hu/arfolyamok.asmx/GetCurrentExchangeRates"
CURRENCIES = ("EUR", "USD", "CHF")
_TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "nevnapok.json"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "YourNicknameTimes/0.1 (morning edition)",
}


def on_this_day_url(language: str, day: date) -> str:
    return (
        f"https://{language}.wikipedia.org/api/rest_v1/feed/onthisday/selected/"
        f"{day.month:02d}/{day.day:02d}"
    )


def collect_almanac(settings: dict, now, *, conn, get: Callable) -> tuple[dict | None, dict, list[str]]:
    from newspaper.sources.weather import coordinates

    extras = bool(settings.get("extras_on", True))
    lines: list[dict] = []
    sources: dict[str, str] = {}
    notes: list[str] = []
    found = coordinates(settings)
    if _enabled(settings, "sun_on", extras):
        if found is None:
            pass
        else:
            try:
                lines.append({"label": "Nap", "text": sun_line(*found, now.date(), now.tzinfo)})
                sources["sun"] = "ok"
            except Exception:
                sources["sun"] = "failed"
    if _enabled(settings, "moon_on", extras):
        if found is None:
            pass
        else:
            try:
                lines.append({"label": "Hold", "text": moon_line(now.date())})
                sources["moon"] = "ok"
            except Exception:
                sources["moon"] = "failed"
    if bool(settings.get("name_day_on", True)):
        try:
            text = name_day_line(now.date())
        except Exception:
            sources["name_day"] = "failed"
        else:
            if text:
                lines.append({"label": "Névnap", "text": text})
                sources["name_day"] = "ok"
    if _enabled(settings, "on_this_day_on", extras):
        language = _language(settings)
        texts, fell_back, state = _on_this_day(get, language, now.date())
        sources["on_this_day"] = state
        if fell_back:
            notes.append("on this day: English fallback\n")
        for text in texts:
            lines.append({"label": "Ezen a napon", "text": f"{text} · {WIKI_CREDIT}"})
    if _enabled(settings, "rates_on", extras):
        rate_line, state, remembered = _rates(get)
        sources["rates"] = state
        if rate_line:
            lines.append({"label": "Árfolyam", "text": rate_line})
            remember_rates(conn, remembered)
    if not lines:
        return None, sources, notes
    return {"lines": lines}, sources, notes


def sun_line(latitude: float, longitude: float, day: date, zone) -> str:
    times = sun(Observer(latitude=latitude, longitude=longitude), date=day, tzinfo=zone)
    rise = times["sunrise"].astimezone(zone).strftime("%H:%M")
    sets = times["sunset"].astimezone(zone).strftime("%H:%M")
    return f"Kel {rise}, nyugszik {sets}"


def moon_line(day: date) -> str:
    value = float(phase(day))
    percent = round((1 - math.cos(2 * math.pi * (value / 28))) / 2 * 100)
    return f"{_moon_name(value)}, {percent}%"


def name_day_line(day: date) -> str | None:
    month = _name_table().get(str(day.month)) or {}
    entry = month.get(str(day.day)) or {}
    names = [str(name).strip() for name in entry.get("main") or [] if str(name).strip()]
    if not names:
        return None
    return f"{', '.join(names)} · {NAME_DAY_CREDIT}"


def _moon_name(value: float) -> str:
    if value < 1:
        return "Újhold"
    if value < 7:
        return "Növekvő sarló"
    if value < 9:
        return "Első negyed"
    if value < 14:
        return "Növekvő hold"
    if value < 16:
        return "Telihold"
    if value < 21:
        return "Fogyó hold"
    if value < 23:
        return "Utolsó negyed"
    return "Fogyó sarló"


def _on_this_day(get: Callable, language: str, day: date) -> tuple[list[str], bool, str]:
    texts, failed = _load_day(get, language, day)
    if texts:
        return texts, False, "ok"
    if language == "en":
        return [], False, "failed" if failed else "ok"
    english, english_failed = _load_day(get, "en", day)
    if english:
        return english, True, "ok"
    if failed or english_failed:
        return [], False, "failed"
    return [], False, "ok"


def _load_day(get: Callable, language: str, day: date) -> tuple[list[str], bool]:
    try:
        response = get(on_this_day_url(language, day), timeout=20, headers=_HEADERS)
        if status_code(response) >= 400:
            return [], True
        payload = json.loads(response_text(response))
    except Exception:
        return [], True
    selected = list(payload.get("selected") or [])
    selected.sort(key=lambda item: len(item.get("pages") or []), reverse=True)
    texts = []
    for item in selected:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        texts.append(text)
        if len(texts) == 3:
            break
    return texts, False


def _rates(get: Callable) -> tuple[str | None, str, list[tuple[str, str, str]]]:
    try:
        response = get(MNB_URL, timeout=20)
        if status_code(response) >= 400:
            raise RuntimeError(f"HTTP {status_code(response)}")
        parsed = _parse_rates(response_text(response))
    except Exception:
        return None, "failed", []
    if parsed is None:
        return None, "failed", []
    rate_date, values = parsed
    parts = [f"{currency} {values[currency]}" for currency in CURRENCIES if currency in values]
    remembered = [(currency, values[currency], rate_date) for currency in CURRENCIES if currency in values]
    return f"{', '.join(parts)} · {rate_date} · MNB", "ok", remembered


def _parse_rates(xml_text: str) -> tuple[str, dict[str, str]] | None:
    root = ET.fromstring(xml_text)
    for element in root.iter():
        if element.tag.split("}")[-1] != "Day":
            continue
        rate_date = str(element.attrib.get("date") or "").strip()
        values: dict[str, str] = {}
        for child in list(element):
            if child.tag.split("}")[-1] != "Rate":
                continue
            currency = str(child.attrib.get("curr") or "").upper()
            amount = str(child.text or "").strip()
            if currency in CURRENCIES and amount:
                values[currency] = amount
        if rate_date and values:
            return rate_date, values
        return None
    return None


def _enabled(settings: dict, key: str, fallback: bool) -> bool:
    if key in settings:
        return bool(settings[key])
    return fallback


def _language(settings: dict) -> str:
    raw = str(settings.get("language") or "hu").split("-")[0].split("_")[0].lower()
    if raw.isalpha():
        return raw
    return "en"


@lru_cache(maxsize=1)
def _name_table() -> dict:
    return json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
