"""Wake on a timer, build the edition, and deliver it."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from newspaper.db import connect, init_data, load_settings, read_secrets
from newspaper.edition_build import run as build_edition_run
from newspaper.render import render_cloud, render_preview

WAKE_SECONDS = 30
TOKEN_URL = "https://api.dropbox.com/oauth2/token"
DROPBOX_API = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT = "https://content.dropboxapi.com/2"


class UploadError(RuntimeError):
    """Dropbox refused the refresh or the upload."""


class PrintError(RuntimeError):
    """CUPS did not accept the job."""


def ntp_argv() -> list[str]:
    return ["timedatectl", "show", "-p", "NTPSynchronized", "--value"]


def query_ntp(run=None) -> bool:
    runner = run or subprocess.run
    result = runner(ntp_argv(), capture_output=True, text=True, check=False)
    return (result.stdout or "").strip().casefold() == "yes"


def lp_argv(printer: str, pdf: Path, duplex: bool) -> list[str]:
    sides = "two-sided-long-edge" if duplex else "one-sided"
    return [
        "lp",
        "-d",
        printer,
        "-o",
        "media=A4",
        "-o",
        "ColorModel=Gray",
        "-o",
        "print-scaling=none",
        "-o",
        f"sides={sides}",
        str(pdf),
    ]


class SystemCups:
    def __init__(self, run=None):
        self._run = run or subprocess.run

    def printer_state(self, name: str) -> str:
        if not str(name or "").strip():
            return ""
        result = self._run(["lpstat", "-p", name], capture_output=True, text=True, check=False)
        lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
        return lines[0] if lines else "unknown"

    def submit(self, argv: list[str]) -> str:
        result = self._run(argv, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "lp failed").strip()
            raise PrintError(detail)
        marker = "request id is "
        text = result.stdout or ""
        if marker not in text:
            raise PrintError(text.strip() or "lp returned no job id")
        return text.split(marker, 1)[1].split()[0]

    def job_visible(self, job_id: str) -> bool:
        completed = self._stdout(["lpstat", "-W", "completed", "-o", job_id])
        active = self._stdout(["lpstat", "-W", "not-completed", "-o", job_id])
        return job_id in completed or job_id in active

    def job_state(self, job_id: str) -> str:
        detailed = self._stdout(["lpstat", "-W", "all", "-l", "-o", job_id])
        lowered = detailed.casefold()
        if "abort" in lowered:
            return "aborted"
        if "cancel" in lowered:
            return "canceled"
        completed = self._stdout(["lpstat", "-W", "completed", "-o", job_id])
        if job_id in completed:
            return "completed"
        return "processing"

    def _stdout(self, argv: list[str]) -> str:
        result = self._run(argv, capture_output=True, text=True, check=False)
        return result.stdout or ""


class DropboxUploader:
    def __init__(self, post=None):
        self._post = post or requests.post

    def upload(self, secrets: dict, pdf: Path, edition_date: str) -> None:
        refresh = str(secrets.get("DROPBOX_REFRESH_TOKEN") or "").strip()
        app_key = str(secrets.get("DROPBOX_APP_KEY") or "").strip()
        app_secret = str(secrets.get("DROPBOX_APP_SECRET") or "").strip()
        if not (refresh and app_key and app_secret):
            raise UploadError("missing dropbox token")
        token = self._refresh(refresh, app_key, app_secret)
        self._folder(token)
        payload = Path(pdf).read_bytes()
        self._put(token, f"/editions/{edition_date}.pdf", payload)
        self._put(token, "/latest.pdf", payload)

    def _refresh(self, refresh: str, app_key: str, app_secret: str) -> str:
        response = self._post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": app_key,
                "client_secret": app_secret,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise UploadError(f"token refresh HTTP {response.status_code}")
        body = response.json()
        token = body.get("access_token") if isinstance(body, dict) else None
        if not token:
            raise UploadError("token refresh returned no access token")
        return token

    def _folder(self, token: str) -> None:
        self._post(
            f"{DROPBOX_API}/files/create_folder_v2",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps({"path": "/editions", "autorename": False}),
            timeout=30,
        )

    def _put(self, token: str, path: str, payload: bytes) -> None:
        response = self._post(
            f"{DROPBOX_CONTENT}/files/upload",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(
                    {"path": path, "mode": "overwrite", "autorename": False, "mute": True}
                ),
            },
            data=payload,
            timeout=60,
        )
        if response.status_code != 200:
            raise UploadError(f"upload HTTP {response.status_code}")


def render_copies(edition_dir: Path, level: str) -> None:
    loaded = json.loads((edition_dir / "edition.json").read_text(encoding="utf-8"))
    render_cloud(edition_dir / "cloud.pdf", loaded, level=level)
    render_preview(edition_dir / "preview.png", loaded)


def cycle(
    data_dir: Path,
    *,
    now: datetime | None = None,
    ntp_synced: bool | None = None,
    build=None,
    cups=None,
    dropbox=None,
    copies=None,
) -> None:
    data_dir = Path(data_dir)
    builder = build or build_edition_run
    printer = cups or SystemCups()
    uploader = dropbox or DropboxUploader()
    copy_fn = copies or render_copies
    box = [init_data(data_dir)]
    try:
        settings = load_settings(box[0])
        zone = ZoneInfo(settings.get("timezone") or "Europe/Budapest")
        moment = _as_local(now, zone)
        synced = query_ntp() if ntp_synced is None else bool(ntp_synced)
        day = moment.date()
        stamp = moment.isoformat(timespec="seconds")
        _heartbeat(box[0], stamp, synced, printer, settings, data_dir)
        _prune_local(data_dir, settings, day)
        if synced and _past_deadline(settings, moment) and not _edition_exists(box[0], day):
            _alert(
                box[0],
                "deadline",
                "info",
                "The edition missed the latest acceptable time.",
                day.isoformat(),
                stamp,
            )
        _reject_pending(box[0], stamp)
        built = _run_regenerate(box, data_dir, settings, moment, builder, copy_fn, stamp)
        if not built and synced:
            built = _run_dated_job(
                box, data_dir, settings, moment, builder, copy_fn, stamp, "run_now", deliver=True
            )
        if synced:
            _run_dated_job(
                box, data_dir, settings, moment, builder, copy_fn, stamp, "preview", deliver=False
            )
        if not built and _should_build(box[0], settings, moment, synced):
            code, elapsed = _invoke_build(box, data_dir, builder, moment)
            _after_build(box[0], data_dir, settings, moment, code, elapsed, copy_fn, stamp)
        _auto_approve(box[0], settings, moment, stamp)
        _deliver_ready(box[0], data_dir, settings, printer, uploader, copy_fn, stamp)
        _reprint(box[0], data_dir, settings, printer, stamp)
        _reupload(box[0], data_dir, uploader, stamp)
        _approval_alerts(box[0], moment, stamp)
    finally:
        box[0].close()


def serve(data_dir: Path, *, sleep=time.sleep, once: bool = False) -> None:
    while True:
        try:
            cycle(Path(data_dir))
        except Exception:
            traceback.print_exc()
        if once:
            return
        sleep(WAKE_SECONDS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Wake every 30 seconds and deliver the edition.")
    parser.add_argument("--data-dir", default="data", help="Directory for the database and editions")
    args = parser.parse_args(argv)
    serve(Path(args.data_dir))


def _invoke_build(box: list, data_dir: Path, builder, moment: datetime) -> tuple[int, float]:
    box[0].close()
    started = time.perf_counter()
    try:
        code = builder(data_dir, now=moment)
        return code, round(time.perf_counter() - started, 3)
    finally:
        box[0] = connect(data_dir / "newspaper.db")


def _run_regenerate(box, data_dir, settings, moment, builder, copy_fn, stamp: str) -> bool:
    jobs = box[0].execute(
        "SELECT * FROM jobs WHERE kind = 'regenerate' AND status = 'pending' ORDER BY id"
    ).fetchall()
    for job in jobs:
        code, elapsed = _invoke_build(box, data_dir, builder, moment)
        _after_build(box[0], data_dir, settings, moment, code, elapsed, copy_fn, stamp)
        status = "done" if code == 0 else "failed"
        box[0].execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, stamp, job["id"]),
        )
        box[0].commit()
    return bool(jobs)


def _run_dated_job(box, data_dir, settings, moment, builder, copy_fn, stamp, kind, *, deliver: bool) -> bool:
    day = moment.date().isoformat()
    jobs = box[0].execute(
        """
        SELECT * FROM jobs
        WHERE kind = ? AND status = 'pending' AND edition_date = ?
        ORDER BY id
        """,
        (kind, day),
    ).fetchall()
    for job in jobs:
        code, elapsed = _invoke_build(box, data_dir, builder, moment)
        directory = data_dir / "editions" / day
        ok = code == 0
        if deliver:
            _after_build(box[0], data_dir, settings, moment, code, elapsed, copy_fn, stamp)
        else:
            if ok:
                try:
                    copy_fn(directory, settings.get("cloud_level") or "trimmed")
                except Exception as exc:
                    ok = False
                    _alert(box[0], "run_failed", "error", f"A delivery file is missing: {exc}", day, stamp)
            sources, model, trims = _snapshot_meta(directory)
            if _non_failed_run(box[0], day) is None:
                status = "failed"
                if ok:
                    status = "done_degraded" if _source_failed(sources) else "done"
                _insert_finished_run(
                    box[0], day, stamp, status, directory, {"build": elapsed}, sources, model, trims
                )
        _set_job(box[0], job["id"], "done" if ok else "failed", stamp)
    return bool(jobs)


def _non_failed_run(conn, day: str):
    return conn.execute(
        "SELECT 1 FROM runs WHERE edition_date = ? AND status != 'failed'",
        (day,),
    ).fetchone()


def _insert_finished_run(conn, day, stamp, status, directory, timing, sources, model, trims) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            edition_date, started_at, finished_at, status, printed, uploaded,
            cups_job_id, upload_attempts, delivery, timing, sources, model, trims, directory
        ) VALUES (?, ?, ?, ?, 0, 0, NULL, 0, NULL, ?, ?, ?, ?, ?)
        """,
        (
            day,
            stamp,
            stamp,
            status,
            json.dumps(timing),
            json.dumps(sources),
            model,
            json.dumps(trims),
            str(directory),
        ),
    )
    conn.commit()


def _reprint(conn, data_dir, settings, cups, stamp: str) -> None:
    for job in _pending_jobs(conn, "reprint"):
        day = job["edition_date"]
        run = _latest_run(conn, day)
        directory = Path(run["directory"]) if run is not None and run["directory"] else data_dir / "editions" / day
        pdf = directory / "print.pdf"
        marker = directory / "reprint.cups"
        if not str(settings.get("printer_name") or "").strip() or not pdf.is_file():
            _fail_reprint(conn, job["id"], marker, day, stamp, alert=pdf.is_file() is False and bool(str(settings.get("printer_name") or "").strip()))
            continue
        job_id = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        if not job_id:
            try:
                job_id = cups.submit(
                    lp_argv(str(settings.get("printer_name") or ""), pdf, bool(settings.get("duplex", True)))
                )
            except Exception as exc:
                _alert(conn, "printer", "error", f"CUPS rejected the job: {exc}", day, stamp)
                _fail_reprint(conn, job["id"], marker, day, stamp, alert=False)
                continue
            directory.mkdir(parents=True, exist_ok=True)
            marker.write_text(job_id + "\n", encoding="utf-8")
            conn.commit()
        visible = cups.job_visible(job_id) if hasattr(cups, "job_visible") else True
        if not visible:
            _alert(conn, "printer", "error", "CUPS lost the reprint.", day, stamp)
            _fail_reprint(conn, job["id"], marker, day, stamp, alert=False)
            continue
        state = cups.job_state(job_id)
        if state == "completed":
            _finish_reprint(conn, job["id"], marker, stamp, "done")
        elif state in {"canceled", "aborted"}:
            _alert(conn, "printer", "error", f"CUPS {state} the job.", day, stamp)
            _finish_reprint(conn, job["id"], marker, stamp, "failed")


def _fail_reprint(conn, job_id: int, marker: Path, day: str, stamp: str, *, alert: bool) -> None:
    if alert:
        _alert(conn, "printer", "error", "A delivery file is missing.", day, stamp)
    _finish_reprint(conn, job_id, marker, stamp, "failed")


def _finish_reprint(conn, job_id: int, marker: Path, stamp: str, status: str) -> None:
    if marker.is_file():
        marker.unlink()
    _set_job(conn, job_id, status, stamp)


def _reupload(conn, data_dir, dropbox, stamp: str) -> None:
    for job in _pending_jobs(conn, "reupload"):
        day = job["edition_date"]
        run = _latest_run(conn, day)
        directory = Path(run["directory"]) if run is not None and run["directory"] else data_dir / "editions" / day
        pdf = directory / "cloud.pdf"
        if not pdf.is_file():
            _alert(conn, "dropbox", "error", "Dropbox upload failed.", day, stamp)
            _set_job(conn, job["id"], "failed", stamp)
            continue
        try:
            dropbox.upload(read_secrets(data_dir / "secrets.env"), pdf, day)
        except Exception:
            _alert(conn, "dropbox", "error", "Dropbox upload failed.", day, stamp)
            _set_job(conn, job["id"], "failed", stamp)
            continue
        _set_job(conn, job["id"], "done", stamp)


def _pending_jobs(conn, kind: str):
    return conn.execute(
        "SELECT * FROM jobs WHERE kind = ? AND status = 'pending' ORDER BY id",
        (kind,),
    ).fetchall()


def _set_job(conn, job_id: int, status: str, stamp: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
        (status, stamp, job_id),
    )
    conn.commit()


def _after_build(conn, data_dir, settings, moment, code, elapsed, copy_fn, stamp: str) -> None:
    day = moment.date().isoformat()
    directory = data_dir / "editions" / day
    sources, model, trims = _snapshot_meta(directory)
    timing = {"build": elapsed}
    if code != 0:
        _save_run(
            conn,
            day,
            stamp,
            "failed",
            "failed",
            directory,
            timing,
            sources,
            model,
            trims,
            finished=stamp,
        )
        _alert(conn, "run_failed", "error", "The page build failed.", day, stamp)
        return
    try:
        copy_fn(directory, settings.get("cloud_level") or "trimmed")
    except Exception as exc:
        _alert(conn, "run_failed", "error", f"A delivery file is missing: {exc}", day, stamp)
    if _source_failed(sources):
        _alert(
            conn,
            "degraded",
            "info",
            "A source failed and the edition used a fallback.",
            day,
            stamp,
        )
    if settings.get("hold_mode"):
        run_id = _save_run(
            conn,
            day,
            stamp,
            "awaiting_approval",
            "held",
            directory,
            timing,
            sources,
            model,
            trims,
        )
        _insert_hold(conn, run_id, day, stamp)
        return
    _save_run(
        conn,
        day,
        stamp,
        "delivering",
        None,
        directory,
        timing,
        sources,
        model,
        trims,
    )


def _deliver_ready(conn, data_dir, settings, cups, dropbox, copy_fn, stamp: str) -> None:
    runs = conn.execute(
        """
        SELECT * FROM runs
        WHERE status IN ('awaiting_approval', 'delivering')
        ORDER BY id
        """
    ).fetchall()
    for run in runs:
        if _ready(conn, run):
            _deliver_one(conn, data_dir, settings, run, cups, dropbox, copy_fn, stamp)


def _deliver_one(conn, data_dir, settings, run, cups, dropbox, copy_fn, stamp: str) -> None:
    run_id = run["id"]
    day = run["edition_date"]
    directory = Path(run["directory"] or data_dir / "editions" / day)
    conn.execute(
        """
        UPDATE runs SET status = 'delivering'
        WHERE id = ? AND status = 'awaiting_approval'
        """,
        (run_id,),
    )
    conn.commit()
    level = settings.get("cloud_level") or "trimmed"
    if not _ensure_copies(directory, level, copy_fn):
        _alert(conn, "run_failed", "error", "A delivery file is missing.", day, stamp)
        return
    edition_day = date.fromisoformat(day)
    print_on = _wants_print(settings, edition_day)
    upload_on = _switch(settings, edition_day, "upload")
    started = time.perf_counter()
    if print_on and not run["printed"] and run["delivery"] != "print_failed":
        outcome = _print_job(conn, run, directory, settings, cups, stamp)
        run = _run_by_id(conn, run_id)
        if outcome == "wait":
            return
    if upload_on and not run["uploaded"]:
        if not _upload(conn, data_dir, run, directory, dropbox, stamp):
            return
        run = _run_by_id(conn, run_id)
    if run["delivery"] == "print_failed":
        conn.execute(
            """
            UPDATE runs
            SET status = 'failed', delivery = 'print_failed', finished_at = ?
            WHERE id = ?
            """,
            (stamp, run_id),
        )
        conn.commit()
        return
    if print_on and not run["printed"]:
        return
    sources = json.loads(run["sources"] or "{}")
    status = "done_degraded" if _source_failed(sources) else "done"
    if run["printed"]:
        delivery = "printed"
    elif run["uploaded"]:
        delivery = "uploaded"
    else:
        delivery = "skipped"
    timing = json.loads(run["timing"] or "{}")
    timing["deliver"] = round(time.perf_counter() - started, 3)
    conn.execute(
        """
        UPDATE runs
        SET status = ?, delivery = ?, finished_at = ?, timing = ?
        WHERE id = ?
        """,
        (status, delivery, stamp, json.dumps(timing), run_id),
    )
    conn.execute(
        """
        UPDATE jobs SET status = 'done', updated_at = ?
        WHERE run_id = ? AND kind = 'hold' AND status = 'approved'
        """,
        (stamp, run_id),
    )
    conn.commit()


def _print_job(conn, run, directory: Path, settings, cups, stamp: str) -> str:
    job_id = run["cups_job_id"]
    if not job_id:
        argv = lp_argv(
            str(settings.get("printer_name") or ""),
            directory / "print.pdf",
            bool(settings.get("duplex", True)),
        )
        try:
            job_id = cups.submit(argv)
        except Exception as exc:
            _alert(conn, "printer", "error", f"CUPS rejected the job: {exc}", run["edition_date"], stamp)
            conn.execute(
                "UPDATE runs SET status = 'delivering', delivery = 'print_failed' WHERE id = ?",
                (run["id"],),
            )
            conn.commit()
            return "failed"
        conn.execute(
            "UPDATE runs SET cups_job_id = ?, status = 'delivering' WHERE id = ?",
            (job_id, run["id"]),
        )
        conn.commit()
    state = cups.job_state(job_id)
    if state == "completed":
        conn.execute("UPDATE runs SET printed = 1 WHERE id = ?", (run["id"],))
        conn.commit()
        return "done"
    if state in {"canceled", "aborted"}:
        _alert(conn, "printer", "error", f"CUPS {state} the job.", run["edition_date"], stamp)
        conn.execute(
            "UPDATE runs SET delivery = 'print_failed', status = 'delivering' WHERE id = ?",
            (run["id"],),
        )
        conn.commit()
        return "failed"
    conn.execute("UPDATE runs SET status = 'delivering' WHERE id = ?", (run["id"],))
    conn.commit()
    return "wait"


def _upload(conn, data_dir, run, directory: Path, dropbox, stamp: str) -> bool:
    secrets = read_secrets(data_dir / "secrets.env")
    try:
        dropbox.upload(secrets, directory / "cloud.pdf", run["edition_date"])
    except Exception:
        attempts = int(run["upload_attempts"]) + 1
        conn.execute(
            "UPDATE runs SET upload_attempts = ? WHERE id = ?",
            (attempts, run["id"]),
        )
        conn.commit()
        if attempts == 3:
            _alert(conn, "dropbox", "error", "Dropbox upload failed three times.", run["edition_date"], stamp)
        return False
    conn.execute("UPDATE runs SET uploaded = 1 WHERE id = ?", (run["id"],))
    conn.commit()
    return True


def _ensure_copies(directory: Path, level: str, copy_fn) -> bool:
    print_pdf = directory / "print.pdf"
    cloud = directory / "cloud.pdf"
    preview = directory / "preview.png"
    if not print_pdf.is_file():
        return False
    if cloud.is_file() and preview.is_file():
        return True
    try:
        copy_fn(directory, level)
    except Exception:
        return False
    return print_pdf.is_file() and cloud.is_file() and preview.is_file()


def _ready(conn, run) -> bool:
    if run["status"] in {"rejected", "failed", "done", "done_degraded"}:
        return False
    holds = conn.execute(
        """
        SELECT status FROM jobs
        WHERE run_id = ? AND kind = 'hold' AND status IN ('pending', 'approved')
        """,
        (run["id"],),
    ).fetchall()
    statuses = {row["status"] for row in holds}
    if "pending" in statuses:
        return False
    if "approved" in statuses:
        return True
    return run["status"] == "delivering"


def _approval_alerts(conn, moment: datetime, stamp: str) -> None:
    rows = conn.execute(
        "SELECT created_at, edition_date FROM jobs WHERE kind = 'hold' AND status = 'pending'"
    ).fetchall()
    for row in rows:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=moment.tzinfo)
        if moment - created > timedelta(hours=1):
            _alert(
                conn,
                "awaiting_approval",
                "info",
                "The edition has been waiting for approval for more than an hour.",
                row["edition_date"],
                stamp,
            )


def _auto_approve(conn, settings, moment: datetime, stamp: str) -> None:
    if not settings.get("auto_approve"):
        return
    clock = str(settings.get("auto_approve_time") or "")
    if not clock:
        return
    if moment.hour * 60 + moment.minute < _minutes(clock):
        return
    conn.execute(
        """
        UPDATE jobs SET status = 'approved', updated_at = ?
        WHERE kind = 'hold' AND status = 'pending' AND edition_date = ?
        """,
        (stamp, moment.date().isoformat()),
    )
    conn.commit()


def _reject_pending(conn, stamp: str) -> None:
    jobs = conn.execute(
        "SELECT * FROM jobs WHERE kind = 'reject' AND status = 'pending' ORDER BY id"
    ).fetchall()
    for job in jobs:
        day = job["edition_date"]
        run = _latest_run(conn, day)
        if run is not None:
            conn.execute(
                """
                UPDATE runs
                SET status = 'rejected', delivery = 'rejected', finished_at = ?
                WHERE id = ?
                """,
                (stamp, run["id"]),
            )
        conn.execute(
            """
            UPDATE jobs SET status = 'done', updated_at = ?
            WHERE edition_date = ? AND kind = 'hold' AND status != 'done'
            """,
            (stamp, day),
        )
        conn.execute(
            "UPDATE jobs SET status = 'done', updated_at = ? WHERE id = ?",
            (stamp, job["id"]),
        )
        conn.commit()


def _insert_hold(conn, run_id: int, day: str, stamp: str) -> None:
    conn.execute(
        """
        UPDATE jobs SET status = 'done', updated_at = ?
        WHERE edition_date = ? AND kind = 'hold' AND status = 'pending'
        """,
        (stamp, day),
    )
    conn.execute(
        """
        INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
        VALUES (?, ?, 'hold', 'pending', ?, ?)
        """,
        (run_id, day, stamp, stamp),
    )
    conn.commit()


def _save_run(
    conn,
    day: str,
    stamp: str,
    status: str,
    delivery: str | None,
    directory: Path,
    timing: dict,
    sources: dict,
    model,
    trims: list,
    *,
    finished: str | None = None,
) -> int:
    existing = _latest_run(conn, day)
    body = (
        stamp,
        finished,
        status,
        0,
        0,
        None,
        0,
        delivery,
        json.dumps(timing),
        json.dumps(sources),
        model,
        json.dumps(trims),
        str(directory),
    )
    if existing is None:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                edition_date, started_at, finished_at, status, printed, uploaded,
                cups_job_id, upload_attempts, delivery, timing, sources, model, trims, directory
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (day, *body),
        )
        conn.commit()
        return int(cursor.lastrowid)
    conn.execute(
        """
        UPDATE runs SET
            started_at = ?, finished_at = ?, status = ?, printed = ?, uploaded = ?,
            cups_job_id = ?, upload_attempts = ?, delivery = ?, timing = ?, sources = ?,
            model = ?, trims = ?, directory = ?
        WHERE id = ?
        """,
        (*body, existing["id"]),
    )
    conn.commit()
    return int(existing["id"])


def _snapshot_meta(directory: Path) -> tuple[dict, str | None, list]:
    path = directory / "edition.json"
    if not path.is_file():
        return {}, None, []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    meta = loaded.get("meta") or {}
    sources = meta.get("sources") or {}
    if not isinstance(sources, dict):
        sources = {"value": sources}
    trims = meta.get("trims") or []
    if not isinstance(trims, list):
        trims = [trims]
    return sources, meta.get("model"), trims


def _ensure_alert_inputs(conn, kind: str, edition_date: str):
    return conn.execute(
        "SELECT 1 FROM alerts WHERE kind = ? AND edition_date = ?",
        (kind, edition_date),
    ).fetchone()


def _alert(conn, kind: str, level: str, message: str, edition_date: str, stamp: str) -> None:
    if _ensure_alert_inputs(conn, kind, edition_date):
        return
    conn.execute(
        """
        INSERT INTO alerts (created_at, kind, level, message, edition_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (stamp, kind, level, message, edition_date),
    )
    conn.commit()


def _heartbeat(conn, stamp: str, synced: bool, cups, settings, data_dir: Path) -> None:
    try:
        printer = cups.printer_state(str(settings.get("printer_name") or ""))
    except Exception:
        printer = "unknown"
    free_mb = shutil.disk_usage(data_dir).free / (1024 * 1024)
    conn.execute(
        """
        INSERT INTO heartbeat (recorded_at, ntp_synced, printer_state, disk_free_mb)
        VALUES (?, ?, ?, ?)
        """,
        (stamp, 1 if synced else 0, printer, free_mb),
    )
    conn.commit()


def _prune_local(data_dir: Path, settings, today: date) -> None:
    days = settings.get("local_retention_days")
    if days is None:
        return
    limit = int(days)
    root = data_dir / "editions"
    if not root.is_dir():
        return
    for child in list(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            edition_day = date.fromisoformat(child.name)
        except ValueError:
            continue
        if (today - edition_day).days > limit:
            shutil.rmtree(child)


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


def _should_build(conn, settings, moment: datetime, synced: bool) -> bool:
    if not synced or _edition_exists(conn, moment.date()):
        return False
    clock = moment.hour * 60 + moment.minute
    return _start_minutes(settings, moment) <= clock < _deadline_minutes(settings)


def _past_deadline(settings, moment: datetime) -> bool:
    return moment.hour * 60 + moment.minute >= _deadline_minutes(settings)


def _start_minutes(settings, moment: datetime) -> int:
    weekend = moment.weekday() >= 5 and bool(settings.get("weekend_edition"))
    if weekend:
        return _minutes(str(settings.get("weekend_start") or "08:00"))
    return _minutes(str(settings.get("weekday_start") or "06:30"))


def _deadline_minutes(settings) -> int:
    return _minutes(str(settings.get("latest_acceptable") or "10:00"))


def _switch(settings, day: date, name: str) -> bool:
    enabled = bool(settings.get(f"{name}_enabled"))
    if settings.get("override_date") == day.isoformat():
        override = settings.get(f"override_{name}")
        if override is not None:
            return bool(override)
    return enabled


def _wants_print(settings, day: date) -> bool:
    return _switch(settings, day, "print") and bool(str(settings.get("printer_name") or "").strip())


def _source_failed(value) -> bool:
    if value == "failed":
        return True
    if isinstance(value, dict):
        return any(_source_failed(item) for item in value.values())
    if isinstance(value, list):
        return any(_source_failed(item) for item in value)
    return False


def _latest_run(conn, day: str):
    return conn.execute(
        "SELECT * FROM runs WHERE edition_date = ? ORDER BY id DESC LIMIT 1",
        (day,),
    ).fetchone()


def _run_by_id(conn, run_id: int):
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def _as_local(now: datetime | None, zone: ZoneInfo) -> datetime:
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def _minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)
