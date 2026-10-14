"""Write a model-off edition.json and render print.pdf from that file."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from newspaper.db import (
    increment_volume,
    init_data,
    load_feeds,
    load_settings,
    read_password,
    record_edition,
    remember_puzzle,
)
from newspaper.http import get as http_get
from newspaper.overflow import drop_one
from newspaper.render import build_document, render_edition
from newspaper.sources.almanac import collect_almanac
from newspaper.sources.caldav_source import collect_caldav
from newspaper.sources.daily import collect_daily
from newspaper.sources.news import collect_news
from newspaper.sources.weather import collect_weather

HU_MONTHS = (
    "január",
    "február",
    "március",
    "április",
    "május",
    "június",
    "július",
    "augusztus",
    "szeptember",
    "október",
    "november",
    "december",
)
HU_WEEKDAYS = (
    "hétfő",
    "kedd",
    "szerda",
    "csütörtök",
    "péntek",
    "szombat",
    "vasárnap",
)
_DROP_LIMIT = 200


def format_dateline(volume: int, when: datetime, city: str) -> str:
    date = f"{when.year}. {HU_MONTHS[when.month - 1]} {when.day}."
    weekday = HU_WEEKDAYS[when.weekday()]
    parts = [f"Vol. {volume}", date, weekday]
    if city:
        parts.append(city)
    parts.append(f"AS OF {when.strftime('%H:%M')}")
    return " · ".join(parts)


def nickname_for(settings: dict) -> str:
    nickname = str(settings.get("nickname") or "").strip()
    if nickname:
        return nickname
    title = str(settings.get("title") or "Your Nickname Times")
    if title.endswith(" Times"):
        return title[: -len(" Times")]
    return title


def assemble_snapshot(
    settings: dict,
    started: datetime,
    *,
    conn,
    password: str,
    get=None,
    client=None,
    rng=None,
) -> tuple[dict, list[str]]:
    if get is None:
        get = http_get
    zone_name = settings.get("timezone") or "Europe/Budapest"
    local = started.astimezone(ZoneInfo(zone_name))
    weekend = bool(settings.get("weekend_edition")) and local.weekday() >= 5
    light = weekend and settings.get("weekend_mood") == "light"
    sources: dict = {}
    notes: list[str] = []

    schedule, caldav_status = collect_caldav(
        settings,
        password,
        local,
        client=client,
        get=get,
    )
    sources.update(caldav_status)

    try:
        news, feed_status = collect_news(
            load_feeds(conn),
            now=local,
            keep_undated=bool(settings.get("keep_undated_news")),
            light=light,
            get=get,
        )
        sources["feeds"] = feed_status
    except Exception:
        news = []
        sources["feeds"] = "failed"

    try:
        weather, weather_status = collect_weather(settings, local, get=get)
        if weather_status:
            sources["weather"] = weather_status
    except Exception:
        weather = {"summary": "Forecast unavailable", "outlook": []}
        sources["weather"] = "failed"

    try:
        daily_item, daily_status = collect_daily(
            settings,
            local,
            weekend=weekend,
            conn=conn,
            get=get,
            rng=rng,
        )
        sources.update(daily_status)
    except Exception:
        daily_item = ""
        sources["daily"] = "failed"

    try:
        almanac, almanac_status, almanac_notes = collect_almanac(settings, local, conn=conn, get=get)
        sources.update(almanac_status)
        notes.extend(almanac_notes)
    except Exception:
        almanac = None
        sources["almanac"] = "failed"

    city = str(settings.get("city") or "").strip()
    volume = int(settings.get("volume") or 1)
    snapshot = {
        "nickname": nickname_for(settings),
        "motto": settings.get("motto") or "",
        "dateline": format_dateline(volume, local, city),
        "weekend": weekend,
        "show_sun": bool(settings.get("show_sun", True)),
        "greeting": settings.get("greeting") or "",
        "news": news,
        "today": schedule["today"],
        "this_week": schedule["this_week"],
        "weather": weather,
        "prep": schedule["prep"],
        "due": schedule["due"],
        "overdue": schedule["overdue"],
        "daily_item": daily_item,
        "almanac": almanac,
        "meta": {
            "mode": "off",
            "model": None,
            "trims": [],
            "sources": sources,
            "as_of": local.isoformat(timespec="minutes"),
            "volume": volume,
            "language": settings.get("language") or "hu",
            "timezone": zone_name,
        },
    }
    return snapshot, notes


def weasy_render(edition: dict, out_path: Path) -> int:
    document = build_document(edition)
    pages = len(document.pages)
    if pages != 1:
        if out_path.exists():
            out_path.unlink()
        return pages
    render_edition(out_path, edition)
    return pages


def build_edition(snapshot: dict, edition_dir: Path, *, render_pdf=None, notes: list[str] | None = None) -> int:
    """Write edition.json, render from the loaded file, and drop until one page."""
    if render_pdf is None:
        render_pdf = weasy_render
    edition_dir.mkdir(parents=True, exist_ok=True)
    working = deepcopy(snapshot)
    json_path = edition_dir / "edition.json"
    pdf_path = edition_dir / "print.pdf"
    log_path = edition_dir / "run.log"
    trims: list[str] = []
    log_lines: list[str] = list(notes or [])

    def write_log() -> None:
        log_path.write_text("".join(log_lines), encoding="utf-8")

    for _ in range(_DROP_LIMIT):
        meta = dict(working.get("meta") or {})
        meta["mode"] = "off"
        meta["model"] = None
        meta["trims"] = list(trims)
        working["meta"] = meta
        json_path.write_text(
            json.dumps(working, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        try:
            pages = render_pdf(loaded, pdf_path)
        except Exception as exc:
            if pdf_path.exists():
                pdf_path.unlink()
            log_lines.append(f"build failed: {exc}\n")
            write_log()
            return 1
        if pages == 1:
            write_log()
            return 0
        if pdf_path.exists():
            pdf_path.unlink()
        what = drop_one(working)
        if what is None:
            write_log()
            return 1
        trims.append(what)
        log_lines.append(f"drop: {what}\n")
        write_log()
    if pdf_path.exists():
        pdf_path.unlink()
    write_log()
    return 1


def run(data_dir: Path, *, now: datetime | None = None, render_pdf=None, get=None, client=None, rng=None) -> int:
    data_dir = Path(data_dir)
    conn = init_data(data_dir)
    try:
        settings = load_settings(conn)
        zone = ZoneInfo(settings.get("timezone") or "Europe/Budapest")
        started = now or datetime.now(zone)
        if started.tzinfo is None:
            started = started.replace(tzinfo=zone)
        else:
            started = started.astimezone(zone)
        snapshot, notes = assemble_snapshot(
            settings,
            started,
            conn=conn,
            password=read_password(data_dir / "secrets.env"),
            get=get,
            client=client,
            rng=rng,
        )
        edition_dir = data_dir / "editions" / started.date().isoformat()
        xkcd_id = (snapshot.get("meta") or {}).get("sources", {}).pop("xkcd_id", None)
        code = build_edition(snapshot, edition_dir, render_pdf=render_pdf, notes=notes)
        if code == 0:
            if xkcd_id:
                try:
                    remember_puzzle(conn, "xkcd", str(xkcd_id), started.date().isoformat())
                except Exception:
                    pass
            record_edition(conn, started.date().isoformat(), int(settings["volume"]), edition_dir)
            increment_volume(conn)
        return code
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write a model-off edition and its one-page PDF.")
    parser.add_argument("--data-dir", default="data", help="Directory for the database and editions")
    args = parser.parse_args(argv)
    code = run(Path(args.data_dir))
    if code:
        print("edition failed", file=sys.stderr)
        raise SystemExit(code)
