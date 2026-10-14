"""SQLite settings, feeds, and edition records."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

SETTINGS_VERSIONS = 5
SECRETS_TEXT = (
    "CALDAV_PASSWORD=\n"
    "DROPBOX_REFRESH_TOKEN=\n"
    "DROPBOX_APP_KEY=\n"
    "DROPBOX_APP_SECRET=\n"
)

DEFAULT_SETTINGS = {
    "caldav_host": "",
    "caldav_username": "",
    "extras_on": True,
    "name_day_on": True,
    "daily_rotation": {
        "monday": "xkcd",
        "tuesday": "sudoku",
        "wednesday": "xkcd",
        "thursday": "sudoku",
        "friday": "xkcd",
        "saturday": "sudoku",
        "sunday": "xkcd",
    },
    "timezone": "Europe/Budapest",
    "language": "hu",
    "motto": "",
    "title": "Your Nickname Times",
    "nickname": "",
    "city": "",
    "greeting": "Yippie, weekend! You earned it!",
    "weekend_edition": True,
    "weekend_mood": "light",
    "show_sun": True,
    "volume": 1,
    "weekday_start": "06:30",
    "weekend_start": "08:00",
    "latest_acceptable": "10:00",
    "hold_mode": True,
    "auto_approve": False,
    "auto_approve_time": "",
    "print_enabled": True,
    "upload_enabled": True,
    "override_date": "",
    "override_print": None,
    "override_upload": None,
    "cloud_level": "trimmed",
    "local_retention_days": 30,
    "dropbox_retention_days": None,
    "duplex": True,
    "printer_name": "",
}

SEED_FEEDS = (
    {
        "name": "Telex",
        "url": "https://telex.hu/rss",
        "category": "local",
        "language": "hu",
        "weight": 1.0,
        "max_items": 20,
        "enabled": 1,
    },
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "category": "interest",
        "language": "en",
        "weight": 1.0,
        "max_items": 20,
        "enabled": 1,
    },
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    version INTEGER PRIMARY KEY,
    saved_at TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    language TEXT NOT NULL,
    weight REAL NOT NULL,
    max_items INTEGER NOT NULL,
    enabled INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS editions (
    id INTEGER PRIMARY KEY,
    edition_date TEXT NOT NULL,
    volume INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    directory TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS puzzle_history (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    item_key TEXT NOT NULL,
    used_on TEXT NOT NULL,
    UNIQUE (kind, item_key)
);

CREATE TABLE IF NOT EXISTS rate_history (
    id INTEGER PRIMARY KEY,
    currency TEXT NOT NULL,
    rate TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    edition_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    printed INTEGER NOT NULL DEFAULT 0,
    uploaded INTEGER NOT NULL DEFAULT 0,
    cups_job_id TEXT,
    upload_attempts INTEGER NOT NULL DEFAULT 0,
    delivery TEXT,
    timing TEXT NOT NULL,
    sources TEXT NOT NULL,
    model TEXT,
    trims TEXT NOT NULL,
    directory TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,
    edition_date TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS heartbeat (
    id INTEGER PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    ntp_synced INTEGER NOT NULL,
    printer_state TEXT NOT NULL,
    disk_free_mb REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    edition_date TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_data(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "editions").mkdir(exist_ok=True)
    (data_dir / "cache").mkdir(exist_ok=True)
    conn = connect(data_dir / "newspaper.db")
    conn.executescript(SCHEMA)
    seed(conn)
    ensure_secrets(data_dir / "secrets.env")
    return conn


def seed(conn: sqlite3.Connection) -> None:
    feed_count = conn.execute("SELECT COUNT(*) AS n FROM feeds").fetchone()["n"]
    if feed_count == 0:
        conn.executemany(
            """
            INSERT INTO feeds (name, url, category, language, weight, max_items, enabled)
            VALUES (:name, :url, :category, :language, :weight, :max_items, :enabled)
            """,
            SEED_FEEDS,
        )
        conn.commit()
    settings_count = conn.execute("SELECT COUNT(*) AS n FROM settings").fetchone()["n"]
    if settings_count == 0:
        save_settings(conn, deepcopy(DEFAULT_SETTINGS))
        return
    body = load_settings(conn)
    added = False
    for key, value in DEFAULT_SETTINGS.items():
        if key not in body:
            body[key] = deepcopy(value)
            added = True
    if added:
        save_settings(conn, body)


def save_settings(conn: sqlite3.Connection, body: dict) -> int:
    current = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM settings").fetchone()
    version = int(current["version"]) + 1
    saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO settings (version, saved_at, body) VALUES (?, ?, ?)",
        (version, saved_at, json.dumps(body, ensure_ascii=False)),
    )
    conn.execute(
        "DELETE FROM settings WHERE version <= ?",
        (version - SETTINGS_VERSIONS,),
    )
    conn.commit()
    return version


def load_settings(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT body FROM settings ORDER BY version DESC LIMIT 1").fetchone()
    if row is None:
        raise LookupError("settings have not been seeded")
    return json.loads(row["body"])


def increment_volume(conn: sqlite3.Connection) -> int:
    body = load_settings(conn)
    body["volume"] = int(body["volume"]) + 1
    save_settings(conn, body)
    return int(body["volume"])


def record_edition(conn: sqlite3.Connection, edition_date: str, volume: int, directory: Path) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    directory_text = str(directory)
    updated = conn.execute(
        """
        UPDATE editions
        SET volume = ?, created_at = ?, directory = ?
        WHERE edition_date = ?
        """,
        (volume, created_at, directory_text, edition_date),
    )
    if updated.rowcount == 0:
        conn.execute(
            """
            INSERT INTO editions (edition_date, volume, created_at, directory)
            VALUES (?, ?, ?, ?)
            """,
            (edition_date, volume, created_at, directory_text),
        )
    conn.commit()


def ensure_secrets(path: Path) -> None:
    if not path.exists():
        path.write_text(SECRETS_TEXT, encoding="utf-8")
    path.chmod(0o600)


def load_feeds(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT name, url, category, language, weight, max_items, enabled
        FROM feeds
        WHERE enabled = 1
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def puzzle_keys(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute(
        "SELECT item_key FROM puzzle_history WHERE kind = ?",
        (kind,),
    ).fetchall()
    return {row["item_key"] for row in rows}


def remember_puzzle(conn: sqlite3.Connection, kind: str, item_key: str, used_on: str) -> None:
    conn.execute(
        """
        INSERT INTO puzzle_history (kind, item_key, used_on)
        VALUES (?, ?, ?)
        ON CONFLICT (kind, item_key) DO NOTHING
        """,
        (kind, item_key, used_on),
    )
    conn.commit()


def remember_rates(conn: sqlite3.Connection, rates: list[tuple[str, str, str]]) -> None:
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        """
        INSERT INTO rate_history (currency, rate, rate_date, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        [(currency, rate, rate_date, recorded_at) for currency, rate, rate_date in rates],
    )
    conn.commit()


def read_password(path: Path) -> str:
    return read_secrets(path).get("CALDAV_PASSWORD", "")


def read_secrets(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key] = value
    return found
