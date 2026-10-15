import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from newspaper.db import connect, init_data, read_secrets, save_settings, load_settings
from newspaper.web import create_app, hash_password, serve, verify_password

ZONE = ZoneInfo("Europe/Budapest")
NINE = datetime(2026, 10, 14, 9, 0, tzinfo=ZONE)
DAY = "2026-10-14"
PASSWORD = "secret"


def _prepare(tmp_path):
    data = tmp_path / "data"
    init_data(data)
    from newspaper.web import _write_secret

    _write_secret(data / "secrets.env", "ADMIN_PASSWORD_HASH", hash_password(PASSWORD))
    _write_secret(data / "secrets.env", "SESSION_SECRET", "test-session-secret")
    return data


def _app(data):
    return create_app(data, cache_seconds=0, clock=lambda: NINE, uptime_seconds=100, cpu_temp_c=48.2)


def _hold(data):
    directory = data / "editions" / DAY
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "print.pdf").write_bytes(b"%PDF-print")
    (directory / "cloud.pdf").write_bytes(b"%PDF-cloud")
    (directory / "edition.json").write_text('{"today":[{"title":"Standup"}]}\n', encoding="utf-8")
    conn = connect(data / "newspaper.db")
    try:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                edition_date, started_at, finished_at, status, printed, uploaded,
                cups_job_id, upload_attempts, delivery, timing, sources, model, trims, directory
            ) VALUES (?, ?, NULL, 'awaiting_approval', 0, 0, NULL, 0, 'held', '{}', ?, NULL, '[]', ?)
            """,
            (DAY, "2026-10-14T06:30:00+02:00", json.dumps({"caldav": "ok"}), str(directory)),
        )
        conn.execute(
            """
            INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
            VALUES (?, ?, 'hold', 'pending', ?, ?)
            """,
            (cursor.lastrowid, DAY, "2026-10-14T06:30:00+02:00", "2026-10-14T06:30:00+02:00"),
        )
        conn.commit()
    finally:
        conn.close()


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _login(data, password=PASSWORD):
    client = TestClient(_app(data))
    token = _csrf(client.get("/login").text)
    response = client.post("/login", data={"password": password, "csrf": token}, follow_redirects=False)
    assert response.status_code == 303
    return client


def _jobs(data, kind):
    conn = connect(data / "newspaper.db")
    try:
        return conn.execute("SELECT status FROM jobs WHERE kind = ?", (kind,)).fetchall()
    finally:
        conn.close()


def test_existing_hash_asks_for_the_password_only(tmp_path, capsys):
    data = _prepare(tmp_path)
    client = TestClient(_app(data))
    page = client.get("/login")
    assert 'name="password"' in page.text
    assert 'name="setup_code"' not in page.text
    assert "setup code:" not in capsys.readouterr().out


def test_setup_code_is_printed_once_and_a_wrong_code_leaves_the_hash_empty(tmp_path, capsys):
    data = tmp_path / "data"
    init_data(data)
    app = _app(data)
    printed = capsys.readouterr().out
    code = printed.split("setup code:", 1)[1].strip().splitlines()[0].strip()
    client = TestClient(app)
    page = client.get("/login")
    assert 'name="setup_code"' in page.text
    assert code not in page.text
    bad = client.post(
        "/login",
        data={"setup_code": "nope", "password": "new-secret", "csrf": _csrf(page.text)},
        follow_redirects=False,
    )
    assert bad.status_code == 200
    assert "That setup code does not match." in bad.text
    assert read_secrets(data / "secrets.env").get("ADMIN_PASSWORD_HASH") == ""
    claimed = client.post(
        "/login",
        data={"setup_code": code, "password": "new-secret", "csrf": _csrf(bad.text)},
        follow_redirects=False,
    )
    assert claimed.status_code == 303
    assert verify_password("new-secret", read_secrets(data / "secrets.env")["ADMIN_PASSWORD_HASH"])
    _app(data)
    assert "setup code:" not in capsys.readouterr().out
    later = TestClient(_app(data)).get("/login")
    assert 'name="setup_code"' not in later.text
    assert 'name="password"' in later.text


def test_login_failures_from_one_address_return_429(tmp_path):
    data = _prepare(tmp_path)
    app = _app(data)
    client = TestClient(app)
    for _ in range(5):
        token = _csrf(client.get("/login").text)
        failed = client.post("/login", data={"password": "nope", "csrf": token}, follow_redirects=False)
        assert failed.status_code == 200
    blocked = client.post(
        "/login",
        data={"password": PASSWORD, "csrf": _csrf(client.get("/login").text)},
        follow_redirects=False,
    )
    assert blocked.status_code == 429
    assert blocked.content == b""
    other = TestClient(app)
    page = other.get("/login", headers={"x-forwarded-for": "192.168.1.40"})
    allowed = other.post(
        "/login",
        data={"password": PASSWORD, "csrf": _csrf(page.text)},
        headers={"x-forwarded-for": "192.168.1.40"},
        follow_redirects=False,
    )
    assert allowed.status_code == 303
    restarted = TestClient(_app(data))
    retry = restarted.post(
        "/login",
        data={"password": "nope", "csrf": _csrf(restarted.get("/login").text)},
        follow_redirects=False,
    )
    assert retry.status_code == 200


def test_a_successful_login_does_not_consume_a_failure_slot(tmp_path):
    data = _prepare(tmp_path)
    client = TestClient(_app(data))
    for _ in range(4):
        failed = client.post(
            "/login",
            data={"password": "nope", "csrf": _csrf(client.get("/login").text)},
            follow_redirects=False,
        )
        assert failed.status_code == 200
    signed = client.post(
        "/login",
        data={"password": PASSWORD, "csrf": _csrf(client.get("/login").text)},
        follow_redirects=False,
    )
    assert signed.status_code == 303
    again = client.post(
        "/login",
        data={"password": "nope", "csrf": _csrf(client.get("/login").text)},
        follow_redirects=False,
    )
    assert again.status_code == 200


def test_overlapping_login_failures_share_one_cap(tmp_path):
    data = _prepare(tmp_path)
    app = _app(data)
    client = TestClient(app)
    page = client.get("/login")
    token = _csrf(page.text)
    cookie = client.cookies.get("ynt_csrf")

    async def attempt():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            http.cookies.set("ynt_csrf", cookie)
            response = await http.post("/login", data={"password": "nope", "csrf": token})
            return response.status_code

    async def main():
        return await asyncio.gather(*(attempt() for _ in range(8)))

    codes = asyncio.run(main())
    assert codes.count(200) == 5
    assert codes.count(429) == 3


def test_https_forwarding_marks_the_cookie_secure(tmp_path):
    data = _prepare(tmp_path)
    plain = TestClient(_app(data)).get("/login")
    assert "secure" not in plain.headers["set-cookie"].lower()
    client = TestClient(_app(data), base_url="https://newspaper.local")
    secure = client.get("/login", headers={"x-forwarded-proto": "https"})
    assert "secure" in secure.headers["set-cookie"].lower()
    signed = client.post(
        "/login",
        data={"password": PASSWORD, "csrf": _csrf(secure.text)},
        headers={"x-forwarded-proto": "https"},
        follow_redirects=False,
    )
    assert signed.status_code == 303
    assert "secure" in signed.headers["set-cookie"].lower()


def test_wrong_password_stays_on_the_form(tmp_path):
    data = _prepare(tmp_path)
    client = TestClient(_app(data))
    token = _csrf(client.get("/login").text)
    response = client.post("/login", data={"password": "nope", "csrf": token}, follow_redirects=False)
    assert response.status_code == 200
    assert "That password does not match." in response.text
    home = client.get("/", follow_redirects=False)
    assert home.headers["location"] == "/login"


def test_approve_updates_the_banner(tmp_path):
    data = _prepare(tmp_path)
    _hold(data)
    client = _login(data)
    home = client.get("/")
    assert 'id="run-status">awaiting_approval' in home.text
    assert 'hx-get="/banner"' in home.text
    assert "Run now" in home.text
    assert f'name="edition_date" value="{DAY}"' in home.text
    approved = client.post(
        "/actions/approve",
        data={"csrf": _csrf(home.text), "edition_date": DAY},
        follow_redirects=False,
    )
    assert approved.status_code == 303
    assert _jobs(data, "hold")[0]["status"] == "approved"
    conn = connect(data / "newspaper.db")
    try:
        conn.execute("UPDATE runs SET status = 'delivering'")
        conn.commit()
    finally:
        conn.close()
    assert 'id="run-status">delivering' in client.get("/banner").text


def test_second_click_inserts_one_pending_job(tmp_path):
    data = _prepare(tmp_path)
    _hold(data)
    client = _login(data)
    home = client.get("/")
    csrf = _csrf(home.text)
    for kind, path in (
        ("reject", "/actions/reject"),
        ("regenerate", "/actions/regenerate"),
        ("run_now", "/actions/run-now"),
        ("preview", "/actions/preview"),
        ("reprint", "/actions/reprint"),
        ("reupload", "/actions/reupload"),
    ):
        payload = {"csrf": csrf, "edition_date": DAY}
        assert client.post(path, data=payload, follow_redirects=False).status_code == 303
        assert client.post(path, data=payload, follow_redirects=False).status_code == 303
        assert len(_jobs(data, kind)) == 1


def test_pdf_requires_login(tmp_path):
    data = _prepare(tmp_path)
    _hold(data)
    anon = TestClient(_app(data))
    logged_out = anon.get(f"/editions/{DAY}/print.pdf", follow_redirects=False)
    assert logged_out.status_code == 303
    assert logged_out.headers["location"] == "/login"
    client = _login(data)
    printed = client.get(f"/editions/{DAY}/print.pdf")
    assert printed.content == b"%PDF-print"
    assert client.get("/editions/2020-01-01/cloud.pdf").status_code == 404
    assert "Reprint" in client.get(f"/editions/{DAY}").text
    assert "Standup" in client.get(f"/editions/{DAY}").text


def test_run_now_uses_today_when_the_latest_edition_is_older(tmp_path):
    data = _prepare(tmp_path)
    _hold(data)
    conn = connect(data / "newspaper.db")
    try:
        conn.execute("UPDATE runs SET edition_date = '2026-10-13'")
        conn.execute("UPDATE jobs SET edition_date = '2026-10-13'")
        conn.commit()
    finally:
        conn.close()
    client = _login(data)
    home = client.get("/")
    assert 'action="/actions/run-now"' in home.text
    assert 'name="edition_date" value="2026-10-14"' in home.text
    assert "Regenerate" in home.text


def test_serve_binds_localhost(tmp_path):
    data = _prepare(tmp_path)
    seen = {}

    def run(app, host, port):
        seen["host"] = host
        seen["port"] = port

    serve(data, run=run)
    assert seen == {"host": "127.0.0.1", "port": 8080}


def test_posts_do_not_call_a_shell(tmp_path, monkeypatch):
    data = _prepare(tmp_path)
    _hold(data)

    def boom(*args, **kwargs):
        raise AssertionError(args)

    monkeypatch.setattr("subprocess.run", boom)
    client = _login(data)
    denied = client.post("/actions/approve", data={"edition_date": DAY}, follow_redirects=False)
    assert denied.status_code == 403
    assert _jobs(data, "hold")[0]["status"] == "pending"
