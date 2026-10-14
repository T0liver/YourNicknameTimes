---
title: '1.3 Build the deterministic edition'
type: 'feature'
ticket: '3'
created: '2026-10-14'
status: 'built'
baseline_revision: 'e1d1a8ddf1b9bf4decd1c730e43ab6da1bc7a812'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/edition.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The template renders a fixture only. Nothing writes the snapshot later stories render from, or drops overflow until the page is one A4 sheet.

**Approach:** Add `newspaper.db`, `data/secrets.env`, and `data/editions/YYYY-MM-DD/`. A model-off run writes `edition.json` and renders `print.pdf` from that file. This slice uses fixture content. Live sources are the follow-on brief.

## Boundaries & Constraints

**Always:**
- `meta.mode` is `off` and `meta.model` is null. `print.pdf` is rendered from the `edition.json` just written. `newspaper-render` still uses the story 1.2 fixture.
- One A4 page. Body type stays put. Drop one item at a time: almanac details, extra week rows, extra news rows, descriptions, second-tier prep notes. Floors: almanac keeps sun, moon, name day, and rates; `this_week` keeps 3; news keeps 4; then clear `dek` and `place`; then drop prep lines after the first. Each drop is `drop: {what}` in `run.log` and `meta.trims`. If it still will not build, or is still over one page, exit non-zero and leave no `print.pdf`.
- Empty blocks are omitted. Missing weather numbers print no high/low line. `daily_item` is a string or `{kind: xkcd|sudoku, ...}` with comic bytes as a data URI.
- `newspaper/http.py` allows http and https only, including redirects, and never calls a shell.
- Fresh database seeds an empty CalDAV host, Telex `https://telex.hu/rss` (local), Wired `https://www.wired.com/feed/rss` (interest), extras on, name day on, xkcd Mon/Wed/Fri/Sun, sudoku Tue/Thu/Sat, timezone `Europe/Budapest`, language Hungarian, empty motto, title `Your Nickname Times`, greeting `Yippie, weekend! You earned it!`, `weekend_edition` on, `weekend_mood` `light`, volume 1. Volume increments only after a one-page PDF. `data/secrets.env` is mode `0600` and holds `CALDAV_PASSWORD` only.
- Dateline: `Vol. N · {date} · {weekday} · {city} · AS OF hh:mm`. `AS OF` is collection start. Hungarian month and weekday names.

**Never:**
- Live CalDAV, RSS, weather, xkcd, sudoku, Wikipedia, MNB, sun, or moon clients. Model calls, the worker, FastAPI, CUPS, Dropbox, `cloud.pdf`, tables `runs`, `jobs`, `heartbeat`, `alerts`.
- Edits to `scripts/smoke/`, shipped fonts, `@page`, or the 7.63 / 5.06 / 2.48 / 2.57 inch grid. Feed URLs inside fetch functions. A personal server address in defaults.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Model-off run | Fixture snapshot that fits | `edition.json` and one A4 `print.pdf` from that JSON; mode `off` | No error expected |
| Empty blocks | All blocks empty | Blocks absent; a present column is full width | Snapshot still written |
| One drop | One almanac line over the floor and over one page | Second render is one page; `run.log` names the drop | No error expected |
| Still too long | Still over one page after the floors | Non-zero exit; no `print.pdf`; drops in `run.log` | Delete a partial PDF |
| Bad URL | `file://` passed to the HTTP helper | No request | Raise; no shell call |

</frozen-after-approval>

## Code Map

- `newspaper/render.py` — Reuse `render_html` (line 27) and `render_edition` (line 38). Leave `main` on the fixture. `tests/test_render.py` calls `render_edition()` with no argument.
- `newspaper/templates/edition.html.j2` — Fix high/low at line 75 and `daily_item` at line 131. Do not restructure the tables. CSS gains comic and sudoku rules only.
- `.gitignore` — Does not yet ignore `data/secrets.env`, `data/newspaper.db`, `data/editions/`, or `data/cache/`. Do not import `scripts/smoke/`.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- Add `requests` and `newspaper-edition`.
- [x] `.gitignore` and `data/secrets.env.example` -- Ignore those four data paths. Example is `CALDAV_PASSWORD=`.
- [x] `newspaper/db.py` -- `settings` with five versions, `feeds`, `editions`, `puzzle_history`, `rate_history`. Seed the Boundaries defaults.
- [x] `newspaper/http.py` -- GET through `requests` after the scheme check on the URL and each redirect. No `subprocess`.
- [x] `newspaper/overflow.py` and `newspaper/edition_build.py` -- `--data-dir` defaults to `data`. Write JSON, render from the loaded file, log drops, delete a bad PDF. Tests pass a snapshot in-process.
- [x] `newspaper/templates/edition.html.j2` and `newspaper/static/edition.css` -- Weather numbers, string daily item, xkcd figure, sudoku grid.
- [x] `tests/test_edition.py` and `README.md` -- I/O matrix, and how to init the database and run the command.

**Acceptance Criteria:**
- Given no nickname, when a run builds, then the nameplate is `Your Nickname Times` and an empty motto adds no motto node.
- Given the written JSON, when the PDF is built, then the renderer receives that object.

## Implementation Notes

- Added `newspaper-edition`, SQLite settings (five versions), feeds, editions, puzzle history, and rate history. A fresh database seeds the boundary defaults. `data/secrets.env` is mode 0600 and holds `CALDAV_PASSWORD`.
- A model-off run writes `edition.json` and renders `print.pdf` from that file. Overflow drops one item at a time down to the floors, logs `drop: {what}`, and deletes a bad PDF. Blocks in this slice come from the fixture.
- Almanac floors match the labels Nap, Hold, Névnap, and Árfolyam (plus the English sun, moon, name day, and rates). An xkcd daily item puts comic bytes in `src`. Language is stored as `hu`.
- `python -m pytest tests/test_render.py tests/test_edition.py`: 23 passed, no network.

## Plan Change Log

## Review Triage Log

- 2026-10-14 quick pass 1: high=0 medium=2 low=0 false=1 maybe-false=0
- medium / patch — `uv.lock` omits `requests` while `pyproject.toml` requires it. Verified: the lock is untracked, absent at the baseline, and its newspaper package does not list `requests`.
- medium / patch — `newspaper/db.py` `record_edition` inserts a new row on every success. Verified: the same `editions/YYYY-MM-DD/` path is overwritten, so an earlier row keeps a volume the files no longer show.
- false — `weasy_render` and `build_edition` unlink `print.pdf` when the page count is not 1. The plan requires a failed build to leave no `print.pdf`, including a partial written into that day's folder.

## Design Notes

Snapshot keys match the Jinja context plus `meta` (`mode`, `model`, `trims`, `sources`, `as_of`, `volume`, `language`, `timezone`). Almanac lines are `{label, text}`. News rows are `headline`, `publisher`, `time`, optional `dek`. Today rows are `time`, `title`, optional `place` and `dek`. City is omitted until one is saved.

## Verification

**Commands:**
- `python -m pytest tests/test_render.py tests/test_edition.py` -- expected: both pass with no network
