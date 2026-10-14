"""Ask OpenRouter for news ids and one prep note per tomorrow item."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from newspaper.http import check_url
from newspaper.sources.news import QUOTA, news_row

API_URL = "https://openrouter.ai/api/v1/chat/completions"
NOTE_MAX = 120
_CATEGORIES = {"interest", "local"}


def apply_model(
    snapshot: dict,
    settings: dict,
    pool: list[dict],
    prep_items: list[dict],
    *,
    api_key: str,
    light: bool,
    edition_dir: Path | None,
    post,
) -> None:
    """Pick news and attach planner notes. A failed block keeps its deterministic rows."""
    meta = snapshot.setdefault("meta", {})
    if not settings.get("model_on", True):
        meta["mode"] = "off"
        meta["model"] = None
        _clear_stored(edition_dir)
        return
    key = (api_key or "").strip()
    if not key:
        meta["mode"] = "degraded"
        meta["model"] = None
        _clear_stored(edition_dir)
        return

    mood = "light" if light else "normal"
    language = str(settings.get("language") or "hu")
    model_name = str(settings.get("model_name") or "").strip() or "openrouter/free"
    described = settings.get("send_task_descriptions", True) is not False
    news_prompt = _news_prompt(pool, mood=mood, snippets=described, strict=False)
    news_strict = _news_prompt(pool, mood=mood, snippets=described, strict=True)
    plan_prompt = _planner_prompt(
        prep_items,
        mood=mood,
        language=language,
        descriptions=described,
        strict=False,
    )
    plan_strict = _planner_prompt(
        prep_items,
        mood=mood,
        language=language,
        descriptions=described,
        strict=True,
    )

    picks, news_attempts, news_ok = _call(post, model_name, key, news_prompt, news_strict, _parse_picks)
    notes, plan_attempts, plan_ok = _call(post, model_name, key, plan_prompt, plan_strict, _parse_notes)
    if news_ok:
        snapshot["news"] = _picked_rows(pool, picks)
    if plan_ok:
        snapshot["prep"] = _noted_lines(snapshot.get("prep") or [], prep_items, notes)

    models = []
    if news_ok:
        models.extend(_answered(news_attempts))
    if plan_ok:
        models.extend(_answered(plan_attempts))
    meta["mode"] = "on" if news_ok and plan_ok else "degraded"
    meta["model"] = _distinct(models)
    if not news_ok or not plan_ok:
        sources = meta.setdefault("sources", {})
        sources["model"] = "failed"
    if edition_dir is not None:
        _store(Path(edition_dir), news_attempts, plan_attempts)


def _call(post, model_name: str, api_key: str, prompt: str, strict: str, parse):
    attempts = []
    for text in (prompt, strict):
        attempt = _attempt(post, model_name, api_key, text)
        attempts.append(attempt)
        if attempt["content"] is not None:
            parsed = parse(attempt["content"])
            if parsed is not None:
                attempt["ok"] = True
                return parsed, attempts, True
    return None, attempts, False


def _attempt(post, model_name: str, api_key: str, prompt: str) -> dict:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        check_url(API_URL)
        response = post(API_URL, json=payload, headers=headers, timeout=60)
    except Exception as exc:
        return {"prompt": prompt, "response": str(exc), "model": None, "content": None}
    text = getattr(response, "text", "") or ""
    status = getattr(response, "status_code", 0)
    redirect = bool(getattr(response, "is_redirect", False)) or status in {301, 302, 303, 307, 308}
    if redirect or not isinstance(status, int) or status < 200 or status >= 300:
        return {"prompt": prompt, "response": text, "model": None, "content": None}
    try:
        data = response.json()
    except Exception:
        return {"prompt": prompt, "response": text, "model": None, "content": None}
    model = data.get("model") if isinstance(data, dict) else None
    if not isinstance(model, str) or not model.strip():
        model = None
    else:
        model = model.strip()
    return {
        "prompt": prompt,
        "response": text,
        "model": model,
        "content": _message_content(data),
    }


def _message_content(data) -> str | None:
    """Blank content fails the attempt. A reasoning trace is not the answer."""
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return content.strip()


def _parse_picks(text: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("picks"), list):
        return None
    picks = []
    for item in data["picks"]:
        if not isinstance(item, dict) or "id" not in item or "category" not in item:
            return None
        picked_id = item["id"]
        if isinstance(picked_id, bool) or not isinstance(picked_id, int):
            return None
        if item["category"] not in _CATEGORIES:
            return None
        picks.append({"id": picked_id, "category": item["category"]})
    return picks


def _parse_notes(text: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("notes"), list):
        return None
    notes = []
    for item in data["notes"]:
        if not isinstance(item, dict) or "id" not in item or "note" not in item:
            return None
        note_id = item["id"]
        if isinstance(note_id, bool) or not isinstance(note_id, int):
            return None
        if not isinstance(item["note"], str):
            return None
        notes.append({"id": note_id, "note": item["note"]})
    return notes


def _picked_rows(pool: list[dict], picks: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in pool if "id" in item}
    interest = 0
    local = 0
    seen = set()
    chosen = []
    for pick in picks:
        item = by_id.get(pick["id"])
        if item is None or pick["id"] in seen:
            continue
        category = item.get("category")
        if category == "interest" and interest < QUOTA:
            interest += 1
        elif category == "local" and local < QUOTA:
            local += 1
        else:
            continue
        seen.add(pick["id"])
        chosen.append(news_row(item))
    return chosen


def _noted_lines(lines, prep_items: list[dict], notes: list[dict]) -> list:
    if not isinstance(lines, list) or len(lines) != len(prep_items):
        return list(lines) if isinstance(lines, list) else []
    kept = {}
    for note in notes:
        if note["id"] in kept:
            continue
        text = note["note"]
        if not text.strip() or len(text) > NOTE_MAX:
            continue
        kept[note["id"]] = text
    rows = []
    for line, item in zip(lines, prep_items):
        note = kept.get(item.get("id"))
        if note is None:
            rows.append(line)
        else:
            rows.append({"line": line, "note": note})
    return rows


def _answered(attempts: list[dict]) -> list[str]:
    for attempt in attempts:
        if attempt.get("ok") and attempt.get("model"):
            return [attempt["model"]]
    return []


def _distinct(names: list[str]) -> str | None:
    seen = []
    for name in names:
        if name not in seen:
            seen.append(name)
    if not seen:
        return None
    return ", ".join(seen)


def _news_prompt(pool: list[dict], *, mood: str, snippets: bool, strict: bool) -> str:
    lines = []
    if strict:
        lines.append("Reply with one JSON object and no other text.")
    lines.append(f"Mood: {mood}.")
    lines.append('Choose news ids. Return {"picks": [{"id": 12, "category": "interest"}]}.')
    lines.append("category is interest or local. Use only ids from this list.")
    for item in pool:
        lines.append(f"{item['id']}. {item['category']} | {_one_line(item.get('title'))}")
        if snippets and item.get("snippet"):
            lines.append(str(item["snippet"]))
    return "\n".join(lines)


def _planner_prompt(items: list[dict], *, mood: str, language: str, descriptions: bool, strict: bool) -> str:
    lines = []
    if strict:
        lines.append("Reply with one JSON object and no other text.")
    written = "Hungarian" if language == "hu" else "English"
    lines.append(f"Write each note in {written}.")
    lines.append("One note per item, at most 120 characters.")
    lines.append("Plain and literal.")
    lines.append("Do not personify the calendar or the tasks.")
    lines.append('Do not use an "X is not Y, it is Z" construction.')
    lines.append("No closing kicker.")
    lines.append("Give no advice beyond the task's own text.")
    lines.append("State no fact that is not in the item.")
    if mood == "light":
        lines.append("The tone may be a little warmer. Skip jokes, personification, and clever reversals.")
    else:
        lines.append("Mood: normal.")
    lines.append('Return {"notes": [{"id": 1, "note": "..."}]}.')
    for item in items:
        lines.append(f"{item['id']}. {_one_line(item.get('title'))}")
        if descriptions and item.get("description"):
            lines.append(str(item["description"]))
    return "\n".join(lines)


def _one_line(value) -> str:
    return " ".join(str(value or "").split())


def _clear_stored(edition_dir: Path | None) -> None:
    if edition_dir is None:
        return
    folder = Path(edition_dir) / "llm"
    if folder.is_dir():
        shutil.rmtree(folder)


def _store(edition_dir: Path, news_attempts: list[dict], plan_attempts: list[dict]) -> None:
    folder = edition_dir / "llm"
    folder.mkdir(parents=True, exist_ok=True)
    _dump(folder / "news.json", [_public(item) for item in news_attempts])
    _dump(folder / "planner.json", [_public(item) for item in plan_attempts])
    _dump(folder / "requests.json", {"count": len(news_attempts) + len(plan_attempts)})


def _public(attempt: dict) -> dict:
    return {
        "prompt": attempt["prompt"],
        "response": attempt["response"],
        "model": attempt["model"],
    }


def _dump(path: Path, body) -> None:
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
