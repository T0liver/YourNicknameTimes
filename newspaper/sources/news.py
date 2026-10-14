"""Rank seed-feed items with the model off."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Callable

import feedparser

from newspaper.http import check_url
from newspaper.sources import response_text, status_code

HOBBY_STEMS = ("hobby", "kert", "récept", "tudomány", "game", "music")
CONFLICT_STEMS = ("háború", "gyilk", "baleset", "war", "kill", "crash")
POOL_CAP = 80
QUOTA = 4
TITLE_RATIO = 0.88
WINDOW = timedelta(hours=24)


def keyword_score(text: str, category: str, *, light: bool) -> int:
    folded = text.casefold()
    bonus = 2 if light else 1
    score = sum(bonus for stem in HOBBY_STEMS if stem.casefold() in folded)
    if category == "interest":
        score -= sum(1 for stem in CONFLICT_STEMS if stem.casefold() in folded)
    return score


def capped_pool(items: list[dict], *, light: bool) -> list[dict]:
    """Rank, dedupe, cap at 80, and number the survivors from 1."""
    scored = []
    for item in items:
        text = f"{item['title']} {item.get('snippet') or ''}"
        scored.append({**item, "keyword": keyword_score(text, item["category"], light=light)})
    scored.sort(
        key=lambda item: (
            item["published"].timestamp() if item["published"] is not None else float("-inf"),
            float(item["weight"]),
            item["keyword"],
        ),
        reverse=True,
    )
    kept: list[dict] = []
    for item in scored:
        url = (item.get("url") or "").strip()
        if url and any((other.get("url") or "").strip() == url for other in kept):
            continue
        title = item["title"]
        if any(
            SequenceMatcher(None, title.casefold(), other["title"].casefold()).ratio() >= TITLE_RATIO
            for other in kept
        ):
            continue
        kept.append(item)
    pool = []
    for index, item in enumerate(kept[:POOL_CAP], start=1):
        pool.append({**item, "id": index})
    return pool


def rows_from_pool(pool: list[dict]) -> list[dict]:
    """Keep at most four interest and four local rows, in pool order."""
    chosen = []
    interest = 0
    local = 0
    for item in pool:
        category = item["category"]
        if category == "interest" and interest < QUOTA:
            interest += 1
            chosen.append(item)
        elif category == "local" and local < QUOTA:
            local += 1
            chosen.append(item)
    return [news_row(item) for item in chosen]


def rank_news(items: list[dict], *, light: bool) -> list[dict]:
    """Sort by recency, feed weight, then keyword score, and apply the quotas."""
    return rows_from_pool(capped_pool(items, light=light))


def collect_pool(
    feeds: list[dict],
    *,
    now: datetime,
    keep_undated: bool,
    light: bool,
    get: Callable,
) -> tuple[list[dict], dict]:
    pooled, status = _fetch(feeds, now, keep_undated, get)
    return capped_pool(pooled, light=light), status


def collect_news(
    feeds: list[dict],
    *,
    now: datetime,
    keep_undated: bool,
    light: bool,
    get: Callable,
) -> tuple[list[dict], dict]:
    pool, status = collect_pool(
        feeds,
        now=now,
        keep_undated=keep_undated,
        light=light,
        get=get,
    )
    return rows_from_pool(pool), status


def _fetch(feeds: list[dict], now: datetime, keep_undated: bool, get: Callable) -> tuple[list[dict], dict]:
    status: dict[str, str] = {}
    pooled: list[dict] = []
    for feed in feeds:
        name = str(feed.get("name") or "")
        url = str(feed.get("url") or "")
        category = str(feed.get("category") or "")
        if category not in {"interest", "local"}:
            status[name] = "failed"
            continue
        try:
            check_url(url)
            response = get(url, timeout=20)
            if status_code(response) >= 400:
                raise RuntimeError(f"HTTP {status_code(response)}")
            parsed = feedparser.parse(response.content)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise RuntimeError("not a feed")
            rows = _entries(parsed, feed, now, keep_undated)
            status[name] = "ok"
        except Exception:
            status[name] = "failed"
            continue
        pooled.extend(rows)
    return pooled, status


def _entries(parsed, feed: dict, now: datetime, keep_undated: bool) -> list[dict]:
    zone = now.tzinfo
    limit = int(feed["max_items"]) if feed.get("max_items") is not None else None
    weight = float(feed.get("weight") or 0)
    category = str(feed["category"])
    name = str(feed.get("name") or "")
    rows = []
    for entry in parsed.entries:
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        published = _published(entry, zone)
        if published is None:
            if not keep_undated:
                continue
        elif published < now - WINDOW or published > now:
            continue
        rows.append(
            {
                "title": title,
                "url": str(entry.get("link") or "").strip(),
                "snippet": _snippet(entry),
                "published": published,
                "weight": weight,
                "category": category,
                "feed": name,
            }
        )
    rows.sort(
        key=lambda item: item["published"].timestamp() if item["published"] is not None else float("-inf"),
        reverse=True,
    )
    if limit is not None:
        rows = rows[: max(0, limit)]
    return rows


def _published(entry, zone) -> datetime | None:
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    published = datetime(*parsed[:6], tzinfo=timezone.utc)
    if zone is not None:
        return published.astimezone(zone)
    return published


def _snippet(entry) -> str:
    raw = entry.get("summary") or entry.get("description") or ""
    return " ".join(str(raw).split())


def news_row(item: dict) -> dict:
    """The printed row: the feed headline, publisher, and time."""
    return _printed(item)


def _printed(item: dict) -> dict:
    published = item["published"]
    clock = published.strftime("%H:%M") if published is not None else ""
    return {"headline": item["title"], "publisher": item["feed"], "time": clock}
