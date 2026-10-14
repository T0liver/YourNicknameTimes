import json
import stat
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from newspaper.db import (
    DEFAULT_SETTINGS,
    init_data,
    load_settings,
    save_settings,
)
from newspaper.edition_build import build_edition, format_dateline, main, run
from newspaper.fixtures import edition_with, fixture_edition
from newspaper.http import UnsafeURL, get
from newspaper.overflow import drop_one
from newspaper.render import build_document, render_edition, render_html

A4_WIDTH_PX = 210 * 96 / 25.4
A4_HEIGHT_PX = 297 * 96 / 25.4
WHEN = datetime(2026, 10, 14, 9, 55, tzinfo=ZoneInfo("Europe/Budapest"))
SATURDAY = datetime(2026, 10, 17, 8, 0, tzinfo=ZoneInfo("Europe/Budapest"))
PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
FLOOR_LINES = [
    {"label": "Nap", "text": "Kel 06:28, nyugszik 18:41"},
    {"label": "Hold", "text": "Fogyó hold"},
    {"label": "Névnap", "text": "Máté, Ildikó"},
    {"label": "Árfolyam", "text": "EUR 395, USD 362, CHF 421"},
]


def _write_ok(edition, path):
    path.write_bytes(b"%PDF-1.4\n")
    return 1


def _read(edition_dir: Path) -> dict:
    return json.loads((edition_dir / "edition.json").read_text(encoding="utf-8"))


def test_model_off_fixture_pdf_is_one_a4_page(tmp_path, monkeypatch):
    received = []
    original = render_edition

    def spy(out_path, edition=None):
        received.append(edition)
        return original(out_path, edition)

    monkeypatch.setattr("newspaper.edition_build.render_edition", spy)
    edition_dir = tmp_path / "edition"
    code = build_edition(fixture_edition(), edition_dir)
    written = _read(edition_dir)
    document = build_document(written)
    page = document.pages[0]
    assert code == 0
    assert written["meta"]["mode"] == "off"
    assert written["meta"]["model"] is None
    assert received == [written]
    assert (edition_dir / "print.pdf").is_file()
    assert len(document.pages) == 1
    assert page.width == pytest.approx(A4_WIDTH_PX, abs=1)
    assert page.height == pytest.approx(A4_HEIGHT_PX, abs=1)


def test_renderer_receives_the_loaded_json(tmp_path):
    snapshot = fixture_edition()
    snapshot["meta"] = {"probe": (1, 2)}
    seen = []

    def render(edition, path):
        seen.append(edition)
        path.write_bytes(b"%PDF-1.4\n")
        return 1

    edition_dir = tmp_path / "edition"
    assert build_edition(snapshot, edition_dir, render_pdf=render) == 0
    written = _read(edition_dir)
    assert seen == [written]
    assert seen[0]["meta"]["probe"] == [1, 2]
    assert seen[0]["meta"]["mode"] == "off"
    assert seen[0]["meta"]["model"] is None


def test_empty_blocks_are_omitted_and_a_present_column_is_full_width(tmp_path):
    empty = edition_with(
        news=[],
        today=[],
        this_week=[],
        weather=None,
        almanac=None,
        prep=[],
        due=[],
        overdue=[],
        daily_item="",
        motto="",
    )
    edition_dir = tmp_path / "empty"
    assert build_edition(empty, edition_dir, render_pdf=_write_ok) == 0
    written = _read(edition_dir)
    html = render_html(written)
    assert "block-label" not in html
    assert "a1-main" not in html
    assert "band" not in html

    lead_only = edition_with(
        today=[],
        this_week=[],
        weather=None,
        almanac=None,
        prep=[],
        due=[],
        overdue=[],
        daily_item=None,
    )
    lead_html = render_html(lead_only)
    assert 'class="lead-td full"' in lead_html
    rail_only = edition_with(
        news=[],
        today=[],
        this_week=[],
        weather=None,
        almanac={"lines": [{"label": "Nap", "text": "Kel 06:28"}]},
        prep=[],
        due=[],
        overdue=[],
        daily_item=None,
    )
    assert 'class="rail-td full"' in render_html(rail_only)


def test_one_almanac_detail_is_dropped_and_the_second_render_fits(tmp_path):
    snapshot = fixture_edition()
    snapshot["almanac"] = {
        "lines": FLOOR_LINES + [{"label": "Ezen a napon", "text": "Valami történt."}]
    }
    calls = []

    def render(edition, path):
        calls.append(edition)
        labels = [line["label"] for line in edition["almanac"]["lines"]]
        if "Ezen a napon" in labels:
            path.write_bytes(b"%PDF-partial")
            return 2
        path.write_bytes(b"%PDF-1.4\n")
        return 1

    edition_dir = tmp_path / "edition"
    assert build_edition(snapshot, edition_dir, render_pdf=render) == 0
    log = (edition_dir / "run.log").read_text(encoding="utf-8")
    written = _read(edition_dir)
    assert len(calls) == 2
    assert calls[1]["meta"]["trims"] == ["almanac detail"]
    assert "drop: almanac detail" in log
    assert "Ezen a napon" not in log
    assert [line["label"] for line in written["almanac"]["lines"]] == [
        "Nap",
        "Hold",
        "Névnap",
        "Árfolyam",
    ]
    assert (edition_dir / "print.pdf").read_bytes().startswith(b"%PDF-1.4")


def test_still_too_long_exits_nonzero_and_deletes_the_pdf(tmp_path):
    snapshot = fixture_edition()
    snapshot["almanac"] = {
        "lines": FLOOR_LINES + [{"label": "Ezen a napon", "text": "Részlet."}]
    }
    snapshot["this_week"] = [{"day": f"Nap {n}", "text": "sor"} for n in range(4)]
    snapshot["news"] = [
        {"headline": "Egy", "publisher": "Telex", "time": "05:00", "dek": "hosszú"},
        {"headline": "Kettő", "publisher": "Telex", "time": "05:01"},
        {"headline": "Három", "publisher": "Telex", "time": "05:02"},
        {"headline": "Négy", "publisher": "Telex", "time": "05:03"},
    ]
    snapshot["today"] = [{"time": "09:00", "title": "Megbeszélés", "place": "Iroda"}]
    snapshot["prep"] = ["Első jegyzet.", "Második jegyzet."]

    def render(edition, path):
        path.write_bytes(b"%PDF-partial")
        return 2

    edition_dir = tmp_path / "edition"
    assert build_edition(snapshot, edition_dir, render_pdf=render) == 1
    log = (edition_dir / "run.log").read_text(encoding="utf-8")
    assert not (edition_dir / "print.pdf").exists()
    assert (edition_dir / "edition.json").is_file()
    for line in (
        "drop: almanac detail",
        "drop: week row",
        "drop: dek",
        "drop: place",
        "drop: prep note",
    ):
        assert line in log
    written = _read(edition_dir)
    assert len(written["news"]) == 4
    assert len(written["this_week"]) == 3
    assert written["prep"] == ["Első jegyzet."]
    assert "dek" not in written["news"][0]
    assert "place" not in written["today"][0]


def test_render_exception_deletes_a_partial_pdf(tmp_path):
    def render(edition, path):
        path.write_bytes(b"%PDF-partial")
        raise RuntimeError("Pango missing")

    edition_dir = tmp_path / "edition"
    assert build_edition(fixture_edition(), edition_dir, render_pdf=render) == 1
    assert not (edition_dir / "print.pdf").exists()
    log = (edition_dir / "run.log").read_text(encoding="utf-8")
    assert "build failed: Pango missing" in log


def test_drop_order_keeps_the_floors():
    edition = {
        "almanac": {
            "lines": FLOOR_LINES
            + [
                {"label": "Ezen a napon", "text": "egy"},
                {"label": "Ezen a napon", "text": "kettő"},
            ]
        },
        "this_week": [{"day": str(n), "text": "x"} for n in range(5)],
        "news": [
            {"headline": "a", "dek": "da"},
            {"headline": "b", "dek": "db"},
            {"headline": "c"},
            {"headline": "d"},
            {"headline": "e"},
            {"headline": "f"},
        ],
        "today": [{"time": "09:00", "title": "t", "dek": "td", "place": "Iroda"}],
        "prep": ["első", "második", "harmadik"],
    }
    dropped = []
    while True:
        what = drop_one(edition)
        if what is None:
            break
        dropped.append(what)
    assert dropped == [
        "almanac detail",
        "almanac detail",
        "week row",
        "week row",
        "news row",
        "news row",
        "dek",
        "dek",
        "dek",
        "place",
        "prep note",
        "prep note",
    ]
    assert [line["label"] for line in edition["almanac"]["lines"]] == [
        "Nap",
        "Hold",
        "Névnap",
        "Árfolyam",
    ]
    assert len(edition["this_week"]) == 3
    assert len(edition["news"]) == 4
    assert edition["prep"] == ["első"]
    assert drop_one(edition) is None


def test_no_nickname_uses_the_default_nameplate_and_omits_the_motto(tmp_path):
    def render(edition, path):
        path.write_bytes(b"%PDF-1.4\n")
        return 1

    data = tmp_path / "data"
    assert run(data, now=WHEN, render_pdf=render) == 0
    written = _read(data / "editions" / "2026-10-14")
    html = render_html(written)
    assert written["nickname"] == "Your Nickname"
    assert written["motto"] == ""
    assert written["dateline"] == "Vol. 1 · 2026. október 14. · szerda · AS OF 09:55"
    assert written["weekend"] is False
    assert written["meta"]["mode"] == "off"
    assert written["meta"]["model"] is None
    assert written["meta"]["as_of"] == "2026-10-14T09:55+02:00"
    assert written["meta"]["volume"] == 1
    assert written["meta"]["language"] == "hu"
    assert written["meta"]["timezone"] == "Europe/Budapest"
    assert ">Your Nickname Times<" in html
    assert 'class="motto"' not in html
    assert "weekend-sun" not in html
    assert (
        format_dateline(2, WHEN, "Budapest")
        == "Vol. 2 · 2026. október 14. · szerda · Budapest · AS OF 09:55"
    )
    conn = init_data(data)
    try:
        assert load_settings(conn)["volume"] == 2
    finally:
        conn.close()


def test_saturday_dateline_and_weekend_masthead(tmp_path):
    data = tmp_path / "data"
    assert run(data, now=SATURDAY, render_pdf=_write_ok) == 0
    written = _read(data / "editions" / "2026-10-17")
    html = render_html(written)
    assert written["dateline"] == "Vol. 1 · 2026. október 17. · szombat · AS OF 08:00"
    assert written["weekend"] is True
    assert "weekend-sun.svg" in html
    assert "Yippie, weekend! You earned it!" in html


def test_same_day_rerun_keeps_one_edition_row(tmp_path):
    data = tmp_path / "data"
    assert run(data, now=WHEN, render_pdf=_write_ok) == 0
    assert run(data, now=WHEN, render_pdf=_write_ok) == 0
    written = _read(data / "editions" / "2026-10-14")
    assert written["meta"]["volume"] == 2
    conn = init_data(data)
    try:
        rows = conn.execute(
            "SELECT edition_date, volume FROM editions ORDER BY edition_date"
        ).fetchall()
        assert [(row["edition_date"], row["volume"]) for row in rows] == [("2026-10-14", 2)]
        assert load_settings(conn)["volume"] == 3
    finally:
        conn.close()


def test_failed_run_does_not_increment_volume(tmp_path):
    def render(edition, path):
        path.write_bytes(b"%PDF-partial")
        return 2

    data = tmp_path / "data"
    assert run(data, now=WHEN, render_pdf=render) == 1
    assert not any(data.rglob("print.pdf"))
    conn = init_data(data)
    try:
        assert load_settings(conn)["volume"] == 1
        assert conn.execute("SELECT COUNT(*) AS n FROM editions").fetchone()["n"] == 0
    finally:
        conn.close()


def test_cli_failure_exits_nonzero(tmp_path, capsys, monkeypatch):
    data = tmp_path / "data"

    def always_long(edition, path):
        path.write_bytes(b"%PDF-partial")
        return 2

    monkeypatch.setattr("newspaper.edition_build.weasy_render", always_long)
    with pytest.raises(SystemExit) as caught:
        main(["--data-dir", str(data)])
    assert caught.value.code == 1
    assert "edition failed" in capsys.readouterr().err
    assert not any(data.rglob("print.pdf"))


def test_fresh_database_seeds_defaults_and_keeps_five_versions(tmp_path):
    data = tmp_path / "data"
    conn = init_data(data)
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {
            "settings",
            "feeds",
            "editions",
            "puzzle_history",
            "rate_history",
            "runs",
            "jobs",
            "heartbeat",
            "alerts",
        } <= tables
        assert tables.isdisjoint({"run_events", "health_checks", "admin"})
        assert load_settings(conn) == DEFAULT_SETTINGS
        feeds = conn.execute("SELECT name, url, category FROM feeds ORDER BY id").fetchall()
        assert [(row["name"], row["url"], row["category"]) for row in feeds] == [
            ("Telex", "https://telex.hu/rss", "local"),
            ("Wired", "https://www.wired.com/feed/rss", "interest"),
        ]
        secrets = data / "secrets.env"
        assert secrets.read_text(encoding="utf-8") == (
            "CALDAV_PASSWORD=\n"
            "DROPBOX_REFRESH_TOKEN=\n"
            "DROPBOX_APP_KEY=\n"
            "DROPBOX_APP_SECRET=\n"
        )
        assert stat.S_IMODE(secrets.stat().st_mode) == 0o600
        assert "CALDAV_PASSWORD" not in conn.execute(
            "SELECT body FROM settings ORDER BY version DESC LIMIT 1"
        ).fetchone()["body"]
        for n in range(5):
            body = load_settings(conn)
            body["volume"] = n + 2
            save_settings(conn, body)
        versions = [
            row["version"]
            for row in conn.execute("SELECT version FROM settings ORDER BY version")
        ]
        assert versions == [2, 3, 4, 5, 6]
        assert load_settings(conn)["volume"] == 6
    finally:
        conn.close()


def test_existing_settings_gain_only_missing_delivery_keys(tmp_path):
    data = tmp_path / "data"
    conn = init_data(data)
    try:
        body = load_settings(conn)
        for key in ("print_enabled", "upload_enabled", "local_retention_days"):
            body.pop(key)
        body["nickname"] = "Ada"
        body["hold_mode"] = False
        save_settings(conn, body)
        version = conn.execute("SELECT MAX(version) AS version FROM settings").fetchone()["version"]
    finally:
        conn.close()
    conn = init_data(data)
    try:
        loaded = load_settings(conn)
        assert loaded["nickname"] == "Ada"
        assert loaded["hold_mode"] is False
        assert loaded["print_enabled"] is True
        assert loaded["upload_enabled"] is True
        assert loaded["local_retention_days"] == 30
        filled = conn.execute("SELECT MAX(version) AS version FROM settings").fetchone()["version"]
        assert filled == version + 1
    finally:
        conn.close()
    conn = init_data(data)
    try:
        stayed = conn.execute("SELECT MAX(version) AS version FROM settings").fetchone()["version"]
        assert stayed == filled
        assert load_settings(conn)["hold_mode"] is False
    finally:
        conn.close()


def test_existing_secrets_file_is_left_alone(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    secrets = data / "secrets.env"
    secrets.write_text("CALDAV_PASSWORD=keep\n", encoding="utf-8")
    conn = init_data(data)
    conn.close()
    assert secrets.read_text(encoding="utf-8") == "CALDAV_PASSWORD=keep\n"
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o600


def test_weather_numbers_and_daily_item_shapes():
    missing = render_html(edition_with(weather={"summary": "Derült", "outlook": []}))
    assert "wx-hl" not in missing
    assert "Derült" in missing
    present = render_html(fixture_edition())
    assert 'class="wx-hl"' in present
    assert "22° / 11°" in present

    string_html = render_html(edition_with(daily_item="Könnyű sudoku"))
    assert "<p>Könnyű sudoku</p>" in string_html
    assert "comic" not in string_html

    comic = render_html(
        edition_with(
            daily_item={
                "kind": "xkcd",
                "src": PNG,
                "alt": "A comic alt",
                "credit": "xkcd.com, CC BY-NC 2.5",
            }
        )
    )
    assert 'class="comic"' in comic
    assert f'src="{PNG}"' in comic
    assert "A comic alt" in comic
    assert "xkcd.com, CC BY-NC 2.5" in comic

    grid = [[0] * 9 for _ in range(9)]
    grid[0][0] = 5
    grid[8][8] = 9
    puzzle = render_html(edition_with(daily_item={"kind": "sudoku", "grid": grid, "large": True}))
    assert 'class="sudoku sudoku-large"' in puzzle
    assert "<td>5</td>" in puzzle
    assert "<td>9</td>" in puzzle
    assert "<td></td>" in puzzle


class _Response:
    def __init__(self, status, url, location=None):
        self.status_code = status
        self.url = url
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None and status in {301, 302, 303, 307, 308}


def test_file_url_raises_without_a_request_or_a_shell(monkeypatch):
    source = Path(get.__code__.co_filename).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "os.system" not in source

    def fail_get(*args, **kwargs):
        raise AssertionError("HTTP request")

    def fail_run(*args, **kwargs):
        raise AssertionError("shell")

    monkeypatch.setattr("newspaper.http.requests.get", fail_get)
    monkeypatch.setattr("subprocess.run", fail_run)
    with pytest.raises(UnsafeURL):
        get("file:///etc/passwd")


def test_redirect_to_file_is_refused_before_the_next_request(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        assert kwargs["allow_redirects"] is False
        return _Response(302, url, "file:///etc/passwd")

    monkeypatch.setattr("newspaper.http.requests.get", fake_get)
    with pytest.raises(UnsafeURL):
        get("https://example.test/start")
    assert calls == ["https://example.test/start"]


def test_https_redirect_is_followed(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/a"):
            return _Response(302, url, "https://example.test/b")
        return _Response(200, url)

    monkeypatch.setattr("newspaper.http.requests.get", fake_get)
    response = get("https://example.test/a")
    assert response.status_code == 200
    assert calls == ["https://example.test/a", "https://example.test/b"]
