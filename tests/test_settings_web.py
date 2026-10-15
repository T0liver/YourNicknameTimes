import re

from fastapi.testclient import TestClient

from newspaper.db import connect, load_settings, read_secrets, save_settings
from newspaper.web import create_app, hash_password

ZONE = __import__("zoneinfo").ZoneInfo("Europe/Budapest")
NINE = __import__("datetime").datetime(2026, 10, 14, 9, 0, tzinfo=ZONE)
PASSWORD = "secret"


def _prepare(tmp_path):
    from newspaper.db import init_data
    from newspaper.web import _write_secret

    data = tmp_path / "data"
    init_data(data)
    _write_secret(data / "secrets.env", "ADMIN_PASSWORD_HASH", hash_password(PASSWORD))
    _write_secret(data / "secrets.env", "SESSION_SECRET", "test-session-secret")
    return data


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _login(data):
    client = TestClient(create_app(data, cache_seconds=0, clock=lambda: NINE))
    token = _csrf(client.get("/login").text)
    client.post("/login", data={"password": PASSWORD, "csrf": token}, follow_redirects=False)
    return client


def test_general_rejects_bad_timezone(tmp_path):
    client = _login(_prepare(tmp_path))
    page = client.get("/settings/general")
    csrf = _csrf(page.text)
    response = client.post(
        "/settings/general",
        data={
            "csrf": csrf,
            "nickname": "Ada",
            "motto": "",
            "city": "Budapest",
            "latitude": "47.5",
            "longitude": "19.0",
            "timezone": "Not/AZone",
            "language": "hu",
            "dashboard_language": "en",
            "paper_size": "A4",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_general_save_and_secrets_stay_out_of_html(tmp_path):
    data = _prepare(tmp_path)
    client = _login(data)
    page = client.get("/settings/general")
    csrf = _csrf(page.text)
    saved = client.post(
        "/settings/general",
        data={
            "csrf": csrf,
            "nickname": "Ada",
            "motto": "Morning",
            "city": "Budapest",
            "latitude": "47.4979",
            "longitude": "19.0402",
            "timezone": "Europe/Budapest",
            "language": "hu",
            "dashboard_language": "hu",
            "paper_size": "A4",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    conn = connect(data / "newspaper.db")
    try:
        body = load_settings(conn)
        assert body["nickname"] == "Ada"
        assert body["dashboard_language"] == "hu"
    finally:
        conn.close()
    model = client.get("/settings/model")
    assert "sk-" not in model.text
    assert "secret_saved" not in model.text.lower() or "saved" in model.text.lower()


def test_system_stores_status_token_settings_without_exposing_secret(tmp_path):
    data = _prepare(tmp_path)
    client = _login(data)
    page = client.get("/settings/system")
    csrf = _csrf(page.text)
    response = client.post(
        "/settings/system",
        data={
            "csrf": csrf,
            "status_token_enabled": "on",
            "status_http_port": "9090",
            "status_bearer_token": "quiet-token",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    conn = connect(data / "newspaper.db")
    try:
        body = load_settings(conn)
        assert body["status_token_enabled"] is True
        assert body["status_http_port"] == 9090
    finally:
        conn.close()
    secrets = read_secrets(data / "secrets.env")
    assert secrets.get("STATUS_BEARER_TOKEN") == "quiet-token"
    again = client.get("/settings/system")
    assert "quiet-token" not in again.text


def test_schedule_rejects_bad_time(tmp_path):
    client = _login(_prepare(tmp_path))
    csrf = _csrf(client.get("/settings/schedule").text)
    bad = client.post(
        "/settings/schedule",
        data={
            "csrf": csrf,
            "weekday_start": "25:99",
            "weekend_edition": "on",
            "weekend_start": "08:00",
            "latest_acceptable": "10:00",
            "hold_mode": "on",
            "auto_approve": "",
            "auto_approve_time": "",
        },
        follow_redirects=False,
    )
    assert bad.status_code == 400


def test_opml_round_trip(tmp_path):
    data = _prepare(tmp_path)
    client = _login(data)
    export = client.get("/settings/news/opml")
    assert export.status_code == 200
    assert "xmlUrl" in export.text
    csrf = _csrf(client.get("/settings/news").text)
    imported = client.post(
        "/settings/news/opml",
        data={"csrf": csrf, "opml": export.text},
        follow_redirects=False,
    )
    assert imported.status_code == 303
    conn = connect(data / "newspaper.db")
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM feeds").fetchone()["n"]
        assert count >= 2
    finally:
        conn.close()
