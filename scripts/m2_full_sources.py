#!/usr/bin/env python3
"""M2-B deterministic full-source normalization.

Implements source adapters and a stable output contract for:
- CalDAV events/tasks
- RSS ingest/filter/dedup + OPML import/export support
- weather
- almanac
- FX rates

Failure policy: never fabricate values. Degraded sources are explicitly marked,
and source data is omitted (data=None, omit=True) when unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


RSS_DEDUP_TITLE_RE = re.compile(r"[^\w\s]+", re.UNICODE)
RSS_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Health:
    source: str
    status: str
    message: str | None
    checked_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "message": self.message,
            "checked_at": self.checked_at,
        }


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str | None, tz: ZoneInfo) -> tuple[datetime | None, bool]:
    """Parse date or datetime text.

    Returns (localized datetime, all_day).
    """
    if not value:
        return None, False

    v = value.strip()
    if not v:
        return None, False

    # Date-only path (YYYY-MM-DD)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        dt = datetime.fromisoformat(v).replace(tzinfo=tz)
        return dt, True

    if v.endswith("Z"):
        v = v[:-1] + "+00:00"

    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz), False


def _canonical_title_for_dedup(text: str) -> str:
    lowered = text.lower().strip()
    lowered = RSS_DEDUP_TITLE_RE.sub(" ", lowered)
    lowered = RSS_WS_RE.sub(" ", lowered)
    return lowered.strip()


def normalize_caldav(
    payload: dict[str, Any],
    *,
    timezone: str,
    now_iso: str,
) -> tuple[dict[str, Any] | None, Health]:
    if payload.get("error"):
        return None, Health("caldav", "degraded", str(payload["error"]), _iso_now())

    tz = ZoneInfo(timezone)
    now_dt, _ = _parse_dt(now_iso, tz)
    if now_dt is None:
        return None, Health("caldav", "degraded", "invalid now_iso", _iso_now())

    today = now_dt.date()
    week_limit = today + timedelta(days=7)

    events_out: list[dict[str, Any]] = []
    for row in payload.get("events", []):
        start_dt, start_all_day = _parse_dt(row.get("start"), tz)
        end_dt, end_all_day = _parse_dt(row.get("end"), tz)
        if start_dt is None:
            continue
        if end_dt is None:
            end_dt = start_dt

        events_out.append(
            {
                "id": row.get("id") or row.get("uid") or "",
                "uid": row.get("uid") or "",
                "title": row.get("title") or "",
                "location": row.get("location") or "",
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "all_day": bool(start_all_day or end_all_day),
                "is_recurring_instance": bool(row.get("recurrence_id") or row.get("recurring", False)),
            }
        )

    events_out.sort(key=lambda e: (e["start"], e["title"], e["id"]))

    tasks_out: list[dict[str, Any]] = []
    for row in payload.get("tasks", []):
        status = str(row.get("status") or "").upper()
        if status in {"COMPLETED", "CANCELLED"}:
            continue

        due_dt, due_all_day = _parse_dt(row.get("due"), tz)
        if due_dt is None:
            bucket = "anytime"
            overdue_days = None
        else:
            due_date = due_dt.date()
            if due_date < today:
                bucket = "overdue"
                overdue_days = (today - due_date).days
            elif due_date == today:
                bucket = "today"
                overdue_days = 0
            elif due_date <= week_limit:
                bucket = "week"
                overdue_days = 0
            else:
                bucket = "later"
                overdue_days = 0

        tasks_out.append(
            {
                "id": row.get("id") or row.get("uid") or "",
                "uid": row.get("uid") or "",
                "title": row.get("title") or "",
                "description": row.get("description") or "",
                "due": due_dt.isoformat() if due_dt else None,
                "all_day_due": bool(due_all_day) if due_dt else False,
                "bucket": bucket,
                "overdue_days": overdue_days,
                "priority": row.get("priority") if row.get("priority") is not None else None,
                "categories": sorted([str(x) for x in row.get("categories", [])]),
                "is_recurring_instance": bool(row.get("recurrence_id") or row.get("recurring", False)),
            }
        )

    tasks_out.sort(key=lambda t: (t["due"] or "9999-99-99", t["title"], t["id"]))

    return {
        "timezone": timezone,
        "events": events_out,
        "tasks": tasks_out,
    }, Health("caldav", "ok", None, _iso_now())


def normalize_rss(
    payload: dict[str, Any],
    *,
    now_iso: str,
    max_age_hours: int,
    include_without_published: bool,
) -> tuple[dict[str, Any] | None, Health]:
    if payload.get("error"):
        return None, Health("rss", "degraded", str(payload["error"]), _iso_now())

    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")).astimezone(UTC)
    horizon = now - timedelta(hours=max_age_hours)

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    kept: list[dict[str, Any]] = []

    for row in payload.get("entries", []):
        published_raw = row.get("published")
        published: datetime | None = None
        if published_raw:
            published = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00")).astimezone(UTC)

        if published is None and not include_without_published:
            continue

        if published is not None and published < horizon:
            continue

        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        canonical_title = _canonical_title_for_dedup(title)

        if url and url in seen_urls:
            continue
        if canonical_title and canonical_title in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if canonical_title:
            seen_titles.add(canonical_title)

        kept.append(
            {
                "feed": row.get("feed") or "",
                "category": row.get("category") or "interest",
                "title": title,
                "url": url,
                "publisher": row.get("publisher") or row.get("feed") or "",
                "published": published.isoformat().replace("+00:00", "Z") if published else None,
                "language": row.get("language") or "",
            }
        )

    kept.sort(key=lambda e: (e["published"] or "", e["title"], e["url"]), reverse=True)

    return {
        "items": kept,
        "filters": {
            "max_age_hours": max_age_hours,
            "include_without_published": include_without_published,
            "dedup_order": ["url", "fuzzy_title"],
        },
    }, Health("rss", "ok", None, _iso_now())


def rss_export_opml(feeds: list[dict[str, Any]]) -> str:
    root = ET.Element("opml", version="2.0")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "YourNicknameTimes Feeds"
    body = ET.SubElement(root, "body")
    for feed in sorted(feeds, key=lambda x: (str(x.get("name") or ""), str(x.get("url") or ""))):
        ET.SubElement(
            body,
            "outline",
            {
                "type": "rss",
                "text": str(feed.get("name") or ""),
                "title": str(feed.get("name") or ""),
                "xmlUrl": str(feed.get("url") or ""),
                "category": str(feed.get("category") or "interest"),
                "language": str(feed.get("language") or ""),
                "weight": str(feed.get("weight") if feed.get("weight") is not None else 1),
                "max_items": str(feed.get("max_items") if feed.get("max_items") is not None else 10),
                "enabled": "true" if bool(feed.get("enabled", True)) else "false",
            },
        )
    return ET.tostring(root, encoding="unicode")


def rss_import_opml(opml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(opml_text)
    imported: list[dict[str, Any]] = []
    for node in root.findall(".//outline"):
        xml_url = (node.attrib.get("xmlUrl") or "").strip()
        if not xml_url:
            continue
        imported.append(
            {
                "name": (node.attrib.get("title") or node.attrib.get("text") or "").strip(),
                "url": xml_url,
                "category": (node.attrib.get("category") or "interest").strip() or "interest",
                "language": (node.attrib.get("language") or "").strip(),
                "weight": int(node.attrib.get("weight") or "1"),
                "max_items": int(node.attrib.get("max_items") or "10"),
                "enabled": (node.attrib.get("enabled") or "true").lower() != "false",
            }
        )
    imported.sort(key=lambda x: (x["name"], x["url"]))
    return imported


def normalize_weather(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, Health]:
    if payload.get("error"):
        return None, Health("weather", "degraded", str(payload["error"]), _iso_now())

    today = payload.get("today") or {}
    if not today:
        return None, Health("weather", "degraded", "missing today forecast", _iso_now())

    out_today: dict[str, Any] = {}
    if today.get("summary"):
        out_today["summary"] = today["summary"]
    if today.get("high_c") is not None:
        out_today["high_c"] = float(today["high_c"])
    if today.get("low_c") is not None:
        out_today["low_c"] = float(today["low_c"])

    outlook: list[dict[str, Any]] = []
    for row in payload.get("outlook", []):
        item: dict[str, Any] = {}
        if row.get("date"):
            item["date"] = row["date"]
        if row.get("summary"):
            item["summary"] = row["summary"]
        if row.get("high_c") is not None:
            item["high_c"] = float(row["high_c"])
        if row.get("low_c") is not None:
            item["low_c"] = float(row["low_c"])
        if item:
            outlook.append(item)

    return {
        "today": out_today,
        "outlook": outlook,
        "source": payload.get("source") or "open-meteo",
    }, Health("weather", "ok", None, _iso_now())


def normalize_almanac(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, Health]:
    if payload.get("error"):
        return None, Health("almanac", "degraded", str(payload["error"]), _iso_now())

    out: dict[str, Any] = {}
    for key in ("sunrise", "sunset", "moon_phase", "moon_illumination", "name_day"):
        if payload.get(key) is not None and payload.get(key) != "":
            out[key] = payload[key]

    on_this_day_rows = payload.get("on_this_day") or []
    clipped: list[dict[str, Any]] = []
    for row in on_this_day_rows[:3]:
        if row.get("year") and row.get("text"):
            clipped.append({"year": int(row["year"]), "text": str(row["text"])})
    if clipped:
        out["on_this_day"] = clipped

    if not out:
        return None, Health("almanac", "degraded", "no almanac values", _iso_now())

    return out, Health("almanac", "ok", None, _iso_now())


def normalize_rates(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, Health]:
    if payload.get("error"):
        return None, Health("rates", "degraded", str(payload["error"]), _iso_now())

    published_date = payload.get("published_date")
    source = payload.get("source") or "unknown"
    values = payload.get("values") or {}

    out_values: dict[str, float] = {}
    for pair in ("EUR_HUF", "USD_HUF", "CHF_HUF"):
        if values.get(pair) is not None:
            out_values[pair] = float(values[pair])

    if not out_values or not published_date:
        return None, Health("rates", "degraded", "missing rates payload fields", _iso_now())

    return {
        "source": source,
        "published_date": published_date,
        "values": out_values,
    }, Health("rates", "ok", None, _iso_now())


def build_full_sources_contract(bundle: dict[str, Any]) -> dict[str, Any]:
    settings = bundle.get("settings") or {}
    timezone = settings.get("timezone") or "Europe/Budapest"
    now_iso = settings.get("now_iso") or _iso_now().replace("Z", "+00:00")

    caldav_data, caldav_health = normalize_caldav(
        bundle.get("caldav") or {}, timezone=timezone, now_iso=now_iso
    )
    rss_data, rss_health = normalize_rss(
        bundle.get("rss") or {},
        now_iso=now_iso,
        max_age_hours=int(settings.get("rss_max_age_hours", 24)),
        include_without_published=bool(settings.get("rss_include_without_published", False)),
    )
    weather_data, weather_health = normalize_weather(bundle.get("weather") or {})
    almanac_data, almanac_health = normalize_almanac(bundle.get("almanac") or {})
    rates_data, rates_health = normalize_rates(bundle.get("rates") or {})

    source_data = {
        "caldav": caldav_data,
        "rss": rss_data,
        "weather": weather_data,
        "almanac": almanac_data,
        "rates": rates_data,
    }
    source_health = {
        "caldav": caldav_health.as_dict(),
        "rss": rss_health.as_dict(),
        "weather": weather_health.as_dict(),
        "almanac": almanac_health.as_dict(),
        "rates": rates_health.as_dict(),
    }

    return {
        "schema_version": "m2.full_sources.v1",
        "deterministic": True,
        "generated_at": _iso_now(),
        "timezone": timezone,
        "sources": {
            name: {
                "omit": source_data[name] is None,
                "data": source_data[name],
                "health": source_health[name],
            }
            for name in ("caldav", "rss", "weather", "almanac", "rates")
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic M2 source contract")
    parser.add_argument("--input", required=True, help="Input bundle JSON")
    parser.add_argument("--output", required=True, help="Output normalized JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    normalized = build_full_sources_contract(bundle)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())