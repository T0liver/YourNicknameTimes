"""Model calls stay on a fake poster. Nothing here reaches OpenRouter."""

import json
from datetime import datetime
from pathlib import Path

import pytest
import requests

from newspaper.db import init_data, load_settings, save_settings
from newspaper.edition_build import run
from newspaper.http import post
from newspaper.llm import API_URL
from newspaper.render import render_html
from tests.test_sources import (
    SATURDAY,
    WHEN,
    ZONE,
    Calendar,
    Client,
    Router,
    _event,
    _rss,
    _write_ok,
)

WIRED = "https://www.wired.com/feed/rss"
TELEX = "https://telex.hu/rss"
INTEREST = "https://news.example/interest"


class Reply:
    def __init__(self, content, model="openrouter/free", status=200, reasoning=None):
        self.status_code = status
        self.is_redirect = status in {301, 302, 303, 307, 308}
        message = {"content": content}
        if reasoning is not None:
            message["reasoning"] = reasoning
        body = {"choices": [{"message": message}]}
        if model is not None:
            body["model"] = model
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class Poster:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.replies:
            raise AssertionError(url)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _picks(*rows, model="news-model"):
    body = {"picks": [{"id": picked_id, "category": category} for picked_id, category in rows]}
    return Reply(json.dumps(body), model=model)


def _notes(*rows, model="plan-model"):
    body = {"notes": [{"id": note_id, "note": text} for note_id, text in rows]}
    return Reply(json.dumps(body), model=model)


def _data(tmp_path, secret="OPENROUTER_API_KEY=sk-test\n", **changes):
    data = tmp_path / "data"
    conn = init_data(data)
    try:
        if changes:
            body = load_settings(conn)
            body.update(changes)
            save_settings(conn, body)
    finally:
        conn.close()
    (data / "secrets.env").write_text(secret, encoding="utf-8")
    return data


def _interest(data, count):
    conn = init_data(data)
    try:
        conn.execute("UPDATE feeds SET enabled = 0")
        conn.execute(
            """
            INSERT INTO feeds (name, url, category, language, weight, max_items, enabled)
            VALUES ('Interest', ?, 'interest', 'en', 1, 20, 1)
            """,
            (INTEREST,),
        )
        conn.commit()
    finally:
        conn.close()
    items = []
    for index in range(1, count + 1):
        hour = 8 - index
        items.append(
            {
                "title": f"Story {index}",
                "link": f"https://news.example/{index}",
                "description": "",
                "pubDate": f"Wed, 14 Oct 2026 0{hour}:00:00 GMT",
            }
        )
    router = Router()
    router.add(INTEREST, _rss(items))
    return router


def _feeds():
    router = Router()
    router.add(
        WIRED,
        _rss(
            [
                {
                    "title": "Lab note",
                    "link": "https://wired.example/lab",
                    "description": "a snippet",
                    "pubDate": "Wed, 14 Oct 2026 06:00:00 GMT",
                }
            ]
        ),
    )
    router.add(
        TELEX,
        _rss(
            [
                {
                    "title": "Híd",
                    "link": "https://telex.example/hid",
                    "description": "helyi",
                    "pubDate": "Wed, 14 Oct 2026 05:00:00 GMT",
                }
            ]
        ),
    )
    return router


def _train(description="jegyet venni"):
    return Client(
        [
            Calendar(
                [
                    _event(
                        "train",
                        "Vonat",
                        datetime(2026, 10, 15, 7, 40, tzinfo=ZONE),
                        description=description,
                    )
                ],
                supported=("VEVENT",),
            )
        ]
    )


def _read(data, day="2026-10-14"):
    return json.loads((data / "editions" / day / "edition.json").read_text(encoding="utf-8"))


def _llm(data, name, day="2026-10-14"):
    return json.loads((data / "editions" / day / "llm" / name).read_text(encoding="utf-8"))


def test_requests_post_is_blocked():
    with pytest.raises(requests.ConnectionError):
        post(API_URL)


def test_valid_picks_and_notes_are_stored_with_the_feed_row(tmp_path):
    data = _data(tmp_path, caldav_host="https://cal.example/dav/")
    poster = Poster(
        [
            _picks((1, "interest"), model="news-model"),
            _notes((1, "Vedd a jegyet."), model="plan-model"),
        ]
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), client=_train(), post=poster) == 0
    written = _read(data)
    assert written["news"] == [{"headline": "Lab note", "publisher": "Wired", "time": "08:00"}]
    assert written["prep"] == [{"line": "07:40 Vonat: jegyet venni", "note": "Vedd a jegyet."}]
    assert written["meta"]["mode"] == "on"
    assert written["meta"]["model"] == "news-model, plan-model"
    assert "model" not in written["meta"]["sources"]
    news = _llm(data, "news.json")
    planner = _llm(data, "planner.json")
    assert news[0]["model"] == "news-model"
    assert "Lab note" in news[0]["prompt"]
    assert "a snippet" in news[0]["prompt"]
    assert "Mood: normal" in news[0]["prompt"]
    assert json.loads(news[0]["response"])["model"] == "news-model"
    assert "jegyet venni" in planner[0]["prompt"]
    assert "Vedd a jegyet." in planner[0]["response"]
    assert planner[0]["model"] == "plan-model"
    assert _llm(data, "requests.json") == {"count": 2}
    assert [call[0] for call in poster.calls] == [API_URL, API_URL]
    assert poster.calls[0][1]["timeout"] == 60
    assert poster.calls[0][1]["headers"]["Authorization"] == "Bearer sk-test"
    html = render_html(written)
    assert html.index("07:40 Vonat: jegyet venni") < html.index("Vedd a jegyet.")


def test_a_schema_miss_retries_once_and_uses_the_second_body(tmp_path):
    data = _data(tmp_path, caldav_host="https://cal.example/dav/")
    poster = Poster(
        [
            Reply("not json", model="draft-model"),
            _picks((2, "local"), model="news-model"),
            _notes((1, "Vedd a jegyet."), model="plan-model"),
        ]
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), client=_train(), post=poster) == 0
    written = _read(data)
    assert written["news"] == [{"headline": "Híd", "publisher": "Telex", "time": "07:00"}]
    news = _llm(data, "news.json")
    assert len(news) == 2
    assert "no other text" not in news[0]["prompt"]
    assert "no other text" in news[1]["prompt"]
    assert news[1]["model"] == "news-model"
    assert _llm(data, "requests.json") == {"count": 3}
    assert written["meta"]["mode"] == "on"
    assert written["meta"]["model"] == "news-model, plan-model"
    assert len(poster.calls) == 3


def test_two_failures_fall_back_and_mark_the_run_degraded(tmp_path):
    data = _data(tmp_path, caldav_host="https://cal.example/dav/")
    poster = Poster(
        [
            Reply("ignored", status=302, model="nope"),
            requests.ConnectionError("down"),
            Reply("nope", model="x"),
            Reply("still nope", model="y"),
        ]
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), client=_train(), post=poster) == 0
    written = _read(data)
    assert [row["headline"] for row in written["news"]] == ["Lab note", "Híd"]
    assert written["prep"] == ["07:40 Vonat: jegyet venni"]
    assert written["meta"]["mode"] == "degraded"
    assert written["meta"]["model"] is None
    assert written["meta"]["sources"]["model"] == "failed"
    assert _llm(data, "requests.json") == {"count": 4}
    assert len(poster.calls) == 4


def test_blank_content_ignores_json_hiding_in_reasoning(tmp_path):
    data = _data(tmp_path, caldav_host="https://cal.example/dav/")
    hidden = json.dumps({"picks": [{"id": 2, "category": "local"}]})
    poster = Poster(
        [
            Reply("", reasoning=hidden, model="trace"),
            Reply("   ", reasoning=hidden, model="trace"),
            _notes((1, "Vedd a jegyet."), model="plan-model"),
        ]
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), client=_train(), post=poster) == 0
    written = _read(data)
    assert [row["headline"] for row in written["news"]] == ["Lab note", "Híd"]
    assert written["prep"] == [{"line": "07:40 Vonat: jegyet venni", "note": "Vedd a jegyet."}]
    assert written["meta"]["mode"] == "degraded"
    assert written["meta"]["model"] == "plan-model"
    assert written["meta"]["sources"]["model"] == "failed"
    assert _llm(data, "requests.json") == {"count": 3}
    stored = json.loads(_llm(data, "news.json")[0]["response"])
    message = stored["choices"][0]["message"]
    assert message["content"] == ""
    assert message["reasoning"] == hidden


def test_dirty_picks_and_a_long_note_are_dropped_without_a_second_call(tmp_path):
    data = _data(tmp_path, caldav_host="https://cal.example/dav/")
    router = _interest(data, 5)
    poster = Poster(
        [
            _picks((5, "interest"), (99, "interest"), (4, "interest"), (3, "interest"), (2, "interest"), (1, "interest")),
            _notes((1, "x" * 121), (2, "n" * 120)),
        ]
    )
    client = Client(
        [
            Calendar(
                [
                    _event("a", "Elso", datetime(2026, 10, 15, 7, 40, tzinfo=ZONE)),
                    _event("b", "Masodik", datetime(2026, 10, 15, 8, 0, tzinfo=ZONE)),
                ],
                supported=("VEVENT",),
            )
        ]
    )
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=client, post=poster) == 0
    written = _read(data)
    assert [row["headline"] for row in written["news"]] == ["Story 5", "Story 4", "Story 3", "Story 2"]
    assert written["prep"] == [
        "07:40 Elso",
        {"line": "08:00 Masodik", "note": "n" * 120},
    ]
    assert written["meta"]["mode"] == "on"
    assert _llm(data, "requests.json") == {"count": 2}
    assert len(poster.calls) == 2


def test_model_off_builds_the_deterministic_edition_without_a_call(tmp_path):
    data = _data(tmp_path, model_on=False)
    leftover = data / "editions" / "2026-10-14" / "llm"
    leftover.mkdir(parents=True)
    (leftover / "news.json").write_text("{}\n", encoding="utf-8")
    poster = Poster([])
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), post=poster) == 0
    written = _read(data)
    assert [row["headline"] for row in written["news"]] == ["Lab note", "Híd"]
    assert written["meta"]["mode"] == "off"
    assert written["meta"]["model"] is None
    assert poster.calls == []
    assert not (data / "editions" / "2026-10-14" / "llm").exists()


def test_titles_only_still_calls_without_snippets_or_descriptions(tmp_path):
    data = _data(
        tmp_path,
        caldav_host="https://cal.example/dav/",
        send_task_descriptions=False,
    )
    router = Router()
    router.add(
        WIRED,
        _rss(
            [
                {
                    "title": "Visible headline",
                    "link": "https://wired.example/visible",
                    "description": "SECRET-SNIPPET",
                    "pubDate": "Wed, 14 Oct 2026 06:00:00 GMT",
                }
            ]
        ),
    )
    router.add(TELEX, _rss([]))
    poster = Poster([_picks((1, "interest")), _notes((1, "Rövid."))])
    client = _train(description="SECRET-TASK")
    assert run(data, now=WHEN, render_pdf=_write_ok, get=router, client=client, post=poster) == 0
    prompts = _llm(data, "news.json")[0]["prompt"] + "\n" + _llm(data, "planner.json")[0]["prompt"]
    assert "SECRET-SNIPPET" not in prompts
    assert "SECRET-TASK" not in prompts
    assert "Visible headline" in prompts
    assert "Vonat" in prompts
    assert "Hungarian" in _llm(data, "planner.json")[0]["prompt"]
    assert len(poster.calls) == 2


def test_an_empty_key_skips_the_request_and_marks_the_run_degraded(tmp_path):
    data = _data(tmp_path, secret="OPENROUTER_API_KEY=\n")
    leftover = data / "editions" / "2026-10-14" / "llm"
    leftover.mkdir(parents=True)
    (leftover / "news.json").write_text("{}\n", encoding="utf-8")
    poster = Poster([])
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), post=poster) == 0
    written = _read(data)
    assert [row["headline"] for row in written["news"]] == ["Lab note", "Híd"]
    assert written["meta"]["mode"] == "degraded"
    assert written["meta"]["model"] is None
    assert "model" not in written["meta"]["sources"]
    assert poster.calls == []
    assert not (data / "editions" / "2026-10-14" / "llm").exists()


def test_a_spaced_key_is_sent_and_not_appended_twice(tmp_path):
    data = _data(tmp_path, secret="OPENROUTER_API_KEY = sk-live\n")
    poster = Poster([_picks(), _notes()])
    assert run(data, now=WHEN, render_pdf=_write_ok, get=_feeds(), post=poster) == 0
    assert poster.calls[0][1]["headers"]["Authorization"] == "Bearer sk-live"
    text = (data / "secrets.env").read_text(encoding="utf-8")
    assert text == "OPENROUTER_API_KEY = sk-live\nADMIN_PASSWORD_HASH=\nSESSION_SECRET=\n"
    assert text.count("OPENROUTER_API_KEY") == 1


def test_weekend_light_mood_and_english_notes(tmp_path):
    data = _data(tmp_path)
    poster = Poster([_picks(), _notes()])
    assert run(data, now=SATURDAY, render_pdf=_write_ok, get=Router(), post=poster) == 0
    day = "2026-10-17"
    assert "Mood: light" in _llm(data, "news.json", day)[0]["prompt"]
    assert "warmer" in _llm(data, "planner.json", day)[0]["prompt"]

    english = _data(tmp_path, language="en")
    poster = Poster([_picks(), _notes()])
    assert run(english, now=WHEN, render_pdf=_write_ok, get=Router(), post=poster) == 0
    prompt = _llm(english, "planner.json")[0]["prompt"]
    assert "Write each note in English." in prompt
    assert "Hungarian" not in prompt


def test_a_title_newline_stays_on_its_numbered_line(tmp_path):
    from newspaper.llm import apply_model

    edition = tmp_path / "edition"
    snapshot = {"news": [], "prep": ["07:40 Vonat"], "meta": {"sources": {}}}
    pool = [
        {
            "id": 1,
            "category": "interest",
            "title": "Line\none",
            "snippet": "snip",
            "published": None,
            "feed": "Wired",
        }
    ]
    poster = Poster([_picks((1, "interest")), _notes((1, "Jegyzet."))])
    apply_model(
        snapshot,
        {
            "model_on": True,
            "language": "hu",
            "model_name": "openrouter/free",
            "send_task_descriptions": True,
        },
        pool,
        [{"id": 1, "title": "Task\nname", "description": "keep this"}],
        api_key="sk-test",
        light=False,
        edition_dir=edition,
        post=poster,
    )
    news = json.loads((edition / "llm" / "news.json").read_text(encoding="utf-8"))
    planner = json.loads((edition / "llm" / "planner.json").read_text(encoding="utf-8"))
    assert "1. interest | Line one" in news[0]["prompt"]
    assert "Line\none" not in news[0]["prompt"]
    assert "1. Task name" in planner[0]["prompt"]
    assert "Task\nname" not in planner[0]["prompt"]


def test_call_files_do_not_import_the_smoke_scripts():
    text = Path("newspaper/llm.py").read_text(encoding="utf-8")
    assert "scripts/smoke" not in text
    assert "scripts.smoke" not in text
