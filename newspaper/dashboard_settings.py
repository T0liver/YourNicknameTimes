"""Dashboard settings groups, validation, tests, and routes."""

from __future__ import annotations

import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from newspaper.db import (
    connect,
    delete_feed,
    list_feeds,
    load_feeds,
    load_settings,
    read_secrets,
    rollback_settings,
    save_feed,
    save_settings,
    set_secret,
)
from newspaper.http import check_url
from newspaper.lan import write_status_port
from newspaper.sources.almanac import collect_almanac
from newspaper.sources.caldav_source import collect_caldav, connect as caldav_connect
from newspaper.sources.daily import collect_daily
from newspaper.sources.news import collect_news
from newspaper.sources.weather import collect_weather, coordinates
from newspaper.worker import DropboxUploader, SystemCups, UploadError

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates" / "dashboard"))

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
GROUPS = (
    "general",
    "schedule",
    "weekend",
    "delivery",
    "calendar",
    "news",
    "weather",
    "model",
    "dropbox",
    "printer",
    "system",
)

SECRET_NAMES = (
    "CALDAV_PASSWORD",
    "OPENROUTER_API_KEY",
    "DROPBOX_REFRESH_TOKEN",
    "DROPBOX_APP_KEY",
    "DROPBOX_APP_SECRET",
    "STATUS_BEARER_TOKEN",
    "SETUP_CODE_HASH",
)

TEXT = {
    "en": {
        "settings": "Settings",
        "general": "General",
        "schedule": "Schedule",
        "weekend": "Weekend touches",
        "delivery": "Delivery",
        "calendar": "Calendar and tasks",
        "news": "News",
        "weather": "Weather and almanac",
        "model": "Model",
        "dropbox": "Dropbox",
        "printer": "Printer",
        "system": "System",
        "save": "Save",
        "test": "Test",
        "undo": "Undo last save",
        "home": "Status",
        "editions": "Editions",
        "saved": "Saved.",
        "test_ok": "Test passed.",
        "invalid": "Fix the highlighted fields.",
        "secret_saved": "Saved (replace only)",
        "nickname": "Nickname",
        "motto": "Motto",
        "city": "City",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "timezone": "Timezone",
        "paper_language": "Paper language",
        "dashboard_language": "Dashboard language",
        "paper_size": "Paper size",
        "weekday_start": "Weekday start",
        "weekend_edition": "Weekend edition",
        "weekend_start": "Weekend start",
        "latest_acceptable": "Latest acceptable time",
        "hold_mode": "Hold mode",
        "auto_approve": "Auto-approve",
        "auto_approve_time": "Auto-approve time",
        "weekend_mood": "News mood",
        "show_sun": "Sun icon on weekend",
        "greeting": "Greeting",
        "print_enabled": "Print",
        "upload_enabled": "Upload",
        "cloud_level": "Cloud trim",
        "local_retention_days": "Local retention (days)",
        "dropbox_retention_days": "Dropbox retention (days, empty = keep)",
        "override_date": "One-day override date",
        "override_print": "Override print",
        "override_upload": "Override upload",
        "caldav_host": "Baïkal URL",
        "caldav_username": "Username",
        "caldav_password": "Password",
        "keep_undated_news": "Keep undated feed items",
        "xkcd_on": "xkcd in rotation",
        "extras_on": "Almanac extras",
        "name_day_on": "Name day",
        "sun_on": "Sunrise and sunset",
        "moon_on": "Moon phase",
        "on_this_day_on": "On this day",
        "rates_on": "Exchange rates",
        "model_on": "Model on",
        "model_name": "Model",
        "send_task_descriptions": "Send task descriptions",
        "openrouter_api_key": "API key",
        "printer_name": "Printer",
        "duplex": "Duplex",
        "admin_password": "Admin password",
        "status_token_enabled": "Require bearer token on /status",
        "status_http_port": "Plain-HTTP status port (empty = off)",
        "status_bearer_token": "Status bearer token",
        "dropbox_refresh_token": "Refresh token",
        "dropbox_app_key": "App key",
        "dropbox_app_secret": "App secret",
        "checklist": "Setup checklist",
        "check_nickname": "Nickname",
        "check_city": "City and coordinates",
        "check_caldav": "Baïkal",
        "check_feeds": "Feeds",
        "check_printer": "Printer",
        "check_dropbox": "Dropbox",
        "export_opml": "Export OPML",
        "import_opml": "Import OPML",
        "backup": "Download settings backup",
        "restore": "Restore settings",
        "diagnostics": "Diagnostics bundle",
    },
    "hu": {
        "settings": "Beállítások",
        "general": "Általános",
        "schedule": "Ütemezés",
        "weekend": "Hétvégi részletek",
        "delivery": "Kézbesítés",
        "calendar": "Naptár és feladatok",
        "news": "Hírek",
        "weather": "Időjárás és naptár",
        "model": "Modell",
        "dropbox": "Dropbox",
        "printer": "Nyomtató",
        "system": "Rendszer",
        "save": "Mentés",
        "test": "Teszt",
        "undo": "Utolsó mentés visszavonása",
        "home": "Állapot",
        "editions": "Kiadványok",
        "saved": "Mentve.",
        "test_ok": "A teszt sikeres.",
        "invalid": "Javítsd a megjelölt mezőket.",
        "secret_saved": "Mentve (csak csere)",
        "nickname": "Becenév",
        "motto": "Mottó",
        "city": "Város",
        "latitude": "Szélesség",
        "longitude": "Hosszúság",
        "timezone": "Időzóna",
        "paper_language": "Lap nyelve",
        "dashboard_language": "Felület nyelve",
        "paper_size": "Lapméret",
        "weekday_start": "Hétköznapi indulás",
        "weekend_edition": "Hétvégi kiadás",
        "weekend_start": "Hétvégi indulás",
        "latest_acceptable": "Legkésőbbi elfogadható idő",
        "hold_mode": "Várakozás mód",
        "auto_approve": "Automatikus jóváhagyás",
        "auto_approve_time": "Automatikus jóváhagyás ideje",
        "weekend_mood": "Hírhangulat",
        "show_sun": "Nap ikon hétvégén",
        "greeting": "Üdvözlés",
        "print_enabled": "Nyomtatás",
        "upload_enabled": "Feltöltés",
        "cloud_level": "Felhő vágás",
        "local_retention_days": "Helyi megőrzés (nap)",
        "dropbox_retention_days": "Dropbox megőrzés (nap, üres = örök)",
        "override_date": "Egynapos felülírás dátuma",
        "override_print": "Nyomtatás felülírása",
        "override_upload": "Feltöltés felülírása",
        "caldav_host": "Baïkal URL",
        "caldav_username": "Felhasználónév",
        "caldav_password": "Jelszó",
        "keep_undated_news": "Dátum nélküli hírek",
        "xkcd_on": "xkcd a rotációban",
        "extras_on": "Naptár extrák",
        "name_day_on": "Névnap",
        "sun_on": "Napkelte és napnyugta",
        "moon_on": "Holdfázis",
        "on_this_day_on": "Ezen a napon",
        "rates_on": "Árfolyamok",
        "model_on": "Modell be",
        "model_name": "Modell",
        "send_task_descriptions": "Feladatleírások küldése",
        "openrouter_api_key": "API kulcs",
        "printer_name": "Nyomtató",
        "duplex": "Duplex",
        "admin_password": "Admin jelszó",
        "status_token_enabled": "Bearer token a /status-on",
        "status_http_port": "HTTP státusz port (üres = ki)",
        "status_bearer_token": "Státusz bearer token",
        "dropbox_refresh_token": "Frissítő token",
        "dropbox_app_key": "App kulcs",
        "dropbox_app_secret": "App titok",
        "checklist": "Telepítési lista",
        "check_nickname": "Becenév",
        "check_city": "Város és koordináták",
        "check_caldav": "Baïkal",
        "check_feeds": "Feedek",
        "check_printer": "Nyomtató",
        "check_dropbox": "Dropbox",
        "export_opml": "OPML export",
        "import_opml": "OPML import",
        "backup": "Beállítások mentése",
        "restore": "Beállítások visszaállítása",
        "diagnostics": "Diagnosztikai csomag",
    },
}


def mount(app: FastAPI, *, session, csrf_check, form, db, now) -> None:
    """Register settings routes. Helpers come from web.py."""

    @app.get("/settings/{group}")
    def settings_form(request: Request, group: str):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        if group not in GROUPS:
            return HTMLResponse("Not found", status_code=404)
        data_dir = request.app.state.data_dir
        with db(request) as conn:
            settings = load_settings(conn)
            context = _page_context(request, sess, group, settings, conn, data_dir)
        return TEMPLATES.TemplateResponse(request, f"settings_{group}.html", context)

    @app.post("/settings/{group}")
    async def settings_save(request: Request, group: str):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        if group not in GROUPS:
            return HTMLResponse("Not found", status_code=404)
        body = await form(request)
        if not csrf_check(sess, body.get("csrf", "")):
            return HTMLResponse("Forbidden", status_code=403)
        data_dir = request.app.state.data_dir
        secrets_path = data_dir / "secrets.env"
        with db(request) as conn:
            settings = load_settings(conn)
            updated, errors, secret_updates = _apply_group(group, settings, body, conn=conn)
            if errors:
                context = _page_context(
                    request, sess, group, updated, conn, data_dir, errors=errors, form=body
                )
                return TEMPLATES.TemplateResponse(request, f"settings_{group}.html", context, status_code=400)
            save_settings(conn, updated)
            for name, value in secret_updates.items():
                set_secret(secrets_path, name, value)
            if group == "system":
                write_status_port(data_dir, updated.get("status_http_port"))
        return RedirectResponse(f"/settings/{group}?notice=saved", status_code=303)

    @app.post("/settings/{group}/test")
    async def settings_test(request: Request, group: str):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        if group not in GROUPS:
            return HTMLResponse("Not found", status_code=404)
        body = await form(request)
        if not csrf_check(sess, body.get("csrf", "")):
            return HTMLResponse("Forbidden", status_code=403)
        data_dir = request.app.state.data_dir
        moment = now(request)
        with db(request) as conn:
            settings = load_settings(conn)
            draft, errors, secret_updates = _apply_group(group, settings, body, conn=conn, validate_only=True)
            if errors:
                context = _page_context(
                    request, sess, group, draft, conn, data_dir, errors=errors, form=body
                )
                return TEMPLATES.TemplateResponse(request, f"settings_{group}.html", context, status_code=400)
            for name, value in secret_updates.items():
                set_secret(data_dir / "secrets.env", name, value)
            try:
                message = _run_test(group, draft, conn, data_dir, moment, get=_test_get)
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                return RedirectResponse(
                    f"/settings/{group}?notice=test_fail&message={_quote(message)}", status_code=303
                )
        return RedirectResponse(f"/settings/{group}?notice=test_ok&message={_quote(message)}", status_code=303)

    @app.post("/settings/{group}/rollback")
    async def settings_rollback(request: Request, group: str):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        body = await form(request)
        if not csrf_check(sess, body.get("csrf", "")):
            return HTMLResponse("Forbidden", status_code=403)
        data_dir = request.app.state.data_dir
        with db(request) as conn:
            if rollback_settings(conn):
                write_status_port(data_dir, load_settings(conn).get("status_http_port"))
        return RedirectResponse(f"/settings/{group}?notice=rolled_back", status_code=303)

    @app.get("/settings/news/opml")
    def export_opml(request: Request):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        with db(request) as conn:
            feeds = list_feeds(conn)
        xml = _feeds_to_opml(feeds)
        return Response(content=xml, media_type="application/xml", headers={"Cache-Control": "no-store"})

    @app.post("/settings/news/opml")
    async def import_opml(request: Request):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        body = await form(request)
        if not csrf_check(sess, body.get("csrf", "")):
            return HTMLResponse("Forbidden", status_code=403)
        upload = body.get("opml", "")
        if not upload.strip():
            return RedirectResponse("/settings/news?notice=invalid", status_code=303)
        with db(request) as conn:
            try:
                _import_opml(conn, upload)
            except ValueError:
                return RedirectResponse("/settings/news?notice=invalid", status_code=303)
        return RedirectResponse("/settings/news?notice=saved", status_code=303)

    @app.get("/settings/system/backup")
    def backup_settings(request: Request):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        with db(request) as conn:
            settings = load_settings(conn)
            feeds = list_feeds(conn)
        payload = json.dumps({"settings": settings, "feeds": feeds}, ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="settings-backup.json"'},
        )

    @app.post("/settings/system/restore")
    async def restore_settings(request: Request):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        body = await form(request)
        if not csrf_check(sess, body.get("csrf", "")):
            return HTMLResponse("Forbidden", status_code=403)
        raw = body.get("backup", "")
        try:
            payload = json.loads(raw)
            settings = payload["settings"]
            feeds = payload["feeds"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return RedirectResponse("/settings/system?notice=invalid", status_code=303)
        with db(request) as conn:
            save_settings(conn, settings)
            conn.execute("DELETE FROM feeds")
            for row in feeds:
                save_feed(
                    conn,
                    None,
                    {
                        "name": row["name"],
                        "url": row["url"],
                        "category": row["category"],
                        "language": row["language"],
                        "weight": float(row["weight"]),
                        "max_items": int(row["max_items"]),
                        "enabled": int(row["enabled"]),
                    },
                )
        write_status_port(request.app.state.data_dir, settings.get("status_http_port"))
        return RedirectResponse("/settings/system?notice=saved", status_code=303)

    @app.get("/settings/system/diagnostics")
    def diagnostics_bundle(request: Request):
        sess = session(request)
        if sess is None:
            return RedirectResponse("/login", status_code=303)
        data_dir = request.app.state.data_dir
        with db(request) as conn:
            settings = deepcopy(load_settings(conn))
            feeds = list_feeds(conn)
        secrets = read_secrets(data_dir / "secrets.env")
        for name in SECRET_NAMES:
            if secrets.get(name):
                secrets[name] = "[redacted]"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("settings.json", json.dumps(settings, ensure_ascii=False, indent=2))
            archive.writestr("feeds.json", json.dumps(feeds, ensure_ascii=False, indent=2))
            archive.writestr("secrets.json", json.dumps(secrets, ensure_ascii=False, indent=2))
        buffer.seek(0)
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="diagnostics.zip"'},
        )


def checklist(settings: dict, data_dir: Path) -> list[tuple[str, bool]]:
    secrets = read_secrets(data_dir / "secrets.env")
    coords = coordinates(settings) is not None
    items = [
        ("check_nickname", bool(str(settings.get("nickname") or "").strip())),
        ("check_city", bool(str(settings.get("city") or "").strip()) and coords),
        ("check_caldav", bool(str(settings.get("caldav_host") or "").strip())),
        ("check_feeds", True),
        ("check_printer", bool(str(settings.get("printer_name") or "").strip())),
        ("check_dropbox", bool(str(secrets.get("DROPBOX_REFRESH_TOKEN") or "").strip())),
    ]
    return items


def _page_context(
    request: Request,
    session: dict,
    group: str,
    settings: dict,
    conn,
    data_dir: Path,
    *,
    errors: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
) -> dict:
    lang = str(settings.get("dashboard_language") or "en")
    labels = TEXT.get(lang, TEXT["en"])
    secrets = read_secrets(data_dir / "secrets.env")
    secret_saved = {name: bool(str(secrets.get(name) or "").strip()) for name in SECRET_NAMES}
    printers = _list_printers()
    calendars = []
    if group == "calendar" and str(settings.get("caldav_host") or "").strip():
        try:
            calendars = _discover_calendars(settings, secrets.get("CALDAV_PASSWORD", ""))
        except Exception:
            calendars = []
    feeds = list_feeds(conn) if group == "news" else []
    notice = request.query_params.get("notice", "")
    flash = request.query_params.get("message", "")
    return {
        "group": group,
        "groups": GROUPS,
        "settings": settings,
        "labels": labels,
        "lang": lang,
        "csrf": session.get("csrf", ""),
        "errors": errors or {},
        "form": form or {},
        "secret_saved": secret_saved,
        "printers": printers,
        "calendars": calendars,
        "feeds": feeds,
        "notice": notice,
        "flash": flash,
        "rotation_days": ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        "checklist": checklist(settings, data_dir),
    }


def _apply_group(
    group: str,
    settings: dict,
    form: dict[str, str],
    *,
    conn=None,
    validate_only: bool = False,
) -> tuple[dict, dict[str, str], dict[str, str]]:
    updated = deepcopy(settings)
    errors: dict[str, str] = {}
    secrets: dict[str, str] = {}
    if group == "general":
        _set_text(updated, "nickname", form.get("nickname", ""))
        _set_text(updated, "motto", form.get("motto", ""))
        _set_text(updated, "city", form.get("city", ""))
        _set_coord(updated, "latitude", form.get("latitude", ""), errors)
        _set_coord(updated, "longitude", form.get("longitude", ""), errors)
        _set_timezone(updated, form.get("timezone", ""), errors)
        _set_choice(updated, "language", form.get("language", ""), ("hu", "en"), errors, "language")
        _set_choice(
            updated,
            "dashboard_language",
            form.get("dashboard_language", ""),
            ("hu", "en"),
            errors,
            "dashboard_language",
        )
        _set_choice(updated, "paper_size", form.get("paper_size", ""), ("A4",), errors, "paper_size")
    elif group == "schedule":
        for key in ("weekday_start", "weekend_start", "latest_acceptable", "auto_approve_time"):
            _set_time(updated, key, form.get(key, ""), errors, required=key != "auto_approve_time")
        updated["weekend_edition"] = _bool(form.get("weekend_edition"))
        updated["hold_mode"] = _bool(form.get("hold_mode"))
        updated["auto_approve"] = _bool(form.get("auto_approve"))
        if updated["auto_approve"] and not str(updated.get("auto_approve_time") or "").strip():
            errors["auto_approve_time"] = "required"
    elif group == "weekend":
        _set_choice(updated, "weekend_mood", form.get("weekend_mood", ""), ("light", "neutral"), errors, "weekend_mood")
        updated["show_sun"] = _bool(form.get("show_sun"))
        _set_text(updated, "greeting", form.get("greeting", ""))
    elif group == "delivery":
        updated["print_enabled"] = _bool(form.get("print_enabled"))
        updated["upload_enabled"] = _bool(form.get("upload_enabled"))
        _set_choice(updated, "cloud_level", form.get("cloud_level", ""), ("trimmed", "full"), errors, "cloud_level")
        _set_int(updated, "local_retention_days", form.get("local_retention_days", ""), errors, minimum=1)
        raw_retention = form.get("dropbox_retention_days", "").strip()
        if not raw_retention:
            updated["dropbox_retention_days"] = None
        else:
            _set_int(updated, "dropbox_retention_days", raw_retention, errors, minimum=1)
        _set_text(updated, "override_date", form.get("override_date", ""))
        override_print = form.get("override_print", "")
        updated["override_print"] = None if override_print == "" else _bool(override_print)
        override_upload = form.get("override_upload", "")
        updated["override_upload"] = None if override_upload == "" else _bool(override_upload)
    elif group == "calendar":
        _set_url(updated, "caldav_host", form.get("caldav_host", ""), errors)
        _set_text(updated, "caldav_username", form.get("caldav_username", ""))
        password = form.get("caldav_password", "").strip()
        if password:
            secrets["CALDAV_PASSWORD"] = password
        updated["caldav_event_calendars"] = _selected(form, "event_cal")
        updated["caldav_task_calendars"] = _selected(form, "task_cal")
    elif group == "news":
        updated["keep_undated_news"] = _bool(form.get("keep_undated_news"))
        feed_errors = _validate_feed_form(form)
        errors.update(feed_errors)
        if not errors and not validate_only and conn is not None and form.get("feed_action") in ("save", "delete"):
            _persist_feed(conn, form)
    elif group == "weather":
        _set_coord(updated, "latitude", form.get("latitude", ""), errors)
        _set_coord(updated, "longitude", form.get("longitude", ""), errors)
        _set_choice(updated, "units", form.get("units", ""), ("celsius",), errors, "units")
        updated["xkcd_on"] = _bool(form.get("xkcd_on"))
        updated["extras_on"] = _bool(form.get("extras_on"))
        updated["name_day_on"] = _bool(form.get("name_day_on"))
        updated["sun_on"] = _bool(form.get("sun_on"))
        updated["moon_on"] = _bool(form.get("moon_on"))
        updated["on_this_day_on"] = _bool(form.get("on_this_day_on"))
        updated["rates_on"] = _bool(form.get("rates_on"))
        rotation = deepcopy(updated.get("daily_rotation") or {})
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            value = form.get(f"rotation_{day}", "sudoku")
            if value not in ("xkcd", "sudoku"):
                errors[f"rotation_{day}"] = "invalid"
            else:
                rotation[day] = value
        updated["daily_rotation"] = rotation
    elif group == "model":
        updated["model_on"] = _bool(form.get("model_on"))
        _set_text(updated, "model_name", form.get("model_name", ""))
        updated["send_task_descriptions"] = _bool(form.get("send_task_descriptions"))
        key = form.get("openrouter_api_key", "").strip()
        if key:
            secrets["OPENROUTER_API_KEY"] = key
    elif group == "dropbox":
        for field, name in (
            ("dropbox_refresh_token", "DROPBOX_REFRESH_TOKEN"),
            ("dropbox_app_key", "DROPBOX_APP_KEY"),
            ("dropbox_app_secret", "DROPBOX_APP_SECRET"),
        ):
            value = form.get(field, "").strip()
            if value:
                secrets[name] = value
    elif group == "printer":
        _set_text(updated, "printer_name", form.get("printer_name", ""))
        updated["duplex"] = _bool(form.get("duplex"))
    elif group == "system":
        updated["status_token_enabled"] = _bool(form.get("status_token_enabled"))
        port_raw = form.get("status_http_port", "").strip()
        if not port_raw:
            updated["status_http_port"] = None
        else:
            _set_int(updated, "status_http_port", port_raw, errors, minimum=1, maximum=65535)
            if "status_http_port" not in errors and updated.get("status_http_port") in (22, 80, 443):
                errors["status_http_port"] = "invalid"
        token = form.get("status_bearer_token", "").strip()
        if token:
            secrets["STATUS_BEARER_TOKEN"] = token
        password = form.get("admin_password", "").strip()
        if password:
            from newspaper.web import hash_password

            secrets["ADMIN_PASSWORD_HASH"] = hash_password(password)
    else:
        errors["group"] = "unknown"
    return updated, errors, secrets


def _validate_feed_form(form: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    action = form.get("feed_action", "")
    if action not in ("save", "delete"):
        return errors
    if action == "delete":
        if not form.get("feed_id", "").strip():
            errors["feed_id"] = "required"
        return errors
    if not form.get("feed_name", "").strip():
        errors["feed_name"] = "required"
    url = form.get("feed_url", "").strip()
    if not url:
        errors["feed_url"] = "required"
    else:
        try:
            check_url(url)
        except Exception:
            errors["feed_url"] = "invalid"
    if form.get("feed_category", "") not in ("interest", "local"):
        errors["feed_category"] = "invalid"
    if form.get("feed_language", "") not in ("hu", "en"):
        errors["feed_language"] = "invalid"
    try:
        weight = float(form.get("feed_weight", "1"))
        if weight <= 0:
            errors["feed_weight"] = "invalid"
    except ValueError:
        errors["feed_weight"] = "invalid"
    try:
        max_items = int(form.get("feed_max_items", "20"))
        if max_items <= 0:
            errors["feed_max_items"] = "invalid"
    except ValueError:
        errors["feed_max_items"] = "invalid"
    return errors


def _persist_feed(conn, form: dict[str, str]) -> None:
    action = form.get("feed_action")
    if action == "delete":
        delete_feed(conn, int(form["feed_id"]))
        return
    feed_id = form.get("feed_id", "").strip()
    body = {
        "name": form.get("feed_name", "").strip(),
        "url": form.get("feed_url", "").strip(),
        "category": form.get("feed_category", "interest"),
        "language": form.get("feed_language", "en"),
        "weight": float(form.get("feed_weight", "1")),
        "max_items": int(form.get("feed_max_items", "20")),
        "enabled": 1 if _bool(form.get("feed_enabled", "on")) else 0,
    }
    save_feed(conn, int(feed_id) if feed_id else None, body)


def _run_test(group: str, settings: dict, conn, data_dir: Path, moment: datetime, *, get: Callable) -> str:
    secrets = read_secrets(data_dir / "secrets.env")
    if group == "general":
        if coordinates(settings) is None and str(settings.get("city") or "").strip():
            raise RuntimeError("Coordinates are missing or invalid.")
        return "General settings look valid."
    if group == "schedule":
        return "Schedule times are valid."
    if group == "weekend":
        return "Weekend settings are valid."
    if group == "delivery":
        return "Delivery settings are valid."
    if group == "calendar":
        collect_caldav(settings, secrets.get("CALDAV_PASSWORD", ""), moment, get=get)
        return "Baïkal answered."
    if group == "news":
        collect_news(load_feeds(conn), now=moment, keep_undated=bool(settings.get("keep_undated_news")), light=False, get=get)
        return "Feeds responded."
    if group == "weather":
        if coordinates(settings) is None:
            raise RuntimeError("Set coordinates first.")
        collect_weather(settings, moment, get=get)
        collect_almanac(settings, moment, conn=conn, get=get)
        collect_daily(settings, moment, weekend=False, conn=conn, get=get)
        return "Weather and almanac sources responded."
    if group == "model":
        from newspaper.llm import apply_model

        pool, _ = collect_news(load_feeds(conn), now=moment, keep_undated=False, light=False, get=get)
        snapshot = {"meta": {}, "news": {"interest": [], "local": []}}
        apply_model(
            snapshot,
            settings,
            pool[0],
            [],
            api_key=secrets.get("OPENROUTER_API_KEY", ""),
            light=False,
            edition_dir=None,
            post=requests.post,
        )
        return "OpenRouter answered."
    if group == "dropbox":
        uploader = DropboxUploader()
        uploader._refresh(
            str(secrets.get("DROPBOX_REFRESH_TOKEN") or ""),
            str(secrets.get("DROPBOX_APP_KEY") or ""),
            str(secrets.get("DROPBOX_APP_SECRET") or ""),
        )
        return "Dropbox accepted the token."
    if group == "printer":
        name = str(settings.get("printer_name") or "").strip()
        if not name:
            raise RuntimeError("Pick a printer first.")
        state = SystemCups().printer_state(name)
        if state == "unknown":
            raise RuntimeError("Printer not found in CUPS.")
        return state
    if group == "system":
        return "System settings stored."
    raise RuntimeError("Unknown group.")


def _test_get(url, **kwargs):
    check_url(url)
    return requests.get(url, **kwargs)


def _list_printers() -> list[str]:
    try:
        result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, check=False)
    except OSError:
        return []
    names = []
    for line in (result.stdout or "").splitlines():
        if line.startswith("printer "):
            names.append(line.split()[1])
    return names


def _discover_calendars(settings: dict, password: str) -> list[dict]:
    client = caldav_connect(
        str(settings.get("caldav_host") or ""),
        str(settings.get("caldav_username") or ""),
        password,
        _test_get,
    )
    found = []
    for calendar in client.principal().calendars():
        name = str(getattr(calendar, "name", "") or calendar)
        url = str(getattr(calendar, "url", "") or name)
        supported = set()
        getter = getattr(calendar, "get_supported_components", None)
        if getter:
            raw = getter() or []
            for item in raw:
                text = str(item).upper()
                for kind in ("VEVENT", "VTODO"):
                    if kind in text:
                        supported.add(kind)
        else:
            supported = {"VEVENT", "VTODO"}
        found.append({"name": name, "url": url, "supported": sorted(supported)})
    return found


def _feeds_to_opml(feeds: list[dict]) -> str:
    root = ET.Element("opml", version="2.0")
    body = ET.SubElement(root, "body")
    for feed in feeds:
        ET.SubElement(
            body,
            "outline",
            text=feed["name"],
            title=feed["name"],
            type="rss",
            xmlUrl=feed["url"],
            category=feed["category"],
            language=feed["language"],
        )
    return ET.tostring(root, encoding="unicode")


def _import_opml(conn, text: str) -> None:
    root = ET.fromstring(text)
    for outline in root.iter("outline"):
        url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlURL")
        if not url:
            continue
        check_url(url)
        name = outline.attrib.get("title") or outline.attrib.get("text") or url
        category = outline.attrib.get("category") or "interest"
        if category not in ("interest", "local"):
            category = "interest"
        language = outline.attrib.get("language") or "en"
        save_feed(
            conn,
            None,
            {
                "name": name,
                "url": url,
                "category": category,
                "language": language,
                "weight": 1.0,
                "max_items": 20,
                "enabled": 1,
            },
        )


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _bool(raw: str) -> bool:
    return raw in ("1", "on", "true", "yes")


def _selected(form: dict[str, str], prefix: str) -> list[str]:
    found = []
    for key, value in form.items():
        if not key.startswith(f"{prefix}:") or not _bool(value):
            continue
        found.append(key.split(":", 1)[1])
    return found


def _set_text(settings: dict, key: str, value: str) -> None:
    settings[key] = value.strip()


def _set_choice(settings: dict, key: str, value: str, allowed: tuple[str, ...], errors: dict, field: str) -> None:
    if value not in allowed:
        errors[field] = "invalid"
        return
    settings[key] = value


def _set_time(settings: dict, key: str, value: str, errors: dict, *, required: bool) -> None:
    value = value.strip()
    if not value:
        if required:
            errors[key] = "required"
        else:
            settings[key] = ""
        return
    if not TIME_RE.match(value):
        errors[key] = "invalid"
        return
    settings[key] = value


def _set_int(
    settings: dict,
    key: str,
    value: str,
    errors: dict,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[key] = "invalid"
        return
    if minimum is not None and number < minimum:
        errors[key] = "invalid"
        return
    if maximum is not None and number > maximum:
        errors[key] = "invalid"
        return
    settings[key] = number


def _set_coord(settings: dict, key: str, value: str, errors: dict) -> None:
    value = value.strip()
    if not value:
        settings[key] = ""
        return
    try:
        number = float(value)
    except ValueError:
        errors[key] = "invalid"
        return
    limit = 90 if key == "latitude" else 180
    if abs(number) > limit:
        errors[key] = "invalid"
        return
    settings[key] = value


def _set_timezone(settings: dict, value: str, errors: dict) -> None:
    value = value.strip()
    if not value:
        errors["timezone"] = "required"
        return
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        errors["timezone"] = "invalid"
        return
    settings["timezone"] = value


def _set_url(settings: dict, key: str, value: str, errors: dict) -> None:
    value = value.strip()
    if not value:
        settings[key] = ""
        return
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https", "file"):
        errors[key] = "invalid"
        return
    settings[key] = value
