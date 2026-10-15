"""One daily item: an unseen grayscale xkcd, or a sudoku with one solution."""

from __future__ import annotations

import base64
import json
import random
from io import BytesIO
from typing import Callable

from PIL import Image

from newspaper.db import puzzle_keys
from newspaper.sources import response_text, status_code

XKCD_CREDIT = "xkcd.com, CC BY-NC 2.5"
XKCD_LATEST = "https://xkcd.com/info.0.json"
WEEKEND_GIVENS = 40
WEEKDAY_GIVENS = 28
MAX_EDGE = 1400
MAX_ASPECT = 2.2
ATTEMPTS = 40
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def collect_daily(
    settings: dict,
    now,
    *,
    weekend: bool,
    conn,
    get: Callable,
    rng: random.Random | None = None,
) -> tuple[dict, dict]:
    rng = rng or random.Random()
    rotation = settings.get("daily_rotation") or {}
    kind = str(rotation.get(WEEKDAYS[now.weekday()]) or "sudoku")
    if not settings.get("xkcd_on", True):
        kind = "sudoku"
    puzzle = _sudoku(rng, weekend)
    if kind != "xkcd":
        return puzzle, {"daily": "ok"}
    comic = _xkcd(get, puzzle_keys(conn, "xkcd"), rng)
    if comic is None:
        return puzzle, {"xkcd": "failed"}
    comic_id = str(comic.pop("id"))
    return comic, {"xkcd": "ok", "xkcd_id": comic_id}


def generate_sudoku(rng: random.Random, givens: int) -> list[list[int]]:
    puzzle = _filled(rng)
    cells = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(cells)
    target = max(0, min(81, givens))
    left = 81
    for row, column in cells:
        if left <= target:
            break
        saved = puzzle[row][column]
        puzzle[row][column] = 0
        if count_solutions(puzzle) == 1:
            left -= 1
        else:
            puzzle[row][column] = saved
    return puzzle


def count_solutions(grid: list[list[int]], limit: int = 2) -> int:
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    empty: list[tuple[int, int]] = []
    for r in range(9):
        for c in range(9):
            number = grid[r][c]
            if number:
                bit = 1 << number
                rows[r] |= bit
                cols[c] |= bit
                boxes[(r // 3) * 3 + (c // 3)] |= bit
            else:
                empty.append((r, c))

    def search(index: int) -> int:
        if index == len(empty):
            return 1
        best = index
        best_count = 10
        best_mask = 0
        for cursor in range(index, len(empty)):
            r, c = empty[cursor]
            mask = ((1 << 10) - 2) & ~(rows[r] | cols[c] | boxes[(r // 3) * 3 + (c // 3)])
            count = mask.bit_count()
            if count < best_count:
                best = cursor
                best_count = count
                best_mask = mask
                if count <= 1:
                    break
        if best_count == 0:
            return 0
        empty[index], empty[best] = empty[best], empty[index]
        r, c = empty[index]
        box = (r // 3) * 3 + (c // 3)
        total = 0
        mask = best_mask
        while mask:
            bit = mask & -mask
            mask ^= bit
            rows[r] |= bit
            cols[c] |= bit
            boxes[box] |= bit
            total += search(index + 1)
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[box] ^= bit
            if total >= limit:
                break
        empty[index], empty[best] = empty[best], empty[index]
        return total

    return search(0)


def _sudoku(rng: random.Random, weekend: bool) -> dict:
    givens = WEEKEND_GIVENS if weekend else WEEKDAY_GIVENS
    return {"kind": "sudoku", "grid": generate_sudoku(rng, givens), "large": weekend}


def _filled(rng: random.Random) -> list[list[int]]:
    digits = list(range(1, 10))
    rng.shuffle(digits)
    rows = [[digits[(3 * (r % 3) + r // 3 + c) % 9] for c in range(9)] for r in range(9)]

    def shuffle_groups(groups: list[list[int]]) -> list[list[int]]:
        bands = [groups[i : i + 3] for i in range(0, 9, 3)]
        for band in bands:
            rng.shuffle(band)
        rng.shuffle(bands)
        return [row for band in bands for row in band]

    rows = shuffle_groups(rows)
    columns = shuffle_groups([list(column) for column in zip(*rows)])
    return [list(row) for row in zip(*columns)]


def _xkcd(get: Callable, used: set[str], rng: random.Random) -> dict | None:
    try:
        latest = _json(get(XKCD_LATEST, timeout=20))
        newest = int(latest["num"])
    except Exception:
        return None
    candidates = [number for number in range(1, newest + 1) if number != 404 and str(number) not in used]
    rng.shuffle(candidates)
    for comic_id in candidates[:ATTEMPTS]:
        comic = _one_comic(get, comic_id)
        if comic is not None:
            return comic
    return None


def _one_comic(get: Callable, comic_id: int) -> dict | None:
    try:
        info = _json(get(f"https://xkcd.com/{comic_id}/info.0.json", timeout=20))
    except Exception:
        return None
    if info.get("extra_parts"):
        return None
    image_url = str(info.get("img") or "")
    if not image_url:
        return None
    try:
        response = get(image_url, timeout=20)
        if status_code(response) >= 400:
            return None
        image = Image.open(BytesIO(response.content))
        image.load()
    except Exception:
        return None
    width, height = image.size
    if width < 1 or height < 1:
        return None
    long_edge = max(width, height)
    short_edge = min(width, height)
    if long_edge > MAX_EDGE or long_edge / short_edge > MAX_ASPECT:
        return None
    gray = image.convert("L")
    buffer = BytesIO()
    gray.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "id": comic_id,
        "kind": "xkcd",
        "src": f"data:image/png;base64,{encoded}",
        "alt": str(info.get("alt") or ""),
        "credit": XKCD_CREDIT,
    }


def _json(response) -> dict:
    if status_code(response) >= 400:
        raise RuntimeError(f"HTTP {status_code(response)}")
    return json.loads(response_text(response))
