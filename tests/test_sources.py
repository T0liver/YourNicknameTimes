import base64
import hashlib
import json
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image
from icalendar import Event, Todo

from newspaper.db import DEFAULT_SETTINGS, init_data, load_settings, save_settings
from newspaper.edition_build import run
from newspaper.http import UnsafeURL
from newspaper.render import render_html
from newspaper.sources.almanac import MNB_URL, name_day_line, on_this_day_url
from newspaper.sources.caldav_source import collect_caldav, connect
from newspaper.sources.daily import (
    WEEKDAY_GIVENS,
    WEEKEND_GIVENS,
    XKCD_CREDIT,
    collect_daily,
    count_solutions,
    generate_sudoku,
)
from newspaper.sources.news import collect_news, keyword_score, rank_news
from newspaper.sources.weather import forecast_url

ZONE = ZoneInfo("Europe/Budapest")
WHEN = datetime(2026, 10, 14, 9, 55, tzinfo=ZONE)
MONDAY = datetime(2026, 10, 12, 6, 30, tzinfo=ZONE)
SATURDAY = datetime(2026, 10, 17, 8, 0, tzinfo=ZONE)
SUNDAY = datetime(2026, 10, 18, 8, 0, tzinfo=ZONE)
LAT = 47.4979
LON = 19.0402
PASSWORD = "s3cret-token"


class Response:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self.headers = headers or {}
        if isinstance(body, str):
            self.text = body
            self.content = body.encode()
        else:
            self.content = body
            self.text = ""


class Router:
    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, url, body, status=200, headers=None):
        self.routes[url] = Response(status, body, headers)

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        if str(url).startswith("file:"):
            raise AssertionError(url)
        found = self.routes.get(url)
        if found is None:
            raise RuntimeError(url)
        if isinstance(found, Exception):
            raise found
        return found


class Component:
    def __init__(self, component):
        self.component = component


class Calendar:
    def __init__(self, components, supported=("VEVENT", "VTODO")):
        self.components = components
        self.supported = list(supported)
        self.calls = []

    def get_supported_components(self):
        return list(self.supported)

    def search(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs.get("expand") is True
        want_event = kwargs.get("event")
        want_todo = kwargs.get("todo")
        found = []
        for component in self.components:
            name = component.name
            if want_event and name != "VEVENT":
                continue
            if want_todo and name != "VTODO":
                continue
            found.append(Component(component))
        return found


class Client:
    def __init__(self, calendars):
        self._calendars = calendars

    def principal(self):
        return self

    def calendars(self):
        return self._calendars


class BrokenCalendar:
    def get_supported_components(self):
        return ["VEVENT"]

    def search(self, **kwargs):
        raise RuntimeError("calendar down")


def _write_ok(edition, path):
    path.write_bytes(b"%PDF-1.4\n")
    return 1


def _png(width, height, color=(20, 80, 140)):
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _rss(items):
    rows = []
    for item in items:
        rows.append(
            "<item>"
            f"<title>{item['title']}</title>"
            f"<link>{item['link']}</link>"
            f"<description>{item.get('description', '')}</description>"
            f"<pubDate>{item['pubDate']}</pubDate>"
            "</item>"
        )
    return (
        "<?xml version='1.0'?>"
        "<rss version='2.0'><channel><title>Feed</title>"
        + "".join(rows)
        + "</channel></rss>"
    )


def _event(uid, summary, start, place="", description=""):
    event = Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstart", start)
    if place:
        event.add("location", place)
    if description:
        event.add("description", description)
    return event


def _todo(uid, summary, due=None, status=None, description="", priority=None, categories=None):
    todo = Todo()
    todo.add("uid", uid)
    todo.add("summary", summary)
    if due is not None:
        todo.add("due", due)
    if status:
        todo.add("status", status)
    if description:
        todo.add("description", description)
    if priority is not None:
        todo.add("priority", priority)
    if categories:
        todo.add("categories", categories)
    return todo


def _prepare(tmp_path, **changes):
    data = tmp_path / "data"
    conn = init_data(data)
    try:
        body = load_settings(conn)
        body.update(changes)
        save_settings(conn, body)
    finally:
        conn.close()
    return data


def _read(data: Path, day: str) -> dict:
    return json.loads((data / "editions" / day / "edition.json").read_text(encoding="utf-8"))


def _weather_body():
    return json.dumps(
        {
            "daily": {
                "time": ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"],
                "weather_code": [0, 3, 61, 80, 2],
                "temperature_2m_max": [22.2, 19.4, 18.2, 17.6, 16.1],
                "temperature_2m_min": [11.1, 10.2, 9.4, 8.6, 7.7],
            }
        }
    )


def _wiki(text, pages):
    return json.dumps({"selected": [{"text": text, "pages": [{} for _ in range(pages)]}]})


def _mnb(rate_date="2026-10-14"):
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<MNBCurrentExchangeRates xmlns='http://www.mnb.hu/webservices/'>"
        f"<Day date='{rate_date}'>"
        "<Rate unit='1' curr='EUR'>395,12</Rate>"
        "<Rate unit='1' curr='USD'>362,40</Rate>"
        "<Rate unit='1' curr='CHF'>421,05</Rate>"
        "<Rate unit='1' curr='GBP'>450,00</Rate>"
        "</Day></MNBCurrentExchangeRates>"
    )


def _xkcd_routes(router, comics):
    router.add("https://xkcd.com/info.0.json", json.dumps({"num": max(comics)}))
    for comic_id, info, image in comics.values():
        router.add(f"https://xkcd.com/{comic_id}/info.0.json", json.dumps(info))
        if image is not None:
            router.add(info["img"], image)


def _full_router():
    router = Router()
    router.add(
        "https://news.example/interest",
        _rss(
            [
                {
                    "title": "A lab note on music hardware",
                    "link": "https://news.example/a",
                    "pubDate": "Wed, 14 Oct 2026 06:00:00 GMT",
                },
                {
                    "title": "A lab note on music hardware!",
                    "link": "https://news.example/a-twin",
                    "pubDate": "Wed, 14 Oct 2026 06:05:00 GMT",
                },
                {
                    "title": "Old wire story",
                    "link": "https://news.example/old",
                    "pubDate": "Mon, 12 Oct 2026 06:00:00 GMT",
                },
            ]
        ),
    )
    router.add(
        "https://news.example/local",
        _rss(
            [
                {
                    "title": "Same bridge story",
                    "link": "https://news.example/b",
                    "pubDate": "Wed, 14 Oct 2026 05:30:00 GMT",
                },
                {
                    "title": "Hídnyitás a pesti rakparton",
                    "link": "https://news.example/b",
                    "pubDate": "Wed, 14 Oct 2026 05:40:00 GMT",
                },
            ]
        ),
    )
    router.add(forecast_url(LAT, LON, "Europe/Budapest"), _weather_body())
    _xkcd_routes(
        router,
        {
            1: (
                1,
                {
                    "extra_parts": {"head": "interactive"},
                    "img": "https://imgs.xkcd.com/1.png",
                    "alt": "skip me",
                },
                _png(80, 80),
            ),
            2: (
                2,
                {"img": "https://imgs.xkcd.com/2.png", "alt": "too wide"},
                _png(1500, 100),
            ),
            3: (
                3,
                {"img": "https://imgs.xkcd.com/3.png", "alt": "too tall"},
                _png(100, 400),
            ),
            4: (
                4,
                {"img": "https://imgs.xkcd.com/4.png", "alt": "A plain caption"},
                _png(120, 80),
            ),
        },
    )
    router.add(on_this_day_url("hu", WHEN.date()), _wiki("Megnyílt a budapesti híd.", 2))
    router.add(MNB_URL, _mnb())
    return router


def _feeds(conn):
    conn.execute("UPDATE feeds SET enabled = 0")
    conn.executemany(
        """
        INSERT INTO feeds (name, url, category, language, weight, max_items, enabled)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        [
            ("Interest", "https://news.example/interest", "interest", "en", 1, 20),
            ("Local", "https://news.example/local", "local", "hu", 1, 20),
        ],
    )
    conn.commit()


def _calendars():
    zone = ZONE
    day = WHEN.date()
    return [
        Calendar(
            [
                _event(
                    "meet",
                    "Csapatmegbeszélés",
                    datetime(2026, 10, 14, 9, 0, tzinfo=zone),
                    place="Iroda",
                ),
                _event("train", "Vonat", datetime(2026, 10, 15, 7, 40, tzinfo=zone)),
                _event("dentist", "Fogorvos", datetime(2026, 10, 16, 14, 0, tzinfo=zone)),
                _event("edge", "Határnap", datetime(2026, 10, 21, 11, 0, tzinfo=zone)),
                _event("later", "Túl messze", datetime(2026, 10, 22, 11, 0, tzinfo=zone)),
            ],
            supported=("VEVENT",),
        ),
        Calendar(
            [
                _todo("report", "Jelentés", datetime(2026, 10, 14, 18, 0, tzinfo=zone), description="Rövid leírás", priority=1, categories=["munka"]),
                _todo("pack", "Csomag", datetime(2026, 10, 15, 12, 0, tzinfo=zone), description="átvenni"),
                _todo("contract", "Szerződés", date(2026, 10, 16)),
                _todo("tax", "Adó", date(2026, 10, 10)),
                _todo("old", "Régi", date(2026, 10, 12)),
                _todo("files", "Iratok"),
                _todo("done", "Kész", datetime(2026, 10, 14, 8, 0, tzinfo=zone), status="COMPLETED"),
                _todo("cancelled", "Törölt", date(2026, 10, 14), status="CANCELLED"),
                _todo("recur", "Ismétlődő", date(2026, 10, 14)),
                _todo("recur", "Ismétlődő", date(2026, 10, 16)),
            ],
            supported=("VTODO",),
        ),
        Calendar([], supported=("VJOURNAL",)),
    ]


def test_keyword_scores_and_light_mood_break_a_tie():
    assert keyword_score("háború a kertben", "local", light=False) == 1
    assert keyword_score("háború a kertben", "interest", light=False) == 0
    assert keyword_score("kert háború", "interest", light=True) == 1
    assert keyword_score("crash", "interest", light=False) == -1
    assert keyword_score("crash", "local", light=True) == 0
    published = WHEN
    plain = {
        "title": "Városi hír",
        "url": "https://news.example/plain",
        "snippet": "",
        "published": published,
        "weight": 1,
        "category": "interest",
        "feed": "Interest",
    }
    hobby = {
        **plain,
        "title": "kert háború",
        "url": "https://news.example/hobby",
    }
    neutral = [row["headline"] for row in rank_news([plain, hobby], light=False)]
    light = [row["headline"] for row in rank_news([plain, hobby], light=True)]
    assert neutral == ["Városi hír", "kert háború"]
    assert light == ["kert háború", "Városi hír"]


def test_rank_uses_recency_then_weight_then_keeps_four_of_each():
    newer = WHEN
    older = WHEN - timedelta(hours=2)
    def title(prefix, index):
        return f"{prefix}-{hashlib.sha1(f'{prefix}{index}'.encode()).hexdigest()}"

    items = []
    for index in range(5):
        items.append(
            {
                "title": title("interest", index),
                "url": f"https://news.example/i{index}",
                "snippet": "",
                "published": newer if index == 0 else older,
                "weight": 1 if index else 9,
                "category": "interest",
                "feed": "Interest",
            }
        )
        items.append(
            {
                "title": title("local", index),
                "url": f"https://news.example/l{index}",
                "snippet": "",
                "published": older,
                "weight": index,
                "category": "local",
                "feed": "Local",
            }
        )
    rows = rank_news(items, light=False)
    headlines = [row["headline"] for row in rows]
    assert len([row for row in rows if row["publisher"] == "Interest"]) == 4
    assert len([row for row in rows if row["publisher"] == "Local"]) == 4
    assert headlines[0] == title("interest", 0)
    assert title("interest", 4) not in headlines


def test_pool_caps_at_eighty_before_the_quota():
    items = [
        {
            "title": hashlib.sha1(f"story-{index}".encode()).hexdigest(),
            "url": f"https://news.example/{index}",
            "snippet": "",
            "published": WHEN - timedelta(minutes=index),
            "weight": 1,
            "category": "interest",
            "feed": "Interest",
        }
        for index in range(80)
    ]
    items.append(
        {
            "title": "Local leftover",
            "url": "https://news.example/local-old",
            "snippet": "",
            "published": WHEN - timedelta(days=1),
            "weight": 9,
            "category": "local",
            "feed": "Local",
        }
    )
    rows = rank_news(items, light=False)
    assert [row["headline"] for row in rows] == [
        hashlib.sha1(f"story-{index}".encode()).hexdigest() for index in range(4)
    ]
    assert all(row["publisher"] == "Interest" for row in rows)


def test_undated_items_and_the_day_window(tmp_path):
    data = _prepare(tmp_path)
    conn = init_data(data)
    try:
        _feeds(conn)
        conn.execute("DELETE FROM feeds WHERE name IN ('Interest', 'Local')")
        conn.execute(
            """
            INSERT INTO feeds (name, url, category, language, weight, max_items, enabled)
            VALUES ('Only', 'https://news.example/only', 'interest', 'en', 1, 20, 1)
            """
        )
        conn.commit()
        body = _rss(
            [
                {
                    "title": "Fresh",
                    "link": "https://news.example/fresh",
                    "pubDate": "Wed, 14 Oct 2026 06:00:00 GMT",
                },
                {
                    "title": "Stale",
                    "link": "https://news.example/stale",
                    "pubDate": "Tue, 13 Oct 2026 05:00:00 GMT",
                },
                {
                    "title": "No date",
                    "link": "https://news.example/none",
                    "pubDate": "",
                },
            ]
        )
    finally:
        conn.close()
    router = Router()
    router.add("https://news.example/only", body)
    conn = init_data(data)
    try:
        from newspaper.db import load_feeds

        dropped = collect_news(load_feeds(conn), now=WHEN, keep_undated=False, light=False, get=router)
        kept = collect_news(load_feeds(conn), now=WHEN, keep_undated=True, light=False, get=router)
    finally:
        conn.close()
    assert [row["headline"] for row in dropped[0]] == ["Fresh"]
    assert [row["headline"] for row in kept[0]] == ["Fresh", "No date"]
    assert kept[0][1]["time"] == ""


def test_full_collect_matches_the_payloads_and_the_pdf_reads_that_json(tmp_path):
    data = _prepare(
        tmp_path,
        latitude=LAT,
        longitude=LON,
        city="Budapest",
        caldav_host="https://cal.example/dav/",
    )
    (data / "secrets.env").write_text(f"CALDAV_PASSWORD={PASSWORD}\n")
    conn = init_data(data)
    try:
        _feeds(conn)
    finally:
        conn.close()
    router = _full_router()
    calendars = _calendars()
    seen = []

    def render(edition, path):
        seen.append(edition)
        path.write_bytes(b"%PDF-1.4\n")
        return 1

    assert run(data, now=WHEN, render_pdf=render, get=router, client=Client(calendars)) == 0
    written = _read(data, "2026-10-14")
    assert seen == [written]
    assert written["meta"]["mode"] == "off"
    assert written["meta"]["model"] is None
    assert PASSWORD not in json.dumps(written)
    assert [row["headline"] for row in written["news"]] == [
        "A lab note on music hardware!",
        "Hídnyitás a pesti rakparton",
    ]
    assert written["news"][1]["publisher"] == "Local"
    assert written["news"][1]["time"] == "07:40"
    assert {"time": "09:00", "title": "Csapatmegbeszélés", "place": "Iroda"} in written["today"]
    mentions = [row["title"] for row in written["today"]]
    mentions += [row["text"] for row in written["this_week"]]
    mentions += written["due"]
    assert sum("Ismétlődő" in text for text in mentions) == 1
    assert {"time": "18:00", "title": "Jelentés", "dek": "Rövid leírás"} in written["today"]
    assert {"time": "bármikor", "title": "Iratok"} in written["today"]
    assert not any("Kész" in json.dumps(row) for row in written["today"])
    assert not any("Törölt" in json.dumps(block) for block in written.values() if block)
    assert written["prep"] == ["07:40 Vonat", "12:00 Csomag: átvenni"]
    assert {"day": "Péntek", "text": "14:00 Fogorvos"} in written["this_week"]
    assert {"day": "Szerda", "text": "11:00 Határnap"} in written["this_week"]
    assert all("Túl messze" not in row["text"] for row in written["this_week"])
    assert "Ismétlődő" not in json.dumps(written["due"])
    assert written["due"] == ["Péntek: Szerződés"]
    assert written["overdue"] == ["4 napja lejárt: Adó", "2 napja lejárt: Régi"]
    assert written["weather"]["summary"] == "Derült"
    assert written["weather"]["high"] == "22°"
    assert written["weather"]["low"] == "11°"
    assert written["weather"]["outlook"] == [
        {"day": "Cs", "text": "Borult", "temps": "19 / 10"},
        {"day": "P", "text": "Enyhe eső", "temps": "18 / 9"},
        {"day": "Szo", "text": "Zápor", "temps": "18 / 9"},
        {"day": "V", "text": "Részben felhős", "temps": "16 / 8"},
    ]
    assert written["daily_item"]["kind"] == "xkcd"
    assert written["daily_item"]["alt"] == "A plain caption"
    assert written["daily_item"]["credit"] == XKCD_CREDIT
    encoded = written["daily_item"]["src"].split(",", 1)[1]
    image = Image.open(BytesIO(base64.b64decode(encoded)))
    assert image.mode == "L"
    labels = [line["label"] for line in written["almanac"]["lines"]]
    assert labels[:3] == ["Nap", "Hold", "Névnap"]
    assert written["almanac"]["lines"][0]["text"] == "Kel 07:01, nyugszik 17:57"
    assert written["almanac"]["lines"][1]["text"] == "Növekvő sarló, 15%"
    assert written["almanac"]["lines"][2]["text"] == "Helén · froccsos/nevnapok-json"
    assert written["almanac"]["lines"][3]["text"] == "Megnyílt a budapesti híd. · Wikipedia (CC BY-SA)"
    assert written["almanac"]["lines"][-1]["text"] == "EUR 395,12, USD 362,40, CHF 421,05 · 2026-10-14 · MNB"
    assert "450,00" not in written["almanac"]["lines"][-1]["text"]
    assert written["meta"]["sources"]["caldav"] == "ok"
    assert calendars[2].calls == []
    assert calendars[0].calls and all(call.get("expand") is True for call in calendars[0].calls)
    assert calendars[1].calls and all(call.get("expand") is True for call in calendars[1].calls)
    assert written["meta"]["sources"]["feeds"] == {"Interest": "ok", "Local": "ok"}
    assert written["meta"]["sources"]["weather"] == "ok"
    assert written["meta"]["sources"]["xkcd"] == "ok"
    conn = init_data(data)
    try:
        assert conn.execute("SELECT item_key FROM puzzle_history").fetchone()["item_key"] == "4"
        rates = conn.execute(
            "SELECT currency, rate, rate_date FROM rate_history ORDER BY currency"
        ).fetchall()
        assert [(row["currency"], row["rate"], row["rate_date"]) for row in rates] == [
            ("CHF", "421,05", "2026-10-14"),
            ("EUR", "395,12", "2026-10-14"),
            ("USD", "362,40", "2026-10-14"),
        ]
    finally:
        conn.close()
    assert not any(call.startswith("file:") for call in router.calls)
    assert "https://telex.hu/rss" not in Path(collect_news.__code__.co_filename).read_text(encoding="utf-8")
    assert "wired.com" not in Path(collect_news.__code__.co_filename).read_text(encoding="utf-8")


def test_weather_failure_omits_numbers_and_leaves_the_other_blocks(tmp_path):
    data = _prepare(tmp_path, latitude=LAT, longitude=LON, caldav_host="https://cal.example/dav/")
    conn = init_data(data)
    try:
        _feeds(conn)
    finally:
        conn.close()
    router = _full_router()
    router.add(forecast_url(LAT, LON, "Europe/Budapest"), "", status=500)
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=Client([_calendars()[0]])) == 0
    written = _read(data, "2026-10-14")
    assert written["weather"] == {"summary": "Forecast unavailable", "outlook": []}
    assert not any(character.isdigit() for character in written["weather"]["summary"])
    assert written["news"]
    assert written["today"]
    assert written["meta"]["sources"]["weather"] == "failed"
    assert written["meta"]["mode"] == "off"


def test_xkcd_failure_on_monday_prints_sudoku_and_the_run_continues(tmp_path):
    data = _prepare(tmp_path)
    conn = init_data(data)
    try:
        _feeds(conn)
    finally:
        conn.close()
    router = Router()
    router.add(
        "https://news.example/local",
        _rss(
            [
                {
                    "title": "Reggeli hír",
                    "link": "https://news.example/m",
                    "pubDate": "Mon, 12 Oct 2026 04:00:00 GMT",
                }
            ]
        ),
    )
    router.routes["https://xkcd.com/info.0.json"] = RuntimeError("xkcd down")
    assert run(data, now=MONDAY, render_pdf=_write_ok, get=router, client=Client([])) == 0
    written = _read(data, "2026-10-12")
    assert written["daily_item"]["kind"] == "sudoku"
    assert written["daily_item"]["large"] is False
    assert count_solutions(written["daily_item"]["grid"]) == 1
    assert written["news"][0]["headline"] == "Reggeli hír"
    assert written["meta"]["sources"]["xkcd"] == "failed"
    assert (data / "editions" / "2026-10-12" / "print.pdf").is_file()


def test_empty_hungarian_on_this_day_uses_english_and_logs_the_fallback(tmp_path):
    data = _prepare(tmp_path)
    router = Router()
    router.add(on_this_day_url("hu", WHEN.date()), json.dumps({"selected": []}))
    router.add(
        on_this_day_url("en", WHEN.date()),
        _wiki("The aqueduct at Segovia was completed.", 3),
    )
    router.add(MNB_URL, _mnb())
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=Client([])) == 0
    written = _read(data, "2026-10-14")
    texts = [line["text"] for line in written["almanac"]["lines"] if line["label"] == "Ezen a napon"]
    assert texts == ["The aqueduct at Segovia was completed. · Wikipedia (CC BY-SA)"]
    log = (data / "editions" / "2026-10-14" / "run.log").read_text(encoding="utf-8")
    assert "on this day: English fallback" in log
    assert on_this_day_url("hu", WHEN.date()) in router.calls
    assert on_this_day_url("en", WHEN.date()) in router.calls


def test_sunday_rates_keep_fridays_published_date(tmp_path):
    data = _prepare(tmp_path)
    router = Router()
    router.add(on_this_day_url("hu", SUNDAY.date()), json.dumps({"selected": []}))
    router.add(on_this_day_url("en", SUNDAY.date()), json.dumps({"selected": []}))
    router.add(MNB_URL, _mnb("2026-10-16"))
    assert run(data, now=SUNDAY, render_pdf=_write_ok, get=router, client=Client([])) == 0
    written = _read(data, "2026-10-18")
    rate_line = next(line["text"] for line in written["almanac"]["lines"] if line["label"] == "Árfolyam")
    assert "2026-10-16" in rate_line
    assert "MNB" in rate_line
    assert "2026-10-18" not in rate_line
    assert "450" not in rate_line
    assert "395,12" in rate_line


def test_file_feed_is_not_requested_and_marked_failed(tmp_path):
    data = _prepare(tmp_path)
    conn = init_data(data)
    try:
        conn.execute("UPDATE feeds SET enabled = 0")
        conn.execute(
            """
            INSERT INTO feeds (name, url, category, language, weight, max_items, enabled)
            VALUES
                ('Odd', 'file:///tmp/feed.xml', 'local', 'hu', 1, 20, 1),
                ('Local', 'https://news.example/local', 'local', 'hu', 1, 20, 1)
            """
        )
        conn.commit()
    finally:
        conn.close()
    router = Router()
    router.add(
        "https://news.example/local",
        _rss(
            [
                {
                    "title": "Élő hír",
                    "link": "https://news.example/live",
                    "pubDate": "Wed, 14 Oct 2026 06:00:00 GMT",
                }
            ]
        ),
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=Client([])) == 0
    written = _read(data, "2026-10-14")
    assert written["meta"]["sources"]["feeds"]["Odd"] == "failed"
    assert written["meta"]["sources"]["feeds"]["Local"] == "ok"
    assert written["news"][0]["headline"] == "Élő hír"
    assert all(not str(call).startswith("file:") for call in router.calls)


def test_saturday_with_the_switch_on_has_the_weekend_touches(tmp_path):
    data = _prepare(tmp_path, weekend_edition=True, weekend_mood="light", show_sun=True)
    assert run(data, now=SATURDAY, render_pdf=_write_ok) == 0
    written = _read(data, "2026-10-17")
    html = render_html(written)
    givens = sum(1 for row in written["daily_item"]["grid"] for cell in row if cell)
    assert written["weekend"] is True
    assert written["daily_item"]["kind"] == "sudoku"
    assert written["daily_item"]["large"] is True
    assert givens == WEEKEND_GIVENS
    assert count_solutions(written["daily_item"]["grid"]) == 1
    assert "weekend-sun.svg" in html
    assert "Yippie, weekend! You earned it!" in html
    assert "band-tight" in html
    assert "sudoku-large" in html


def test_saturday_with_the_switch_off_skips_the_weekend_touches(tmp_path):
    data = _prepare(tmp_path, weekend_edition=False, weekend_mood="light", show_sun=True)
    assert run(data, now=SATURDAY, render_pdf=_write_ok) == 0
    written = _read(data, "2026-10-17")
    html = render_html(written)
    givens = sum(1 for row in written["daily_item"]["grid"] for cell in row if cell)
    assert written["weekend"] is False
    assert written["daily_item"]["kind"] == "sudoku"
    assert written["daily_item"]["large"] is False
    assert givens == WEEKDAY_GIVENS
    assert givens < WEEKEND_GIVENS
    assert "weekend-sun" not in html
    assert "Yippie, weekend! You earned it!" not in html
    assert "band-tight" not in html
    assert "sudoku-large" not in html


def test_sudoku_stays_unique_and_weekdays_have_fewer_givens():
    import random

    for seed in range(4):
        rng = random.Random(seed)
        weekend = generate_sudoku(rng, WEEKEND_GIVENS)
        weekday = generate_sudoku(rng, WEEKDAY_GIVENS)
        assert sum(cell != 0 for row in weekend for cell in row) == WEEKEND_GIVENS
        assert sum(cell != 0 for row in weekday for cell in row) == WEEKDAY_GIVENS
        assert count_solutions(weekend) == 1
        assert count_solutions(weekday) == 1


def test_xkcd_skips_interactive_wide_and_tall_comics(tmp_path):
    data = _prepare(tmp_path)
    conn = init_data(data)
    try:
        settings = load_settings(conn)
        router = Router()
        _xkcd_routes(
            router,
            {
                1: (
                    1,
                    {"extra_parts": {"head": "x"}, "img": "https://imgs.xkcd.com/1.png", "alt": "interactive"},
                    _png(40, 40),
                ),
            },
        )
        comic, status = collect_daily(settings, WHEN, weekend=False, conn=conn, get=router)
        assert comic["kind"] == "sudoku"
        assert status["xkcd"] == "failed"

        router = Router()
        _xkcd_routes(
            router,
            {
                2: (2, {"img": "https://imgs.xkcd.com/2.png", "alt": "wide"}, _png(1401, 100)),
            },
        )
        comic, status = collect_daily(settings, WHEN, weekend=False, conn=conn, get=router)
        assert status["xkcd"] == "failed"

        router = Router()
        _xkcd_routes(
            router,
            {
                8: (8, {"img": "https://imgs.xkcd.com/8.png", "alt": "aspect"}, _png(230, 100)),
            },
        )
        comic, status = collect_daily(settings, WHEN, weekend=False, conn=conn, get=router)
        assert comic["kind"] == "sudoku"

        conn.execute("INSERT INTO puzzle_history (kind, item_key, used_on) VALUES ('xkcd', '4', '2026-10-01')")
        conn.commit()
        router = Router()
        _xkcd_routes(
            router,
            {
                4: (4, {"img": "https://imgs.xkcd.com/4.png", "alt": "seen"}, _png(80, 80)),
                5: (5, {"img": "https://imgs.xkcd.com/5.png", "alt": "fresh caption"}, _png(90, 70)),
            },
        )
        comic, status = collect_daily(settings, WHEN, weekend=False, conn=conn, get=router)
        assert status["xkcd"] == "ok"
        assert status["xkcd_id"] == "5"
        assert comic["alt"] == "fresh caption"
        assert "id" not in comic
        keys = {row["item_key"] for row in conn.execute("SELECT item_key FROM puzzle_history")}
        assert "5" not in keys
        assert "https://xkcd.com/4/info.0.json" not in router.calls
    finally:
        conn.close()


def test_a_failed_calendar_keeps_the_events_already_read():
    calendar = Calendar(
        [_event("meet", "Csapatmegbeszélés", datetime(2026, 10, 14, 9, 0, tzinfo=ZONE), place="Iroda")],
        supported=("VEVENT",),
    )
    settings = {**DEFAULT_SETTINGS, "caldav_host": "https://cal.example/dav/"}
    blocks, status = collect_caldav(
        settings,
        "",
        WHEN,
        client=Client([calendar, BrokenCalendar()]),
    )
    assert status["caldav"] == "failed"
    assert blocks["today"] == [{"time": "09:00", "title": "Csapatmegbeszélés", "place": "Iroda"}]


def test_file_caldav_host_makes_no_request():
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        raise AssertionError(url)

    settings = {**DEFAULT_SETTINGS, "caldav_host": "file:///tmp/dav"}
    blocks, status = collect_caldav(settings, PASSWORD, WHEN, get=get)
    assert calls == []
    assert status["caldav"] == "failed"
    assert blocks["today"] == []


def test_caldav_auth_is_basic_or_digest():
    built = {}

    class FakeClient:
        def __init__(self, **kwargs):
            built.update(kwargs)

    def digest_get(url, **kwargs):
        return Response(401, "", headers={"WWW-Authenticate": 'Digest realm="dav", nonce="abc"'})

    connect("https://cal.example/dav/", "ada", PASSWORD, digest_get, client_cls=FakeClient)
    assert built["auth_type"] == "digest"
    assert built["username"] == "ada"
    assert built["password"] == PASSWORD
    assert built["require_tls"] is True
    assert built["enable_rfc6764"] is False

    def basic_get(url, **kwargs):
        return Response(401, "", headers={"WWW-Authenticate": 'Basic realm="dav"'})

    connect("http://cal.example/dav/", "ada", PASSWORD, basic_get, client_cls=FakeClient)
    assert built["auth_type"] == "basic"
    assert built["require_tls"] is False

    def both_get(url, **kwargs):
        return Response(401, "", headers={"WWW-Authenticate": 'Basic realm="dav", Digest realm="dav"'})

    connect("https://cal.example/dav/", "ada", PASSWORD, both_get, client_cls=FakeClient)
    assert built["auth_type"] == "digest"

    try:
        connect("file:///tmp/dav", "ada", PASSWORD, digest_get, client_cls=FakeClient)
    except UnsafeURL:
        pass
    else:
        raise AssertionError("file URL was accepted")


def test_run_passes_the_caldav_password(tmp_path, monkeypatch):
    seen = {}

    def fake_connect(url, username, password, get, client_cls=None):
        seen["url"] = url
        seen["username"] = username
        seen["password"] = password
        return Client([])

    monkeypatch.setattr("newspaper.sources.caldav_source.connect", fake_connect)
    data = _prepare(tmp_path, caldav_host="https://cal.example/dav/", caldav_username="ada")
    (data / "secrets.env").write_text(f"CALDAV_PASSWORD={PASSWORD}\n")
    router = Router()
    router.add(on_this_day_url("hu", WHEN.date()), json.dumps({"selected": []}))
    router.add(on_this_day_url("en", WHEN.date()), json.dumps({"selected": []}))
    router.add(MNB_URL, "<not-xml")
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router) == 0
    assert seen == {
        "url": "https://cal.example/dav/",
        "username": "ada",
        "password": PASSWORD,
    }
    written = _read(data, "2026-10-14")
    assert PASSWORD not in json.dumps(written)
    assert "Árfolyam" not in json.dumps(written["almanac"])


def test_name_day_uses_the_vendored_main_names_and_skips_a_blank_day():
    assert name_day_line(date(2026, 10, 14)) == "Helén · froccsos/nevnapok-json"
    assert name_day_line(date(2024, 2, 29)) is None
    assert name_day_line(date(2026, 12, 8)) is None
    license_text = Path("newspaper/data/nevnapok-LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Copyright (c) 2020 Belső Dániel" in license_text


def test_missing_coordinates_omit_sun_moon_and_weather(tmp_path):
    data = _prepare(tmp_path)
    router = Router()
    router.add(on_this_day_url("hu", WHEN.date()), json.dumps({"selected": []}))
    router.add(on_this_day_url("en", WHEN.date()), json.dumps({"selected": []}))
    router.add(MNB_URL, _mnb())
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=Client([])) == 0
    written = _read(data, "2026-10-14")
    assert written["weather"] is None
    labels = [line["label"] for line in written["almanac"]["lines"]]
    assert "Nap" not in labels
    assert "Hold" not in labels
    assert "open-meteo.com" not in "".join(router.calls)


def test_collectors_do_not_import_the_smoke_scripts_or_call_a_shell():
    root = Path("newspaper")
    for path in list(root.glob("*.py")) + list((root / "sources").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "scripts.smoke" not in text
        assert "scripts/smoke" not in text
        assert "subprocess" not in text
        assert "os.system" not in text
