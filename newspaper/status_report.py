"""Build the /status document from the database, without the HTTP layer."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

STALE_AFTER = timedelta(minutes=2)
CLOCK_GRACE = timedelta(hours=1)
DISK_FLOOR_MB = 100
ALMANAC_KEYS = ("sun", "moon", "name_day", "on_this_day", "rates", "almanac")


def status_http_code(state: str, *, strict: bool) -> int:
    if state == "down":
        return 503
    if strict and state == "degraded":
        return 503
    return 200


def build_report(
    conn,
    *,
    now: datetime,
    uptime_seconds: float,
    cpu_temp_c: float | None,
    version: str,
) -> tuple[dict, str]:
    try:
        return _build(conn, now=now, uptime_seconds=uptime_seconds, cpu_temp_c=cpu_temp_c, version=version)
    except Exception:
        return _down_shell(now=now, uptime_seconds=uptime_seconds, cpu_temp_c=cpu_temp_c, version=version), "down"


def _build(conn, *, now, uptime_seconds, cpu_temp_c, version) -> tuple[dict, str]:
    settings = _settings(conn)
    beat = conn.execute("SELECT * FROM heartbeat ORDER BY id DESC LIMIT 1").fetchone()
    run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    alerts = conn.execute(
        "SELECT kind, level, message, created_at FROM alerts ORDER BY id"
    ).fetchall()
    alive, last_heartbeat = _heartbeat_alive(beat, now)
    ntp_synced = bool(beat["ntp_synced"]) if beat is not None else False
    disk_free = float(beat["disk_free_mb"]) if beat is not None else None
    printer_raw = beat["printer_state"] if beat is not None else ""
    sources = _sources(run)
    checks = {
        "caldav": _scalar_check(sources.get("caldav"), run),
        "rss": _rss_check(sources.get("feeds")),
        "weather": _group_check(sources.get("weather"), run),
        "almanac": _almanac_check(sources, run),
        "llm": _llm_check(sources, run),
        "dropbox": _dropbox_check(conn, run),
        "printer": _printer_check(printer_raw),
    }
    state = _overall(
        alive=alive,
        ntp_synced=ntp_synced,
        uptime_seconds=uptime_seconds,
        disk_free=disk_free,
        deadline_missed=_deadline_missed(conn, settings, now),
        run=run,
        checks=checks,
        alerts=alerts,
    )
    body = {
        "status": state,
        "time": now.isoformat(timespec="seconds"),
        "version": version,
        "uptime_seconds": int(uptime_seconds),
        "worker": {"alive": alive, "last_heartbeat": last_heartbeat},
        "schedule": _schedule(settings, now),
        "last_edition": _last_edition(conn, run),
        "checks": checks,
        "system": {
            "disk_free_mb": disk_free,
            "cpu_temp_c": cpu_temp_c,
            "ntp_synced": ntp_synced,
        },
        "alerts": [
            {
                "code": row["kind"],
                "severity": "info" if row["level"] == "info" else "warning",
                "since": row["created_at"],
            }
            for row in alerts
        ],
    }
    return body, state


def _down_shell(*, now, uptime_seconds, cpu_temp_c, version) -> dict:
    unknown = {"status": "unknown", "last_success": None, "message": None}
    return {
        "status": "down",
        "time": now.isoformat(timespec="seconds"),
        "version": version,
        "uptime_seconds": int(uptime_seconds),
        "worker": {"alive": False, "last_heartbeat": None},
        "schedule": {"next_run": None, "mode": None, "hold_mode": None, "llm_enabled": None},
        "last_edition": None,
        "checks": {
            "caldav": dict(unknown),
            "rss": {"status": "unknown", "feeds_ok": 0, "feeds_total": 0, "message": None},
            "weather": dict(unknown),
            "almanac": dict(unknown),
            "llm": {"status": "unknown", "requests_today": None, "daily_limit": None, "message": None},
            "dropbox": dict(unknown),
            "printer": {"status": "unknown", "state": None, "message": None},
        },
        "system": {"disk_free_mb": None, "cpu_temp_c": cpu_temp_c, "ntp_synced": False},
        "alerts": [],
    }


def _settings(conn) -> dict:
    row = conn.execute("SELECT body FROM settings ORDER BY version DESC LIMIT 1").fetchone()
    if row is None:
        return {}
    loaded = json.loads(row["body"])
    return loaded if isinstance(loaded, dict) else {}


def _sources(run) -> dict:
    if run is None:
        return {}
    try:
        loaded = json.loads(run["sources"] or "{}")
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _heartbeat_alive(beat, now: datetime) -> tuple[bool, str | None]:
    if beat is None:
        return False, None
    try:
        recorded = datetime.fromisoformat(beat["recorded_at"])
    except ValueError:
        return False, None
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=now.tzinfo)
    alive = now - recorded <= STALE_AFTER
    return alive, beat["recorded_at"]


def _overall(*, alive, ntp_synced, uptime_seconds, disk_free, deadline_missed, run, checks, alerts) -> str:
    clock_down = (not ntp_synced) and uptime_seconds > CLOCK_GRACE.total_seconds()
    disk_down = disk_free is not None and disk_free < DISK_FLOOR_MB
    if not alive or clock_down or disk_down or deadline_missed:
        return "down"
    if run is not None and run["status"] in {"failed", "done_degraded"}:
        return "degraded"
    if any(row["level"] in {"warning", "error"} for row in alerts):
        return "degraded"
    for check in checks.values():
        if check.get("status") in {"failed", "degraded"}:
            return "degraded"
    return "ok"


def _deadline_missed(conn, settings, now: datetime) -> bool:
    clock = now.hour * 60 + now.minute
    if clock < _minutes(settings.get("latest_acceptable") or "10:00"):
        return False
    return not _edition_exists(conn, now.date())


def _edition_exists(conn, day: date) -> bool:
    iso = day.isoformat()
    if conn.execute("SELECT 1 FROM editions WHERE edition_date = ?", (iso,)).fetchone():
        return True
    return (
        conn.execute(
            "SELECT 1 FROM runs WHERE edition_date = ? AND status != 'failed'",
            (iso,),
        ).fetchone()
        is not None
    )


def _schedule(settings, now: datetime) -> dict:
    weekend = now.weekday() >= 5 and bool(settings.get("weekend_edition", True))
    return {
        "next_run": _next_run(settings, now).isoformat(timespec="seconds"),
        "mode": "weekend" if weekend else "weekday",
        "hold_mode": bool(settings.get("hold_mode", True)),
        "llm_enabled": bool(settings.get("model_on", True)),
    }


def _next_run(settings, now: datetime) -> datetime:
    if now < _start_at(settings, now):
        return _start_at(settings, now)
    tomorrow = now + timedelta(days=1)
    return _start_at(settings, tomorrow)


def _start_at(settings, moment: datetime) -> datetime:
    weekend = moment.weekday() >= 5 and bool(settings.get("weekend_edition", True))
    clock = settings.get("weekend_start") if weekend else settings.get("weekday_start")
    if not clock:
        clock = "08:00" if weekend else "06:30"
    hour, minute = [int(part) for part in str(clock).split(":", 1)]
    return datetime(moment.year, moment.month, moment.day, hour, minute, tzinfo=moment.tzinfo)


def _last_edition(conn, run) -> dict | None:
    if run is None:
        return None
    pending = conn.execute(
        """
        SELECT 1 FROM jobs
        WHERE edition_date = ? AND kind = 'hold' AND status = 'pending'
        """,
        (run["edition_date"],),
    ).fetchone()
    return {
        "date": run["edition_date"],
        "status": run["status"],
        "awaiting_approval": run["status"] == "awaiting_approval" or pending is not None,
        "finished_at": run["finished_at"],
    }


def _scalar_check(value, run) -> dict:
    status = _named_status(value)
    return {"status": status, "last_success": _last_success(status, run), "message": None}


def _group_check(value, run) -> dict:
    status = _named_status(value)
    return {"status": status, "last_success": _last_success(status, run), "message": None}


def _named_status(value) -> str:
    if value is None:
        return "unknown"
    if value == "ok":
        return "ok"
    if value == "failed":
        return "degraded"
    if isinstance(value, dict):
        return _map_status(value)
    return "unknown"


def _map_status(mapping: dict) -> str:
    if not mapping:
        return "unknown"
    states = [str(item) for item in mapping.values()]
    if all(item == "ok" for item in states):
        return "ok"
    if any(item == "ok" for item in states):
        return "degraded"
    if any(item == "failed" for item in states):
        return "degraded"
    return "unknown"


def _rss_check(value) -> dict:
    if value is None:
        return {"status": "unknown", "feeds_ok": 0, "feeds_total": 0, "message": None}
    if value == "failed":
        return {"status": "failed", "feeds_ok": 0, "feeds_total": 0, "message": None}
    if not isinstance(value, dict):
        return {"status": "unknown", "feeds_ok": 0, "feeds_total": 0, "message": None}
    total = len(value)
    ok = sum(1 for item in value.values() if item == "ok")
    failing = total - ok
    status = _map_status(value)
    message = None
    if failing == 1:
        message = "1 feed failing"
    elif failing > 1:
        message = f"{failing} feeds failing"
    return {"status": status, "feeds_ok": ok, "feeds_total": total, "message": message}


def _almanac_check(sources: dict, run) -> dict:
    present = {key: sources[key] for key in ALMANAC_KEYS if key in sources}
    if not present:
        status = "unknown"
    else:
        status = _map_status(present)
    return {"status": status, "last_success": _last_success(status, run), "message": None}


def _llm_check(sources: dict, run) -> dict:
    if run is None:
        status = "unknown"
    elif sources.get("model") == "failed":
        status = "degraded"
    else:
        status = "ok"
    return {
        "status": status,
        "requests_today": _request_count(run),
        "daily_limit": None,
        "message": None,
    }


def _request_count(run) -> int | None:
    if run is None or not run["directory"]:
        return None
    path = Path(run["directory"]) / "llm" / "requests.json"
    if not path.is_file():
        return 0
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict) or "count" not in loaded:
        return None
    try:
        return int(loaded["count"])
    except (TypeError, ValueError):
        return None


def _dropbox_check(conn, run) -> dict:
    alert = conn.execute("SELECT 1 FROM alerts WHERE kind = 'dropbox'").fetchone()
    if alert is not None:
        return {"status": "degraded", "last_success": None, "message": None}
    if run is not None and int(run["uploaded"] or 0) == 1:
        return {"status": "ok", "last_success": _last_success("ok", run), "message": None}
    return {"status": "unknown", "last_success": None, "message": None}


def _printer_check(raw: str) -> dict:
    text = raw or ""
    if text == "":
        return {"status": "unknown", "state": None, "message": None}
    if " is idle" in text:
        return {"status": "ok", "state": "idle", "message": None}
    return {"status": "degraded", "state": "problem", "message": None}


def _last_success(status: str, run):
    if status == "ok" and run is not None:
        return run["finished_at"]
    return None


def _minutes(value: str) -> int:
    hour, minute = str(value).split(":", 1)
    return int(hour) * 60 + int(minute)
