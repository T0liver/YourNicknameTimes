"""Calendar and task blocks from one CalDAV account."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Callable
from urllib.parse import urlparse

from newspaper.http import check_url

HU_WEEKDAYS = (
    "hétfő",
    "kedd",
    "szerda",
    "csütörtök",
    "péntek",
    "szombat",
    "vasárnap",
)
_SKIPPED = {"COMPLETED", "CANCELLED", "CANCELED"}
_DESCRIPTION_LIMIT = 160


@dataclass
class _Item:
    kind: str
    summary: str
    description: str
    place: str
    when: date | None
    clock: str | None
    priority: int
    uid: str
    until: date | None = None


def empty_schedule() -> dict:
    return {"today": [], "this_week": [], "prep": [], "due": [], "overdue": []}


def collect_caldav(
    settings: dict,
    password: str,
    now: datetime,
    *,
    client=None,
    get: Callable | None = None,
) -> tuple[dict, dict]:
    host = str(settings.get("caldav_host") or "").strip()
    if not host:
        return empty_schedule(), {"caldav": "ok"}
    try:
        if client is None:
            if get is None:
                from newspaper.http import get as get
            client = connect(
                host,
                str(settings.get("caldav_username") or ""),
                password,
                get,
            )
        schedule, failed = _read(client, now)
        return schedule, {"caldav": "failed" if failed else "ok"}
    except Exception:
        return empty_schedule(), {"caldav": "failed"}


def connect(url: str, username: str, password: str, get: Callable, client_cls=None):
    check_url(url)
    auth_type = _auth_type(url, get)
    if client_cls is None:
        import caldav

        client_cls = caldav.DAVClient
    return client_cls(
        url=url,
        username=username,
        password=password,
        auth_type=auth_type,
        enable_rfc6764=False,
        require_tls=urlparse(url).scheme.lower() == "https",
        timeout=30,
    )


def _auth_type(url: str, get: Callable) -> str:
    response = get(url, timeout=20)
    headers = getattr(response, "headers", {}) or {}
    header = ""
    if hasattr(headers, "get"):
        header = headers.get("WWW-Authenticate") or headers.get("Www-Authenticate") or ""
    if "digest" in str(header).lower():
        return "digest"
    return "basic"


def _read(client, now: datetime) -> tuple[dict, bool]:
    zone = now.tzinfo
    today = now.date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    end = datetime.combine(today + timedelta(days=8), time.min, tzinfo=zone)
    task_start = datetime(2000, 1, 1, tzinfo=zone)
    events: list[_Item] = []
    tasks: list[_Item] = []
    failed = False
    for calendar in client.principal().calendars():
        try:
            supported = _supported(calendar)
            if "VEVENT" in supported:
                for component in _search(calendar, start=start, end=end, event=True):
                    item = _event(component, zone)
                    if item is not None:
                        events.append(item)
            if "VTODO" in supported:
                seen = list(_search(calendar, start=task_start, end=end, todo=True))
                try:
                    seen.extend(_search(calendar, todo=True))
                except Exception:
                    failed = True
                for component in seen:
                    item = _task(component, zone)
                    if item is not None:
                        tasks.append(item)
        except Exception:
            failed = True
    return _place(events, _current(tasks, today), today), failed


def _search(calendar, **kwargs):
    found = calendar.search(expand=True, **kwargs)
    components = []
    for obj in found:
        components.extend(_components(obj))
    return components


def _supported(calendar) -> set[str]:
    getter = getattr(calendar, "get_supported_components", None)
    if getter is None:
        return {"VEVENT", "VTODO"}
    raw = getter()
    if not raw:
        return {"VEVENT", "VTODO"}
    names = set()
    for item in raw:
        text = str(item).upper()
        for kind in ("VEVENT", "VTODO", "VJOURNAL"):
            if kind in text:
                names.add(kind)
    return names or {"VEVENT", "VTODO"}


def _components(obj) -> list:
    component = getattr(obj, "component", None)
    if component is None:
        component = getattr(obj, "icalendar_component", obj)
    name = getattr(component, "name", "")
    if name == "VCALENDAR":
        return [child for child in component.walk() if getattr(child, "name", "") in {"VEVENT", "VTODO"}]
    if name in {"VEVENT", "VTODO"}:
        return [component]
    return []


def _event(component, zone) -> _Item | None:
    if _status(component) in _SKIPPED:
        return None
    summary = _summary(component)
    if not summary:
        return None
    when, clock = _local(component, "dtstart", zone)
    _touch(component)
    return _Item(
        "event",
        summary,
        _description(component),
        _location(component),
        when,
        clock,
        _priority(component),
        _uid(component),
        _covered_until(component, zone),
    )


def _task(component, zone) -> _Item | None:
    if _status(component) in _SKIPPED:
        return None
    summary = _summary(component)
    if not summary:
        return None
    when, clock = _local(component, "due", zone)
    _touch(component)
    return _Item("task", summary, _description(component), _location(component), when, clock, _priority(component), _uid(component))


def _current(tasks: list[_Item], today: date) -> list[_Item]:
    grouped: dict[str, list[_Item]] = {}
    for task in tasks:
        uid = task.uid or f"{task.summary}|{task.when}|{task.clock}"
        grouped.setdefault(uid, []).append(task)
    chosen = []
    for items in grouped.values():
        unique = []
        seen = set()
        for item in items:
            key = (item.when, item.clock, item.summary)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        picked = _pick(unique, today)
        if picked is not None:
            chosen.append(picked)
    return chosen


def _pick(items: list[_Item], today: date) -> _Item | None:
    dated = [item for item in items if item.when is not None]
    undated = [item for item in items if item.when is None]
    if not dated:
        return undated[0] if undated else None
    on_today = [item for item in dated if item.when == today]
    if on_today:
        return min(on_today, key=_item_key)
    upcoming = [item for item in dated if item.when > today]
    if upcoming:
        return min(upcoming, key=lambda item: (item.when, _item_key(item)))
    return max(dated, key=lambda item: (item.when, item.clock or ""))


def _place(events: list[_Item], tasks: list[_Item], today: date) -> dict:
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    due_start = today + timedelta(days=2)
    today_rows = []
    week_rows = []
    prep_rows = []
    due_rows = []
    overdue_rows = []

    def add_today(item: _Item) -> None:
        today_rows.append((_item_key(item) if item.when is not None else (2, "", 99, item.summary), _today_row(item)))

    def add_week(item: _Item) -> None:
        week_rows.append(((item.when, item.clock or "", item.summary), _week_row(item)))

    def add_prep(item: _Item) -> None:
        prep_rows.append(((item.clock or "", item.summary), _prep_line(item)))

    for item in events:
        if item.when == today or _spans_today(item, today):
            add_today(item if item.when == today else replace(item, when=today, clock=None))
        elif item.when is not None and tomorrow <= item.when <= week_end:
            add_week(item)
            if item.when == tomorrow:
                add_prep(item)
    for item in tasks:
        if item.when is None:
            add_today(item)
            continue
        if item.when == today:
            add_today(item)
        if tomorrow <= item.when <= week_end:
            add_week(item)
        if item.when == tomorrow:
            add_prep(item)
        if due_start <= item.when <= week_end:
            due_rows.append((item.when, item.summary, _due_line(item)))
        if item.when < today:
            overdue_rows.append((item.when, item.summary, _overdue_line(item, today)))

    today_rows.sort(key=lambda pair: pair[0])
    week_rows.sort(key=lambda pair: pair[0])
    prep_rows.sort(key=lambda pair: pair[0])
    due_rows.sort(key=lambda pair: (pair[0], pair[1]))
    overdue_rows.sort(key=lambda pair: (pair[0], pair[1]))
    return {
        "today": [row for _, row in today_rows],
        "this_week": [row for _, row in week_rows],
        "prep": [row for _, row in prep_rows],
        "due": [row for _, _, row in due_rows],
        "overdue": [row for _, _, row in overdue_rows],
    }


def _today_row(item: _Item) -> dict:
    if item.when is None:
        row = {"time": "bármikor", "title": item.summary}
    else:
        row = {"time": item.clock or "egész nap", "title": item.summary}
    if item.place:
        row["place"] = item.place
    if item.description:
        row["dek"] = item.description[:_DESCRIPTION_LIMIT]
    return row


def _week_row(item: _Item) -> dict:
    text = f"{item.clock} {item.summary}".strip() if item.clock else item.summary
    if item.place:
        text = f"{text} ({item.place})"
    row = {"day": _day_name(item.when), "text": text}
    if item.place:
        row["place"] = item.place
    return row


def _prep_line(item: _Item) -> str:
    text = f"{item.clock} {item.summary}".strip() if item.clock else item.summary
    if item.place:
        text = f"{text} ({item.place})"
    if item.description:
        text = f"{text}: {item.description[:_DESCRIPTION_LIMIT]}"
    return text


def _due_line(item: _Item) -> str | dict:
    text = f"{_day_name(item.when)}: {item.summary}"
    if item.description:
        detail = item.description[:_DESCRIPTION_LIMIT]
        return {"text": f"{text}: {detail}", "detail": detail}
    return text


def _overdue_line(item: _Item, today: date) -> str:
    days = (today - item.when).days
    return f"{days} napja lejárt: {item.summary}"


def _day_name(day: date) -> str:
    return HU_WEEKDAYS[day.weekday()].capitalize()


def _item_key(item: _Item):
    if item.when is None:
        return (2, "", item.priority or 99, item.summary)
    if item.clock is None:
        return (0, "", item.priority or 99, item.summary)
    return (1, item.clock, item.priority or 99, item.summary)


def _spans_today(item: _Item, today: date) -> bool:
    return item.when is not None and item.until is not None and item.when < today <= item.until


def _covered_until(component, zone) -> date | None:
    value = _end_value(component)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=zone)
        elif zone is not None:
            value = value.astimezone(zone)
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            return value.date() - timedelta(days=1)
        return value.date()
    if isinstance(value, date):
        return value - timedelta(days=1)
    return None


def _end_value(component):
    prop = component.get("dtend")
    if prop is not None:
        return prop.dt if hasattr(prop, "dt") else prop
    duration = component.get("duration")
    start = component.get("dtstart")
    if duration is None or start is None:
        return None
    start_value = start.dt if hasattr(start, "dt") else start
    delta = duration.dt if hasattr(duration, "dt") else duration
    try:
        return start_value + delta
    except TypeError:
        return None


def _local(component, key: str, zone):
    prop = component.get(key)
    if prop is None:
        return None, None
    value = prop.dt if hasattr(prop, "dt") else prop
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=zone)
        else:
            value = value.astimezone(zone)
        return value.date(), value.strftime("%H:%M")
    if isinstance(value, date):
        return value, None
    return None, None


def _summary(component) -> str:
    raw = component.get("summary")
    return str(raw).strip() if raw else ""


def _description(component) -> str:
    raw = component.get("description")
    if not raw:
        return ""
    return " ".join(str(raw).split())


def _location(component) -> str:
    raw = component.get("location")
    return str(raw).strip() if raw else ""


def _status(component) -> str:
    raw = component.get("status")
    return str(raw or "").strip().upper()


def _priority(component) -> int:
    raw = component.get("priority")
    try:
        return int(raw) if raw not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _uid(component) -> str:
    raw = component.get("uid")
    return str(raw).strip() if raw else ""


def _touch(component) -> None:
    component.get("categories")
