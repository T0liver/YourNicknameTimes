#!/usr/bin/env python3
"""List Baïkal calendars and task lists (CalDAV discovery)."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import caldav


def _req(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"FAIL missing {name} (set in smoke.local.env)", file=sys.stderr)
        sys.exit(1)
    return val


def main() -> int:
    url = _req("CALDAV_URL")
    user = _req("CALDAV_USER")
    password = _req("CALDAV_PASSWORD")

    print("== Baïkal CalDAV ==")
    if "baikal.example" in url or "example.com" in url:
        print(
            "FAIL CALDAV_URL is still the smoke.env.example placeholder; set your real Baïkal URL",
            file=sys.stderr,
        )
        return 1
    print(f"URL: {url}")

    client = caldav.DAVClient(url=url, username=user, password=password)
    principal = client.principal()

    calendars = principal.calendars()
    if not calendars:
        print("WARN no calendars returned")
    else:
        print(f"-- calendars ({len(calendars)}) --")
        for cal in calendars:
            print(f"  • {getattr(cal, 'name', cal)}")

    # Task lists are often separate calendars with VTODO support.
    todo_lists: list = []
    for cal in calendars:
        try:
            supported = cal.get_supported_components()
            if supported and "VTODO" in supported:
                todo_lists.append(cal)
        except Exception:
            continue

    if todo_lists:
        print(f"-- task lists ({len(todo_lists)}) --")
        for cal in todo_lists:
            print(f"  • {getattr(cal, 'name', cal)}")
    else:
        print("-- task lists --")
        print("  (none flagged with VTODO; if tasks live elsewhere, check Baïkal)")

    # Light fetch: today-ish events and open todos (no DB, no secrets.env).
    print("-- sample data --")
    start = date.today()
    end = start + timedelta(days=7)
    for cal in calendars[:3]:
        try:
            events = cal.date_search(start=start, end=end, expand=True)
            print(f"  {getattr(cal, 'name', 'calendar')}: {len(events)} event(s) in next 7 days")
        except Exception as exc:
            print(f"  {getattr(cal, 'name', 'calendar')}: search skipped ({exc})")

    for cal in todo_lists[:2]:
        try:
            todos = cal.todos()
            open_todos = [t for t in todos if t]
            print(f"  {getattr(cal, 'name', 'tasks')}: {len(open_todos)} todo(s) listed")
        except Exception as exc:
            print(f"  {getattr(cal, 'name', 'tasks')}: todo list skipped ({exc})")

    print("PASS check_baikal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
