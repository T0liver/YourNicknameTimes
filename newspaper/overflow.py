"""Drop one overflow item at a time until the edition hits its floors."""

from __future__ import annotations

FLOOR_LABELS = {
    "nap",
    "sun",
    "hold",
    "moon",
    "névnap",
    "name day",
    "árfolyam",
    "rates",
}
WEEK_FLOOR = 3
NEWS_FLOOR = 4


def drop_one(edition: dict) -> str | None:
    """Remove the next lowest-priority item. Return what was dropped."""
    lines = _lines(edition)
    for index in range(len(lines) - 1, -1, -1):
        if not _is_floor_line(lines[index]):
            lines.pop(index)
            return "almanac detail"

    week = edition.get("this_week")
    if isinstance(week, list) and len(week) > WEEK_FLOOR:
        week.pop()
        return "week row"

    news = edition.get("news")
    if isinstance(news, list) and len(news) > NEWS_FLOOR:
        news.pop()
        return "news row"

    cleared = _clear_description(edition)
    if cleared:
        return cleared

    note = _clear_prep_note(edition)
    if note:
        return note

    prep = edition.get("prep")
    if isinstance(prep, list) and len(prep) > 1:
        prep.pop()
        return "prep note"
    return None


def _lines(edition: dict) -> list:
    almanac = edition.get("almanac")
    if not isinstance(almanac, dict):
        return []
    lines = almanac.get("lines")
    if not isinstance(lines, list):
        return []
    return lines


def _is_floor_line(line: object) -> bool:
    if not isinstance(line, dict):
        return False
    label = str(line.get("label", "")).strip().casefold()
    return label in FLOOR_LABELS


def _clear_prep_note(edition: dict) -> str | None:
    prep = edition.get("prep")
    if not isinstance(prep, list):
        return None
    for index in range(len(prep) - 1, -1, -1):
        item = prep[index]
        if not isinstance(item, dict):
            continue
        note = item.get("note")
        if not isinstance(note, str) or not note:
            continue
        line = item.get("line", "")
        prep[index] = line if isinstance(line, str) else ""
        return "prep note"
    return None


def _clear_description(edition: dict) -> str | None:
    for key in ("news", "today"):
        rows = edition.get(key)
        if not isinstance(rows, list):
            continue
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            if row.get("dek"):
                row.pop("dek", None)
                return "dek"
            if row.get("place"):
                row.pop("place", None)
                return "place"
    return None
