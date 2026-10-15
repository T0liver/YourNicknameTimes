import json
import stat
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

from newspaper.db import connect, init_data, load_settings, save_settings
from newspaper.render import render_cloud, render_html, render_preview, trim_cloud
from newspaper.sources.caldav_source import _Item, _due_line, _week_row
from newspaper.worker import (
    WAKE_SECONDS,
    DropboxUploader,
    SystemCups,
    UploadError,
    cycle,
    lp_argv,
    ntp_argv,
    query_ntp,
    serve,
)

ZONE = ZoneInfo("Europe/Budapest")
NINE = datetime(2026, 10, 14, 9, 0, tzinfo=ZONE)
TEN = datetime(2026, 10, 14, 10, 0, tzinfo=ZONE)
DAY = "2026-10-14"


class Resp:
    def __init__(self, code=200, payload=None, text="ok"):
        self.status_code = code
        self.text = text
        self._payload = {} if payload is None else payload

    def json(self):
        return self._payload


class FakeCups:
    def __init__(self, states=("completed",)):
        self.states = list(states)
        self.submits = []
        self.job_id = "Brother-7"

    def printer_state(self, name):
        return "printer Brother is idle"

    def submit(self, argv):
        self.submits.append(list(argv))
        return self.job_id

    def job_state(self, job_id):
        assert job_id == self.job_id
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]


def _quiet_copies(edition_dir, level):
    edition_dir = Path(edition_dir)
    (edition_dir / "cloud.pdf").write_bytes(b"%PDF-cloud")
    (edition_dir / "preview.png").write_bytes(b"\x89PNG\r\n\x1a\n")


def _init(tmp_path, **changes):
    data = tmp_path / "data"
    conn = init_data(data)
    try:
        if changes:
            body = load_settings(conn)
            body.update(changes)
            save_settings(conn, body)
    finally:
        conn.close()
    return data


def _secrets(data, token="refresh-token"):
    text = (
        "CALDAV_PASSWORD=\n"
        f"DROPBOX_REFRESH_TOKEN={token}\n"
        "DROPBOX_APP_KEY=app-key\n"
        "DROPBOX_APP_SECRET=app-secret\n"
    )
    path = data / "secrets.env"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def _builder(code=0, sources=None):
    calls = []

    def build(data_dir, now=None):
        calls.append(now)
        directory = Path(data_dir) / "editions" / now.date().isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "nickname": "Ada",
            "motto": "",
            "dateline": f"AS OF {now.strftime('%H:%M')}",
            "weekend": False,
            "prep": ["Jegyet előre venni."],
            "today": [
                {
                    "time": "09:00",
                    "title": "Megbeszélés",
                    "place": "Iroda",
                    "dek": "hosszú dek",
                    "attendees": ["Nóra"],
                }
            ],
            "this_week": [{"day": "Péntek", "text": "14:00 Fogorvos (Rendelő)", "place": "Rendelő"}],
            "due": [{"text": "Péntek: Szerződés: átnézni", "detail": "átnézni"}],
            "news": [],
            "overdue": [],
            "daily_item": "",
            "weather": None,
            "almanac": None,
            "meta": {
                "mode": "off",
                "model": None,
                "trims": [],
                "sources": {"caldav": "ok"} if sources is None else sources,
                "as_of": now.isoformat(timespec="minutes"),
            },
        }
        (directory / "edition.json").write_text(json.dumps(snapshot), encoding="utf-8")
        pdf = directory / "print.pdf"
        if code == 0:
            pdf.write_bytes(b"%PDF-print")
        elif pdf.exists():
            pdf.unlink()
        return code

    return calls, build


def _seed(data, *, status="awaiting_approval", job_status="approved", sources=None, created_at=None):
    directory = data / "editions" / DAY
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "dateline": "AS OF 06:30",
        "prep": ["Jegyet előre venni."],
        "today": [{"title": "Megbeszélés", "place": "Iroda", "dek": "hosszú dek"}],
        "meta": {
            "mode": "off",
            "model": None,
            "trims": ["dek"],
            "sources": {"caldav": "ok"} if sources is None else sources,
            "as_of": "2026-10-14T06:30+02:00",
        },
    }
    (directory / "edition.json").write_text(json.dumps(snapshot), encoding="utf-8")
    (directory / "print.pdf").write_bytes(b"%PDF-print")
    (directory / "cloud.pdf").write_bytes(b"%PDF-cloud")
    (directory / "preview.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    stamp = created_at or "2026-10-14T06:30:00+02:00"
    conn = connect(data / "newspaper.db")
    try:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                edition_date, started_at, finished_at, status, printed, uploaded,
                cups_job_id, upload_attempts, delivery, timing, sources, model, trims, directory
            ) VALUES (?, ?, NULL, ?, 0, 0, NULL, 0, 'held', '{}', ?, NULL, ?, ?)
            """,
            (
                DAY,
                stamp,
                status,
                json.dumps(snapshot["meta"]["sources"]),
                json.dumps(snapshot["meta"]["trims"]),
                str(directory),
            ),
        )
        run_id = cursor.lastrowid
        if job_status:
            conn.execute(
                """
                INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
                VALUES (?, ?, 'hold', ?, ?, ?)
                """,
                (run_id, DAY, job_status, stamp, stamp),
            )
        conn.commit()
    finally:
        conn.close()
    return directory


def _rows(data, sql):
    conn = connect(data / "newspaper.db")
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _kinds(data):
    return [row["kind"] for row in _rows(data, "SELECT kind FROM alerts ORDER BY id")]


def _run(data):
    return _rows(data, "SELECT * FROM runs ORDER BY id DESC LIMIT 1")[0]


def _post_recorder(posts, upload_code=200, folder_code=200):
    def post(url, **kwargs):
        posts.append((url, kwargs))
        if url.endswith("/oauth2/token"):
            return Resp(200, {"access_token": "tok"})
        if url.endswith("/files/create_folder_v2"):
            return Resp(folder_code, {})
        return Resp(upload_code, {})

    return post


def test_approved_hold_prints_once_and_uploads_both_copies(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    directory = _seed(data)
    posts = []
    cups = FakeCups(("completed",))
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=lambda data_dir, now=None: 0,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    uploads = [item for item in posts if item[0].endswith("/files/upload")]
    paths = [json.loads(item[1]["headers"]["Dropbox-API-Arg"])["path"] for item in uploads]
    assert cups.submits == [lp_argv("Brother", directory / "print.pdf", True)]
    assert paths == ["/editions/2026-10-14.pdf", "/latest.pdf"]
    assert all(item[1]["data"] == b"%PDF-cloud" for item in uploads)
    assert all(json.loads(item[1]["headers"]["Dropbox-API-Arg"])["mode"] == "overwrite" for item in uploads)
    assert not any("delete" in item[0] for item in posts)
    run = _run(data)
    assert run["printed"] == 1
    assert run["uploaded"] == 1
    assert run["status"] == "done"
    assert run["delivery"] == "printed"
    assert run["cups_job_id"] == "Brother-7"
    assert json.loads(run["trims"]) == ["dek"]
    assert "run_failed" not in _kinds(data)


def test_processing_job_is_polled_without_a_second_lp(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    _seed(data)
    posts = []
    cups = FakeCups(("processing", "completed"))
    common = dict(
        now=NINE,
        ntp_synced=True,
        build=lambda data_dir, now=None: 0,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    cycle(data, **common)
    assert len(cups.submits) == 1
    assert _run(data)["printed"] == 0
    assert posts == []
    cycle(data, **common)
    assert len(cups.submits) == 1
    assert cups.job_id == _run(data)["cups_job_id"]
    assert _run(data)["printed"] == 1
    assert _run(data)["uploaded"] == 1
    assert len([item for item in posts if item[0].endswith("/files/upload")]) == 2


def test_fresh_hold_writes_copies_and_alerts_after_an_hour(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    calls, build = _builder()
    cups = FakeCups()
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=build,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    directory = data / "editions" / DAY
    assert calls == [NINE]
    assert (directory / "print.pdf").is_file()
    assert (directory / "cloud.pdf").read_bytes() == b"%PDF-cloud"
    assert (directory / "preview.png").read_bytes().startswith(b"\x89PNG")
    assert cups.submits == []
    assert posts == []
    job = _rows(data, "SELECT status, kind FROM jobs")[0]
    assert (job["kind"], job["status"]) == ("hold", "pending")
    assert _run(data)["status"] == "awaiting_approval"
    assert "awaiting_approval" not in _kinds(data)
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            "UPDATE jobs SET created_at = ? WHERE kind = 'hold'",
            ("2026-10-14T07:00:00+02:00",),
        )
        conn.commit()
    finally:
        conn.close()
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=build,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert calls == [NINE]
    alerts = _rows(data, "SELECT kind, level FROM alerts")
    assert [(row["kind"], row["level"]) for row in alerts] == [("awaiting_approval", "info")]
    assert "run_failed" not in _kinds(data)


def test_reject_stops_delivery_and_leaves_the_files(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    directory = _seed(data, job_status="pending")
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
            VALUES (1, ?, 'reject', 'pending', ?, ?)
            """,
            (DAY, "2026-10-14T08:00:00+02:00", "2026-10-14T08:00:00+02:00"),
        )
        conn.commit()
    finally:
        conn.close()
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, cups=cups, dropbox=DropboxUploader(post=lambda *a, **k: Resp()), copies=_quiet_copies)
    assert cups.submits == []
    assert (directory / "print.pdf").is_file()
    assert (directory / "cloud.pdf").is_file()
    assert _run(data)["status"] == "rejected"
    assert "run_failed" not in _kinds(data)


def test_regenerate_writes_a_new_as_of_and_holds_again(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    _seed(data, job_status="pending")
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
            VALUES (1, ?, 'regenerate', 'pending', ?, ?)
            """,
            (DAY, "2026-10-14T08:00:00+02:00", "2026-10-14T08:00:00+02:00"),
        )
        conn.commit()
    finally:
        conn.close()
    calls, build = _builder()
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    written = json.loads((data / "editions" / DAY / "edition.json").read_text(encoding="utf-8"))
    assert calls == [NINE]
    assert written["meta"]["as_of"] == "2026-10-14T09:00+02:00"
    assert written["dateline"] == "AS OF 09:00"
    assert cups.submits == []
    holds = _rows(data, "SELECT status FROM jobs WHERE kind = 'hold' ORDER BY id")
    assert [row["status"] for row in holds] == ["done", "pending"]
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'regenerate'")[0]["status"] == "done"
    assert _run(data)["status"] == "awaiting_approval"


def test_failed_rebuild_prints_nothing(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _seed(data, job_status="pending")
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
            VALUES (1, ?, 'regenerate', 'pending', ?, ?)
            """,
            (DAY, "2026-10-14T08:00:00+02:00", "2026-10-14T08:00:00+02:00"),
        )
        conn.commit()
    finally:
        conn.close()
    calls, build = _builder(code=1)
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls == [NINE]
    assert cups.submits == []
    assert not (data / "editions" / DAY / "print.pdf").exists()
    assert _run(data)["status"] == "failed"
    assert "run_failed" in _kinds(data)


def test_bad_page_does_not_print(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    calls, build = _builder(code=1)
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls == [NINE]
    assert cups.submits == []
    assert not (data / "editions" / DAY / "print.pdf").exists()
    assert _run(data)["status"] == "failed"
    assert _kinds(data) == ["run_failed"]
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls == [NINE, NINE]
    assert cups.submits == []
    assert not (data / "editions" / DAY / "print.pdf").exists()


def test_ntp_off_skips_catch_up_and_deadline_needs_a_synced_clock(tmp_path, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError(args)

    monkeypatch.setattr("newspaper.worker.subprocess.run", explode)
    early = _init(tmp_path / "early")
    calls, build = _builder()
    cycle(early, now=NINE, ntp_synced=False, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == []
    assert _kinds(early) == []

    late = _init(tmp_path / "late")
    missed, missed_build = _builder()
    cycle(late, now=TEN, ntp_synced=True, build=missed_build, cups=FakeCups(), copies=_quiet_copies)
    cycle(late, now=TEN, ntp_synced=True, build=missed_build, cups=FakeCups(), copies=_quiet_copies)
    assert missed == []
    assert _kinds(late) == ["deadline"]

    unsynced = _init(tmp_path / "unsynced")
    cycle(unsynced, now=TEN, ntp_synced=False, build=_builder()[1], cups=FakeCups(), copies=_quiet_copies)
    assert _kinds(unsynced) == []


def test_catch_up_builds_once_and_skips_when_today_exists(tmp_path):
    data = _init(tmp_path)
    calls, build = _builder()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == [NINE]
    run = _run(data)
    assert json.loads(run["timing"])["build"] >= 0
    assert json.loads(run["sources"]) == {"caldav": "ok"}
    assert run["model"] is None

    present = _init(tmp_path / "present")
    conn = connect(present / "newspaper.db")
    try:
        conn.execute(
            "INSERT INTO editions (edition_date, volume, created_at, directory) VALUES (?, 1, ?, ?)",
            (DAY, "2026-10-14T06:30:00+02:00", str(present / "editions" / DAY)),
        )
        conn.commit()
    finally:
        conn.close()
    again, again_build = _builder()
    cycle(present, now=NINE, ntp_synced=True, build=again_build, cups=FakeCups(), copies=_quiet_copies)
    assert again == []


def test_upload_only_override_skips_lp_and_a_missing_token_fails_the_upload(tmp_path):
    data = _init(
        tmp_path,
        printer_name="Brother",
        override_date=DAY,
        override_print=False,
        override_upload=True,
    )
    directory = _seed(data)
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, cups=cups, dropbox=DropboxUploader(), copies=_quiet_copies)
    assert cups.submits == []
    assert (directory / "print.pdf").read_bytes() == b"%PDF-print"
    assert (directory / "cloud.pdf").is_file()
    assert _run(data)["upload_attempts"] == 1
    assert _run(data)["uploaded"] == 0
    assert "dropbox" not in _kinds(data)
    assert "run_failed" not in _kinds(data)


def test_third_upload_failure_alerts_and_the_next_cycle_retries(tmp_path):
    data = _init(tmp_path, printer_name="Brother", hold_mode=False)
    _secrets(data)
    directory = _seed(data, status="delivering", job_status=None)
    posts = []
    cups = FakeCups(("completed",))
    for _ in range(4):
        cycle(
            data,
            now=NINE,
            ntp_synced=True,
            cups=cups,
            dropbox=DropboxUploader(post=_post_recorder(posts, upload_code=500)),
            copies=_quiet_copies,
        )
    assert len(cups.submits) == 1
    assert (directory / "cloud.pdf").is_file()
    assert _run(data)["upload_attempts"] == 4
    assert _kinds(data).count("dropbox") == 1
    token_posts = [item for item in posts if item[0].endswith("/oauth2/token")]
    assert len(token_posts) == 4


def test_local_retention_deletes_expired_directories_only(tmp_path, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError(args[0] if args else kwargs)

    monkeypatch.setattr("newspaper.worker.requests.post", explode)
    data = _init(tmp_path)
    old = data / "editions" / "2026-09-13"
    recent = data / "editions" / "2026-10-01"
    old.mkdir(parents=True)
    recent.mkdir(parents=True)
    (old / "print.pdf").write_bytes(b"%PDF-old")
    (old / "cloud.pdf").write_bytes(b"%PDF-old")
    (old / "preview.png").write_bytes(b"\x89PNG")
    (old / "edition.json").write_text("{}\n", encoding="utf-8")
    (recent / "print.pdf").write_bytes(b"%PDF-new")
    cycle(data, now=NINE, ntp_synced=False, cups=FakeCups(), copies=_quiet_copies)
    assert not old.exists()
    assert (recent / "print.pdf").is_file()


def test_trimmed_cloud_omits_place_dek_and_prep_and_full_keeps_them(tmp_path, monkeypatch):
    edition = {
        "nickname": "Ada",
        "motto": "",
        "dateline": "AS OF 06:30",
        "weekend": False,
        "show_sun": True,
        "greeting": "",
        "news": [{"headline": "Híd", "publisher": "Telex", "time": "05:00", "dek": "hosszú dek"}],
        "today": [
            {
                "time": "09:00",
                "title": "Megbeszélés",
                "place": "Iroda",
                "dek": "ma dek",
                "attendees": ["Nóra"],
            }
        ],
        "this_week": [{"day": "Péntek", "text": "14:00 Fogorvos (Rendelő)", "place": "Rendelő"}],
        "weather": None,
        "prep": ["Jegyet előre venni."],
        "due": [{"text": "Péntek: Szerződés: átnézni", "detail": "átnézni"}],
        "overdue": [],
        "daily_item": "",
        "almanac": None,
    }
    printed = render_html(edition)
    cloud_edition = trim_cloud(edition)
    cloud = render_html(cloud_edition)
    assert "Iroda" in printed
    assert "hosszú dek" in printed
    assert "Jegyet előre venni." in printed
    assert "Rendelő" in printed
    assert "Iroda" not in cloud
    assert "hosszú dek" not in cloud
    assert "ma dek" not in cloud
    assert "Jegyet előre venni." not in cloud
    assert "Rendelő" not in cloud
    assert "Nóra" not in cloud
    assert cloud_edition["due"] == [{"text": "Péntek: Szerződés: átnézni"}]
    assert cloud_edition["prep"] == []
    assert "attendees" not in cloud_edition["today"][0]
    seen = []

    def capture(path, payload=None):
        seen.append(payload)
        Path(path).write_bytes(b"%PDF-1.4\n")
        return 0.01

    monkeypatch.setattr("newspaper.render.render_edition", capture)
    render_cloud(tmp_path / "cloud.pdf", edition, level="trimmed")
    render_cloud(tmp_path / "full.pdf", edition, level="full")
    assert "place" not in seen[0]["today"][0]
    assert seen[0]["prep"] == []
    assert seen[1]["today"][0]["place"] == "Iroda"
    assert seen[1]["prep"] == ["Jegyet előre venni."]
    assert "Iroda" in render_html(seen[1])


def test_week_place_and_due_detail_keep_the_print_strings():
    week = _Item("event", "Fogorvos", "", "Rendelő", date(2026, 10, 16), "14:00", 0, "d")
    row = _week_row(week)
    assert row == {"day": "Péntek", "text": "14:00 Fogorvos (Rendelő)", "place": "Rendelő"}
    plain = _Item("event", "Fogorvos", "", "", date(2026, 10, 16), "14:00", 0, "d")
    assert _week_row(plain) == {"day": "Péntek", "text": "14:00 Fogorvos"}
    due = _Item("task", "Szerződés", "átnézni", "", date(2026, 10, 16), None, 0, "c")
    assert _due_line(due) == {"text": "Péntek: Szerződés: átnézni", "detail": "átnézni"}
    bare = _Item("task", "Szerződés", "", "", date(2026, 10, 16), None, 0, "c")
    assert _due_line(bare) == "Péntek: Szerződés"
    html = render_html(
        {
            "nickname": "Ada",
            "motto": "",
            "dateline": "AS OF 06:30",
            "weekend": False,
            "show_sun": False,
            "greeting": "",
            "news": [],
            "today": [],
            "this_week": [],
            "weather": None,
            "prep": [],
            "due": [_due_line(due)],
            "overdue": [],
            "daily_item": "",
            "almanac": None,
        }
    )
    assert "<p>Péntek: Szerződés: átnézni</p>" in html
    assert "detail" not in html


def test_preview_png_is_the_full_page(tmp_path):
    destination = tmp_path / "preview.png"
    render_preview(
        destination,
        {
            "nickname": "Ada",
            "motto": "",
            "dateline": "AS OF 06:30",
            "weekend": False,
            "show_sun": False,
            "greeting": "",
            "news": [],
            "today": [{"time": "09:00", "title": "Megbeszélés", "place": "Iroda"}],
            "this_week": [],
            "weather": None,
            "prep": ["Jegyet előre venni."],
            "due": [],
            "overdue": [],
            "daily_item": "",
            "almanac": None,
        },
    )
    image = Image.open(destination)
    assert image.format == "PNG"
    assert image.width > 400
    assert image.height > image.width


def test_copies_are_rendered_from_the_written_json(tmp_path, monkeypatch):
    data = _init(tmp_path, cloud_level="full")
    calls, build = _builder()
    seen = []

    def cloud(path, edition, level="trimmed"):
        seen.append(("cloud", edition["meta"]["as_of"], level, edition["today"][0]["place"]))
        Path(path).write_bytes(b"%PDF-cloud")

    def preview(path, edition):
        seen.append(("preview", edition["dateline"], edition["prep"]))
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("newspaper.worker.render_cloud", cloud)
    monkeypatch.setattr("newspaper.worker.render_preview", preview)
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=FakeCups(), copies=None)
    assert calls == [NINE]
    assert seen == [
        ("cloud", "2026-10-14T09:00+02:00", "full", "Iroda"),
        ("preview", "AS OF 09:00", ["Jegyet előre venni."]),
    ]


def test_missing_copy_skips_delivery_until_the_file_is_back(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    directory = _seed(data)
    (directory / "cloud.pdf").unlink()
    (directory / "preview.png").unlink()
    cups = FakeCups()

    def broken(edition_dir, level):
        raise OSError("no png")

    cycle(data, now=NINE, ntp_synced=True, cups=cups, dropbox=DropboxUploader(), copies=broken)
    assert cups.submits == []
    assert (directory / "print.pdf").is_file()
    assert "run_failed" in _kinds(data)
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert len(cups.submits) == 1
    assert _run(data)["printed"] == 1
    assert len([item for item in posts if item[0].endswith("/files/upload")]) == 2


def _record_edition(data, directory):
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO editions (edition_date, volume, created_at, directory)
            VALUES (?, 1, ?, ?)
            """,
            (DAY, "2026-10-14T06:30:00+02:00", str(directory)),
        )
        conn.commit()
    finally:
        conn.close()


def test_canceled_job_raises_a_printer_alert_and_is_not_sent_again(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    directory = _seed(data)
    _record_edition(data, directory)
    cups = FakeCups(("canceled",))
    posts = []
    uploader = DropboxUploader(post=_post_recorder(posts))
    cycle(data, now=NINE, ntp_synced=True, cups=cups, dropbox=uploader, copies=_quiet_copies)
    cycle(data, now=NINE, ntp_synced=True, cups=cups, dropbox=uploader, copies=_quiet_copies)
    assert len(cups.submits) == 1
    assert _run(data)["printed"] == 0
    assert _run(data)["status"] == "failed"
    assert _run(data)["delivery"] == "print_failed"
    assert (directory / "print.pdf").is_file()
    assert "printer" in _kinds(data)
    assert "run_failed" not in _kinds(data)


def test_rejected_lp_is_not_submitted_again(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _secrets(data)
    directory = _seed(data)
    _record_edition(data, directory)
    cups = FakeCups()

    def reject(argv):
        cups.submits.append(list(argv))
        raise RuntimeError("lp rejected")

    cups.submit = reject
    posts = []

    def post(url, **kwargs):
        posts.append(url)
        if url.endswith("/oauth2/token"):
            return Resp(200, {"access_token": "tok"})
        if url.endswith("/files/create_folder_v2"):
            return Resp(200, {})
        if sum(item.endswith("/files/upload") for item in posts) == 1:
            return Resp(500, text="nope")
        return Resp(200, {})

    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=cups,
        dropbox=DropboxUploader(post=post),
        copies=_quiet_copies,
    )
    assert len(cups.submits) == 1
    assert _run(data)["status"] == "delivering"
    assert _run(data)["delivery"] == "print_failed"
    assert _run(data)["upload_attempts"] == 1
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=cups,
        dropbox=DropboxUploader(post=post),
        copies=_quiet_copies,
    )
    assert len(cups.submits) == 1
    assert _run(data)["status"] == "failed"
    assert _run(data)["delivery"] == "print_failed"
    assert _run(data)["uploaded"] == 1
    assert (directory / "print.pdf").is_file()
    assert "printer" in _kinds(data)
    assert "run_failed" not in _kinds(data)


def test_failed_page_still_raises_the_deadline(tmp_path):
    data = _init(tmp_path)
    calls, build = _builder(code=1)
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    cycle(data, now=TEN, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == [NINE]
    assert "deadline" in _kinds(data)
    assert "run_failed" in _kinds(data)


def test_one_sided_when_duplex_is_off(tmp_path):
    data = _init(tmp_path, printer_name="Brother", duplex=False)
    _secrets(data)
    directory = _seed(data)
    cups = FakeCups()
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert cups.submits == [lp_argv("Brother", directory / "print.pdf", False)]
    assert "sides=one-sided" in cups.submits[0]


def test_empty_printer_name_skips_lp(tmp_path):
    data = _init(tmp_path, printer_name="")
    _secrets(data)
    _seed(data)
    cups = FakeCups()
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=cups,
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert cups.submits == []
    assert _run(data)["uploaded"] == 1
    assert _run(data)["printed"] == 0
    assert _run(data)["status"] == "done"


def test_failed_source_ends_done_degraded(tmp_path):
    data = _init(tmp_path, printer_name="Brother", hold_mode=False)
    _secrets(data)
    calls, build = _builder(sources={"caldav": "failed", "feeds": "ok"})
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=build,
        cups=FakeCups(),
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert calls == [NINE]
    assert _run(data)["status"] == "done_degraded"
    assert "degraded" in _kinds(data)


def test_weekend_start_follows_the_edition_switch(tmp_path):
    early = datetime(2026, 10, 17, 7, 0, tzinfo=ZONE)
    opened = datetime(2026, 10, 17, 8, 0, tzinfo=ZONE)
    waiting = _init(tmp_path / "on")
    calls, build = _builder()
    cycle(waiting, now=early, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == []
    cycle(waiting, now=opened, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == [opened]

    off = _init(tmp_path / "off", weekend_edition=False)
    off_calls, off_build = _builder()
    cycle(
        off,
        now=datetime(2026, 10, 17, 6, 30, tzinfo=ZONE),
        ntp_synced=True,
        build=off_build,
        cups=FakeCups(),
        copies=_quiet_copies,
    )
    assert off_calls == [datetime(2026, 10, 17, 6, 30, tzinfo=ZONE)]


def test_weekday_before_0630_does_not_build(tmp_path):
    data = _init(tmp_path)
    calls, build = _builder()
    cycle(
        data,
        now=datetime(2026, 10, 14, 6, 29, tzinfo=ZONE),
        ntp_synced=True,
        build=build,
        cups=FakeCups(),
        copies=_quiet_copies,
    )
    assert calls == []
    cycle(
        data,
        now=datetime(2026, 10, 14, 6, 30, tzinfo=ZONE),
        ntp_synced=True,
        build=build,
        cups=FakeCups(),
        copies=_quiet_copies,
    )
    assert len(calls) == 1


def test_auto_approve_delivers_after_its_clock(tmp_path):
    data = _init(tmp_path, printer_name="Brother", auto_approve=True, auto_approve_time="07:00")
    _secrets(data)
    calls, build = _builder()
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=build,
        cups=FakeCups(),
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert calls == [NINE]
    assert _run(data)["printed"] == 1
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'hold'")[0]["status"] == "done"


def test_heartbeat_records_ntp_printer_and_free_space(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        build=lambda data_dir, now=None: 1,
        cups=FakeCups(),
        copies=_quiet_copies,
    )
    beat = _rows(data, "SELECT * FROM heartbeat")[0]
    assert beat["ntp_synced"] == 1
    assert beat["printer_state"] == "printer Brother is idle"
    assert beat["disk_free_mb"] > 0
    assert beat["recorded_at"].startswith("2026-10-14T09:00:00")


def test_worker_wakes_every_30_seconds(monkeypatch):
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        raise SystemExit

    monkeypatch.setattr("newspaper.worker.cycle", lambda *args, **kwargs: None)
    try:
        serve(Path("/tmp/newspaper-worker"), sleep=sleep)
    except SystemExit:
        pass
    assert WAKE_SECONDS == 30
    assert slept == [30]


def test_ntp_and_cups_commands_do_not_use_a_shell(monkeypatch):
    seen = []

    class Result:
        def __init__(self, stdout="", code=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = code

    def run(argv, **kwargs):
        seen.append((list(argv), kwargs))
        if argv[:2] == ["lpstat", "-p"]:
            return Result("printer Brother is idle.\n")
        if argv[:4] == ["lpstat", "-W", "all", "-l"]:
            return Result("job aborted by the system\n")
        if argv[:3] == ["lpstat", "-W", "completed"]:
            return Result("")
        if argv[0] == "lp":
            return Result("request id is Brother-7 (1 file(s))\n")
        return Result("yes\n")

    monkeypatch.setattr("newspaper.worker.subprocess.run", run)
    assert query_ntp() is True
    cups = SystemCups(run=run)
    assert cups.printer_state("Brother") == "printer Brother is idle."
    assert cups.submit(lp_argv("Brother", Path("print.pdf"), True)) == "Brother-7"
    assert cups.job_state("Brother-7") == "aborted"

    def completed_run(argv, **kwargs):
        seen.append((list(argv), kwargs))
        if argv[:4] == ["lpstat", "-W", "all", "-l"]:
            return Result("")
        if argv[:3] == ["lpstat", "-W", "completed"]:
            return Result("Brother-7 user 1024\n")
        return Result()

    assert SystemCups(run=completed_run).job_state("Brother-7") == "completed"
    assert seen[0][0] == ntp_argv()
    commands = [item[0] for item in seen]
    assert ["lpstat", "-p", "Brother"] in commands
    assert ["lpstat", "-W", "all", "-l", "-o", "Brother-7"] in commands
    assert ["lpstat", "-W", "completed", "-o", "Brother-7"] in commands
    assert all(item[1].get("shell", False) is False for item in seen)
    source = Path(cycle.__code__.co_filename).read_text(encoding="utf-8")
    assert "scripts.smoke" not in source
    assert "shell=True" not in source
    assert "os.system" not in source


def test_dropbox_posts_the_refresh_and_both_upload_hosts(tmp_path):
    posts = []
    pdf = tmp_path / "cloud.pdf"
    pdf.write_bytes(b"%PDF-cloud")
    DropboxUploader(post=_post_recorder(posts, folder_code=409)).upload(
        {
            "DROPBOX_REFRESH_TOKEN": "refresh-token",
            "DROPBOX_APP_KEY": "app-key",
            "DROPBOX_APP_SECRET": "app-secret",
        },
        pdf,
        DAY,
    )
    assert posts[0][0] == "https://api.dropbox.com/oauth2/token"
    assert posts[0][1]["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-token",
        "client_id": "app-key",
        "client_secret": "app-secret",
    }
    assert posts[0][1]["timeout"] == 30
    assert posts[1][0] == "https://api.dropboxapi.com/2/files/create_folder_v2"
    assert posts[2][0] == "https://content.dropboxapi.com/2/files/upload"
    assert posts[3][0] == "https://content.dropboxapi.com/2/files/upload"
    assert posts[2][1]["timeout"] == 60
    try:
        DropboxUploader().upload({"DROPBOX_REFRESH_TOKEN": ""}, pdf, DAY)
    except UploadError as exc:
        assert "missing dropbox token" in str(exc)
    else:
        raise AssertionError("missing token")


def test_secrets_mode_stays_private(tmp_path):
    data = _init(tmp_path)
    _secrets(data)
    assert stat.S_IMODE((data / "secrets.env").stat().st_mode) == 0o600


def _job(data, kind, day=DAY, stamp="2026-10-14T08:00:00+02:00"):
    conn = connect(data / "newspaper.db")
    try:
        conn.execute(
            """
            INSERT INTO jobs (run_id, edition_date, kind, status, created_at, updated_at)
            VALUES (NULL, ?, ?, 'pending', ?, ?)
            """,
            (day, kind, stamp, stamp),
        )
        conn.commit()
    finally:
        conn.close()


def test_run_now_builds_today_and_holds(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _seed(data, job_status="pending")
    _job(data, "run_now")
    calls, build = _builder()
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls == [NINE]
    assert cups.submits == []
    assert _run(data)["status"] == "awaiting_approval"
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'run_now'")[0]["status"] == "done"


def test_stale_preview_does_not_build_tomorrow(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _job(data, "preview", day=DAY)
    calls, build = _builder()
    tomorrow = datetime(2026, 10, 15, 6, 0, tzinfo=ZONE)
    cycle(data, now=tomorrow, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == []
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'preview'")[0]["status"] == "pending"
    assert _rows(data, "SELECT id FROM runs") == []


def test_preview_without_ntp_stays_pending(tmp_path):
    data = _init(tmp_path)
    _job(data, "preview")
    calls, build = _builder()
    cycle(data, now=NINE, ntp_synced=False, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == []
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'preview'")[0]["status"] == "pending"


def test_preview_keeps_a_held_run_and_refreshes_cloud(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    directory = _seed(data, job_status="pending")
    (directory / "cloud.pdf").write_bytes(b"old")
    _job(data, "preview")
    calls, build = _builder()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=FakeCups(), copies=_quiet_copies)
    assert calls == [NINE]
    assert len(_rows(data, "SELECT id FROM runs")) == 1
    assert _run(data)["status"] == "awaiting_approval"
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'hold'")[0]["status"] == "pending"
    assert (directory / "cloud.pdf").read_bytes() == b"%PDF-cloud"


def test_preview_without_a_run_records_one_and_does_not_print(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _job(data, "preview")
    calls, build = _builder()
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls == [NINE]
    assert cups.submits == []
    assert _rows(data, "SELECT kind FROM jobs WHERE kind = 'hold'") == []
    assert _run(data)["status"] == "done"
    assert (data / "editions" / DAY / "preview.png").is_file()


def test_failed_preview_prints_nothing(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    _job(data, "preview")
    calls, build = _builder(code=1)
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, build=build, cups=cups, copies=_quiet_copies)
    assert calls
    assert all(item == NINE for item in calls)
    assert cups.submits == []
    assert _run(data)["status"] == "failed"
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'preview'")[0]["status"] == "failed"


def test_reprint_polls_marker_and_leaves_the_run(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    directory = _seed(data, status="done", job_status=None)
    _job(data, "reprint")
    before = dict(_run(data))
    cups = FakeCups(("processing", "completed"))
    cycle(data, now=NINE, ntp_synced=True, cups=cups, copies=_quiet_copies)
    assert len(cups.submits) == 1
    assert (directory / "reprint.cups").is_file()
    assert _run(data)["status"] == "done"
    assert _run(data)["cups_job_id"] is None
    cycle(data, now=NINE, ntp_synced=True, cups=cups, copies=_quiet_copies)
    assert len(cups.submits) == 1
    assert not (directory / "reprint.cups").exists()
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'reprint'")[0]["status"] == "done"
    assert dict(_run(data))["status"] == before["status"]


def test_missing_print_pdf_fails_reprint_and_removes_marker(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    directory = _seed(data, status="done", job_status=None)
    (directory / "reprint.cups").write_text("Brother-old\n", encoding="utf-8")
    (directory / "print.pdf").unlink()
    _job(data, "reprint")
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, cups=cups, copies=_quiet_copies)
    assert cups.submits == []
    assert not (directory / "reprint.cups").exists()
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'reprint'")[0]["status"] == "failed"


def test_empty_printer_name_does_not_reprint(tmp_path):
    data = _init(tmp_path, printer_name="")
    _seed(data, status="done", job_status=None)
    _job(data, "reprint")
    cups = FakeCups()
    cycle(data, now=NINE, ntp_synced=True, cups=cups, copies=_quiet_copies)
    assert cups.submits == []
    assert _rows(data, "SELECT status FROM jobs WHERE kind = 'reprint'")[0]["status"] == "failed"
    assert _kinds(data) == []


def test_reupload_sends_cloud_pdf_and_missing_file_fails(tmp_path):
    data = _init(tmp_path, printer_name="Brother")
    directory = _seed(data, status="done", job_status=None)
    _secrets(data)
    _job(data, "reupload")
    posts = []
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=FakeCups(),
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    uploads = [item for item in posts if item[0].endswith("/files/upload")]
    assert len(uploads) == 2
    assert _run(data)["status"] == "done"
    assert _run(data)["uploaded"] == 0
    (directory / "cloud.pdf").unlink()
    _job(data, "reupload")
    posts.clear()
    cycle(
        data,
        now=NINE,
        ntp_synced=True,
        cups=FakeCups(),
        dropbox=DropboxUploader(post=_post_recorder(posts)),
        copies=_quiet_copies,
    )
    assert posts == []
    failed = _rows(data, "SELECT status FROM jobs WHERE kind = 'reupload' ORDER BY id")
    assert failed[-1]["status"] == "failed"
