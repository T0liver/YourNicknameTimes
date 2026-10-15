import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from newspaper.db import connect, init_data, load_settings, save_settings, set_secret
from newspaper.web import create_app, hash_password

ZONE = ZoneInfo("Europe/Budapest")
NINE = datetime(2026, 10, 14, 9, 0, tzinfo=ZONE)
TEN = datetime(2026, 10, 14, 10, 0, tzinfo=ZONE)
DAY = "2026-10-14"


def _app(data, **kwargs):
    options = dict(cache_seconds=0, clock=lambda: NINE, uptime_seconds=100, cpu_temp_c=None)
    options.update(kwargs)
    return create_app(data, **options)


def _prepare(tmp_path):
    data = tmp_path / "data"
    init_data(data)
    return data


def _heartbeat(data, when, *, age=0, printer="printer Brother is idle. enabled since today", disk=500, ntp=1):
    recorded = (when - timedelta(seconds=age)).isoformat(timespec="seconds")
    conn = connect(data / "newspaper.db")
    try:
        conn.execute("DELETE FROM heartbeat")
        conn.execute(
            """
            INSERT INTO heartbeat (recorded_at, ntp_synced, printer_state, disk_free_mb)
            VALUES (?, ?, ?, ?)
            """,
            (recorded, ntp, printer, disk),
        )
        conn.commit()
    finally:
        conn.close()
    return recorded


def _run(data, *, status="awaiting_approval", sources=None, finished="2026-10-14T06:33:40+02:00"):
    directory = data / "editions" / DAY
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"caldav": "ok", "feeds": {"Telex": "ok", "Wired": "ok"}, "weather": "ok"}
    if sources is not None:
        payload = sources
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO runs (
                edition_date, started_at, finished_at, status, printed, uploaded,
                cups_job_id, upload_attempts, delivery, timing, sources, model, trims, directory
            ) VALUES (?, ?, ?, ?, 0, 0, NULL, 0, 'held', '{}', ?, NULL, '[]', ?)
            """,
            (DAY, "2026-10-14T06:30:00+02:00", finished, status, json.dumps(payload), str(directory)),
        )
        conn.commit()
    finally:
        conn.close()
    return directory


def test_held_edition_is_ok_and_head_is_empty(tmp_path):
    data = _prepare(tmp_path)
    recorded = _heartbeat(data, NINE)
    _run(data)
    client = TestClient(_app(data))
    response = client.get("/status")
    body = response.json()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert body["status"] == "ok"
    assert body["worker"]["alive"] is True
    assert body["worker"]["last_heartbeat"] == recorded
    assert body["last_edition"]["awaiting_approval"] is True
    assert body["checks"]["printer"]["state"] == "idle"
    head = client.head("/status")
    assert head.status_code == 200
    assert head.headers["cache-control"] == "no-store"
    assert head.headers["content-type"].startswith("application/json")
    assert head.content == b""


def test_stale_heartbeat_is_down(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE, age=121)
    _run(data)
    response = TestClient(_app(data)).get("/status")
    assert response.status_code == 503
    assert response.json()["status"] == "down"
    assert response.json()["worker"]["alive"] is False


def test_printer_problem_is_degraded_and_strict_is_503(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE, printer="unknown")
    _run(data)
    client = TestClient(_app(data))
    plain = client.get("/status")
    assert plain.status_code == 200
    assert plain.json()["status"] == "degraded"
    assert plain.json()["checks"]["printer"]["state"] == "problem"
    strict = client.get("/status?strict=1")
    assert strict.status_code == 503


def test_empty_printer_stays_ok(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE, printer="")
    _run(data)
    body = TestClient(_app(data)).get("/status").json()
    assert body["status"] == "ok"
    assert body["checks"]["printer"]["status"] == "unknown"


def test_deadline_disk_and_clock(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, TEN)
    missed = TestClient(_app(data, clock=lambda: TEN)).get("/status")
    assert missed.status_code == 503
    _run(data)
    held = TestClient(_app(data, clock=lambda: TEN)).get("/status")
    assert held.status_code == 200
    _heartbeat(data, NINE, disk=99)
    low = TestClient(_app(data)).get("/status")
    assert low.status_code == 503
    _heartbeat(data, NINE, disk=500, ntp=0)
    late = TestClient(_app(data, uptime_seconds=3601)).get("/status")
    assert late.status_code == 503
    assert late.json()["system"]["ntp_synced"] is False


def test_unreadable_database_hides_the_path(tmp_path):
    data = _prepare(tmp_path)
    client = TestClient(_app(data))
    db = data / "newspaper.db"
    db.unlink()
    for suffix in ("-wal", "-shm"):
        extra = Path_extra(data, suffix)
        if extra.exists():
            extra.unlink()
    db.mkdir()
    response = client.get("/status")
    assert response.status_code == 503
    assert response.json()["status"] == "down"
    assert str(data) not in response.text
    assert "SELECT" not in response.text


def Path_extra(data, suffix):
    return data / f"newspaper.db{suffix}"


def _token(data, *, enabled, token):
    conn = connect(data / "newspaper.db")
    try:
        body = load_settings(conn)
        body["status_token_enabled"] = enabled
        save_settings(conn, body)
    finally:
        conn.close()
    set_secret(data / "secrets.env", "STATUS_BEARER_TOKEN", token)


def test_status_stays_open_when_the_token_switch_is_off(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE)
    _run(data)
    _token(data, enabled=False, token="quiet-token")
    response = TestClient(_app(data)).get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    head = TestClient(_app(data)).head("/status")
    assert head.status_code == 200
    assert head.content == b""


def test_status_requires_the_bearer_when_the_switch_is_on(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE)
    _run(data)
    _token(data, enabled=True, token="quiet-token")
    client = TestClient(_app(data))
    missing = client.get("/status")
    assert missing.status_code == 401
    assert missing.content == b""
    wrong = client.get("/status", headers={"authorization": "Bearer other-token"})
    assert wrong.status_code == 401
    assert wrong.content == b""
    head = client.head("/status", headers={"authorization": "Bearer quiet-token"})
    assert head.status_code == 200
    assert head.content == b""
    allowed = client.get("/status", headers={"authorization": "Bearer quiet-token"})
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "ok"
    assert "quiet-token" not in allowed.text


def test_enabled_token_with_an_empty_secret_is_401(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE)
    _run(data)
    _token(data, enabled=True, token="")
    response = TestClient(_app(data)).get("/status", headers={"authorization": "Bearer "})
    assert response.status_code == 401
    assert response.content == b""


def test_status_flood_from_one_address_returns_429(tmp_path):
    data = _prepare(tmp_path)
    _heartbeat(data, NINE)
    _run(data)
    app = _app(data)
    client = TestClient(app)
    for _ in range(60):
        assert client.get("/status").status_code == 200
    blocked = client.get("/status")
    assert blocked.status_code == 429
    assert blocked.content == b""
    allowed = TestClient(app).get("/status", headers={"x-forwarded-for": "192.168.1.41"})
    assert allowed.status_code == 200


def test_status_omits_private_text(tmp_path):
    data = _prepare(tmp_path)
    conn = connect(data / "newspaper.db")
    try:
        body = json.loads(conn.execute("SELECT body FROM settings").fetchone()["body"])
        body["nickname"] = "NICK-SECRET"
        conn.execute(
            "UPDATE settings SET body = ? WHERE version = (SELECT MAX(version) FROM settings)",
            (json.dumps(body),),
        )
        conn.commit()
    finally:
        conn.close()
    _heartbeat(data, NINE)
    directory = _run(
        data,
        sources={"caldav": "ok", "feeds": {"https://secret.example/rss": "failed", "Telex": "ok"}},
    )
    (directory / "edition.json").write_text(
        json.dumps({"today": [{"title": "CALENDAR-TITLE-SECRET"}]}),
        encoding="utf-8",
    )
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO alerts (created_at, kind, level, message, edition_date)
            VALUES (?, 'printer', 'error', 'ALERT-MESSAGE-SECRET', ?)
            """,
            ("2026-10-14T06:30:00+02:00", DAY),
        )
        conn.commit()
    finally:
        conn.close()
    text = TestClient(_app(data)).get("/status").text
    assert "https://secret.example/rss" not in text
    assert "CALENDAR-TITLE-SECRET" not in text
    assert "ALERT-MESSAGE-SECRET" not in text
    assert "NICK-SECRET" not in text
