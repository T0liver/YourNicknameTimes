"""Localhost dashboard and /status. This process does not print."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets as pysecrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from newspaper.dashboard_settings import checklist, mount as mount_settings
from newspaper.db import connect, init_data, load_settings, read_secrets
from newspaper.status_report import build_report, status_http_code

HOST = "127.0.0.1"
PORT = 8080
ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates" / "dashboard"))
CACHE_SECONDS = 3.0


def hash_password(password: str) -> str:
    salt = pysecrets.token_hex(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    _, n, r, p, salt, digest = parts
    try:
        got = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


def ensure_admin(path: Path) -> None:
    found = read_secrets(path)
    if not found.get("ADMIN_PASSWORD_HASH"):
        password = pysecrets.token_urlsafe(12)
        _write_secret(path, "ADMIN_PASSWORD_HASH", hash_password(password))
        print(f"admin password: {password}", flush=True)
    if not found.get("SESSION_SECRET"):
        _write_secret(path, "SESSION_SECRET", pysecrets.token_hex(32))


def _write_secret(path: Path, name: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    updated = []
    for line in lines:
        if line.startswith(f"{name}="):
            updated.append(f"{name}={value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{name}={value}")
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    path.chmod(0o600)


def create_app(data_dir: Path, *, clock=None, cache_seconds: float = CACHE_SECONDS, uptime_seconds=None, cpu_temp_c=None) -> FastAPI:
    data_dir = Path(data_dir)
    init_data(data_dir)
    ensure_admin(data_dir / "secrets.env")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.data_dir = data_dir
    app.state.clock = clock
    app.state.cache_seconds = cache_seconds
    app.state.cache = None
    app.state.uptime_seconds = uptime_seconds
    app.state.cpu_temp_c = cpu_temp_c
    app.state.session_secret = read_secrets(data_dir / "secrets.env").get("SESSION_SECRET", "")
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    _routes(app)
    mount_settings(
        app,
        session=_session,
        csrf_check=lambda sess, token: hmac.compare_digest(str(sess.get("csrf") or ""), str(token or "")),
        form=_form,
        db=_db,
        now=_now,
    )
    return app


def serve(data_dir: Path, *, run=None) -> None:
    app = create_app(data_dir)
    runner = run or _uvicorn
    runner(app, HOST, PORT)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the dashboard and /status on localhost.")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)
    serve(Path(args.data_dir))


def _uvicorn(app, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def _routes(app: FastAPI) -> None:
    @app.get("/login")
    def login_form(request: Request):
        token = pysecrets.token_urlsafe(32)
        response = TEMPLATES.TemplateResponse(request, "login.html", {"csrf": token, "error": ""})
        _csrf_cookie(response, request, token)
        return response

    @app.post("/login")
    async def login_submit(request: Request):
        form = await _form(request)
        if not hmac.compare_digest(form.get("csrf", ""), _csrf_cookie_value(request)):
            return HTMLResponse("Forbidden", status_code=403)
        stored = read_secrets(request.app.state.data_dir / "secrets.env").get("ADMIN_PASSWORD_HASH", "")
        if not verify_password(form.get("password", ""), stored):
            token = pysecrets.token_urlsafe(32)
            response = TEMPLATES.TemplateResponse(
                request, "login.html", {"csrf": token, "error": "That password does not match."}
            )
            _csrf_cookie(response, request, token)
            return response
        token = pysecrets.token_urlsafe(32)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("ynt", _sign(request.app.state.session_secret, {"csrf": token}), httponly=True, samesite="lax")
        return response

    @app.get("/")
    def home(request: Request):
        session = _session(request)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        return TEMPLATES.TemplateResponse(request, "home.html", _home_context(request, session))

    @app.get("/banner")
    def banner(request: Request):
        session = _session(request)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        with _db(request) as conn:
            context = _banner(conn, _now(request), session)
        return TEMPLATES.TemplateResponse(request, "banner.html", context)

    @app.get("/editions/{edition_date}")
    def edition_page(request: Request, edition_date: str):
        session = _session(request)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        return TEMPLATES.TemplateResponse(request, "edition.html", _edition_context(request, session, edition_date))

    @app.post("/actions/{kind}")
    async def action(request: Request, kind: str):
        session = _session(request)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        form = await _form(request)
        if not hmac.compare_digest(form.get("csrf", ""), str(session.get("csrf") or "")):
            return HTMLResponse("Forbidden", status_code=403)
        moment = _now(request)
        day = form.get("edition_date") or moment.date().isoformat()
        with _db(request) as conn:
            if kind == "approve":
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    UPDATE jobs SET status = 'approved', updated_at = ?
                    WHERE kind = 'hold' AND status = 'pending' AND edition_date = ?
                    """,
                    (moment.isoformat(timespec="seconds"), day),
                )
                conn.commit()
            else:
                job_kind = {"run-now": "run_now"}.get(kind, kind)
                _insert_pending(conn, job_kind, day, moment.isoformat(timespec="seconds"))
        return RedirectResponse(form.get("next") or "/", status_code=303)

    @app.get("/editions/{edition_date}/{name}")
    def download(request: Request, edition_date: str, name: str):
        if _session(request) is None:
            return RedirectResponse("/login", status_code=303)
        path = _safe_file(request.app.state.data_dir, edition_date, name)
        if path is None:
            return HTMLResponse("Not found", status_code=404)
        return FileResponse(path)

    @app.get("/editions/{edition_date}/llm/{name}")
    def download_llm(request: Request, edition_date: str, name: str):
        if _session(request) is None:
            return RedirectResponse("/login", status_code=303)
        path = _safe_file(request.app.state.data_dir, edition_date, "llm", name)
        if path is None:
            return HTMLResponse("Not found", status_code=404)
        return FileResponse(path)

    @app.api_route("/status", methods=["GET", "HEAD"])
    def status(request: Request):
        body, state = _status_body(request)
        code = status_http_code(state, strict=request.query_params.get("strict") == "1")
        headers = {"Cache-Control": "no-store"}
        if request.method == "HEAD":
            return Response(status_code=code, headers=headers, media_type="application/json")
        return JSONResponse(body, status_code=code, headers=headers)


def _insert_pending(conn, kind: str, edition_date: str, stamp: str) -> None:
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute(
        """
        SELECT 1 FROM jobs
        WHERE kind = ? AND edition_date = ? AND status = 'pending'
        """,
        (kind, edition_date),
    ).fetchone()
    if existing:
        conn.commit()
        return
    run = conn.execute(
        "SELECT id FROM runs WHERE edition_date = ? ORDER BY id DESC LIMIT 1",
        (edition_date,),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
        VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (None if run is None else run["id"], edition_date, kind, stamp, stamp),
    )
    conn.commit()


def _status_body(request: Request) -> tuple[dict, str]:
    request.app.state.last_status_at = _now(request).isoformat(timespec="seconds")
    now = _now(request)
    cached = request.app.state.cache
    ttl = float(request.app.state.cache_seconds or 0)
    if cached and ttl > 0 and (now - cached[0]).total_seconds() < ttl:
        return cached[1], cached[2]
    version = _version()
    uptime = request.app.state.uptime_seconds
    if uptime is None:
        uptime = _read_uptime()
    temp = request.app.state.cpu_temp_c
    if request.app.state.cpu_temp_c is None:
        temp = _read_temp()
    try:
        conn = connect(request.app.state.data_dir / "newspaper.db")
    except Exception:
        conn = None
    try:
        body, state = build_report(
            conn, now=now, uptime_seconds=float(uptime or 0), cpu_temp_c=temp, version=version
        )
    finally:
        if conn is not None:
            conn.close()
    request.app.state.cache = (now, body, state)
    return body, state


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("newspaper")
    except Exception:
        return "0.1.0"


def _read_uptime() -> float:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except OSError:
        return 0.0


def _read_temp() -> float | None:
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(path.read_text(encoding="utf-8").strip()) / 1000
    except (OSError, ValueError):
        return None


def _home_context(request: Request, session: dict) -> dict:
    with _db(request) as conn:
        settings = load_settings(conn)
        moment = _now(request)
        banner = _banner(conn, moment, session)
        editions = _editions(conn, request.app.state.data_dir, settings, moment)
    labels = _labels(settings)
    return {
        "banner": banner,
        "editions": editions,
        "today": moment.date().isoformat(),
        "wifi": "unknown",
        "status_url": f"http://{HOST}:{PORT}/status",
        "last_status": getattr(request.app.state, "last_status_at", None),
        "csrf": session.get("csrf", ""),
        "labels": labels,
        "checklist": checklist(settings, request.app.state.data_dir),
        "show_checklist": not all(done for _, done in checklist(settings, request.app.state.data_dir)),
    }


def _labels(settings: dict) -> dict:
    from newspaper.dashboard_settings import TEXT

    lang = str(settings.get("dashboard_language") or "en")
    return TEXT.get(lang, TEXT["en"])


def _edition_context(request: Request, session: dict, edition_date: str) -> dict:
    directory = request.app.state.data_dir / "editions" / edition_date
    snapshot = ""
    path = directory / "edition.json"
    if path.is_file():
        snapshot = path.read_text(encoding="utf-8")
    llm = []
    llm_dir = directory / "llm"
    if llm_dir.is_dir():
        llm = sorted(item.name for item in llm_dir.iterdir() if item.is_file())
    run_status = "none"
    with _db(request) as conn:
        row = conn.execute(
            "SELECT status, finished_at, delivery FROM runs WHERE edition_date = ? ORDER BY id DESC LIMIT 1",
            (edition_date,),
        ).fetchone()
    if row is not None:
        run_status = row["status"]
    return {
        "edition_date": edition_date,
        "snapshot": snapshot,
        "llm": llm,
        "run_status": run_status,
        "csrf": session.get("csrf", ""),
    }


def _banner(conn, moment: datetime, session: dict) -> dict:
    run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    day = run["edition_date"] if run else moment.date().isoformat()
    hold = None
    if run is not None:
        hold = conn.execute(
            """
            SELECT 1 FROM jobs
            WHERE edition_date = ? AND kind = 'hold' AND status = 'pending'
            """,
            (day,),
        ).fetchone()
    return {
        "run_status": run["status"] if run else "none",
        "edition_date": day,
        "hold_pending": hold is not None,
        "csrf": session.get("csrf", ""),
    }


def _editions(conn, data_dir: Path, settings, moment: datetime) -> list[str]:
    limit = settings.get("local_retention_days")
    root = Path(data_dir) / "editions"
    if not root.is_dir():
        return []
    found = []
    for child in sorted(root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        try:
            day = datetime.fromisoformat(child.name).date()
        except ValueError:
            continue
        if limit is not None and (moment.date() - day).days > int(limit):
            continue
        found.append(child.name)
    return found


def _safe_file(data_dir: Path, edition_date: str, *parts: str) -> Path | None:
    if len(edition_date) != 10 or not edition_date[4] == "-" or "/" in edition_date:
        return None
    root = (Path(data_dir) / "editions" / edition_date).resolve()
    path = root.joinpath(*parts).resolve()
    if root not in path.parents and path != root:
        return None
    if not path.is_file():
        return None
    return path


def _now(request: Request) -> datetime:
    zone = ZoneInfo("Europe/Budapest")
    try:
        with _db(request) as conn:
            zone = ZoneInfo(load_settings(conn).get("timezone") or "Europe/Budapest")
    except Exception:
        zone = ZoneInfo("Europe/Budapest")
    clock = request.app.state.clock
    if clock is not None:
        moment = clock()
        if moment.tzinfo is None:
            return moment.replace(tzinfo=zone)
        return moment.astimezone(zone)
    return datetime.now(zone)


class _DB:
    def __init__(self, request: Request):
        self.request = request
        self.conn = None

    def __enter__(self):
        self.conn = connect(self.request.app.state.data_dir / "newspaper.db")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if self.conn is not None:
            self.conn.close()


def _db(request: Request) -> _DB:
    return _DB(request)


def _session(request: Request) -> dict | None:
    raw = request.cookies.get("ynt")
    if not raw:
        return None
    return _unsign(request.app.state.session_secret, raw)


def _sign(secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{body.hex()}.{sig}"


def _unsign(secret: str, token: str) -> dict | None:
    try:
        body_hex, sig = token.split(".", 1)
        body = bytes.fromhex(body_hex)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    loaded = json.loads(body.decode("utf-8"))
    return loaded if isinstance(loaded, dict) else None


def _csrf_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        "ynt_csrf",
        _sign(request.app.state.session_secret, {"csrf": token}),
        httponly=True,
        samesite="lax",
    )


def _csrf_cookie_value(request: Request) -> str:
    loaded = _unsign(request.app.state.session_secret, request.cookies.get("ynt_csrf", ""))
    if not loaded:
        return ""
    return str(loaded.get("csrf") or "")


async def _form(request: Request) -> dict[str, str]:
    form = await request.form()
    return {str(key): str(value) for key, value in form.items()}
