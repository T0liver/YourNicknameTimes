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
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/data-sources.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/edition.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The A4 template could render a fixture only. A morning run could not fill it from CalDAV, the seed feeds, weather, one daily item, and the almanac, or save the snapshot later stories render from.

**Approach:** Add `newspaper.db`, `data/secrets.env`, and `data/editions/YYYY-MM-DD/`. A model-off run collects those sources, writes `edition.json`, and renders `print.pdf` from that file. Overflow drops items in edition.md order. Fetches stay on http and https.

## Boundaries & Constraints

**Always:**
- `meta.mode` is `off` and `meta.model` is null. News rank is recency, then feed weight, then keyword score. Prep is the plain tomorrow list. Almanac is the expanded strip. `print.pdf` is rendered from the `edition.json` just written. `newspaper-render` still uses the story 1.2 fixture.
- One A4 page. Body type stays put. Drop one item at a time: almanac details, extra week rows, extra news rows, descriptions, second-tier prep notes. Floors: almanac keeps sun, moon, name day, and rates; `this_week` keeps 3; news keeps 4; then clear `dek` and `place`; then drop prep lines after the first. Each drop is `drop: {what}` in `run.log` and `meta.trims`. If it still will not build, or is still over one page, exit non-zero and leave no `print.pdf`.
- Empty blocks are omitted. A weather failure says `Forecast unavailable` and prints no numbers. A failed extra is omitted. `daily_item` is a string or `{kind: xkcd|sudoku, ...}` with comic bytes as a data URI.
- `newspaper/http.py` allows http and https only, including redirects, and never calls a shell. Feed URLs come from `feeds`. CalDAV may use the `caldav` library after the host passes that check. `search(expand=True)`. Skip completed and cancelled tasks. No collection picks means every calendar and task list. Password is `CALDAV_PASSWORD` in `data/secrets.env` mode `0600`. An empty host leaves the schedule blocks empty.
- RSS keeps 24 hours, drops undated items unless `keep_undated_news` is on, dedupes by URL then title ratio 0.88, caps at 80, and prints 4 interest and 4 local rows. Rotation: xkcd Mon/Wed/Fri/Sun, sudoku Tue/Thu/Sat. Unseen grayscale comic, English alt text, credit `xkcd.com, CC BY-NC 2.5`. Skip `extra_parts`, an edge over 1400 px, or aspect over 2.2. Comic failure prints sudoku. Weekend sudoku is easy and larger.
- Fresh database seeds an empty CalDAV host, Telex `https://telex.hu/rss` (local), Wired `https://www.wired.com/feed/rss` (interest), extras on, name day on, timezone `Europe/Budapest`, language Hungarian, empty motto, title `Your Nickname Times`, greeting `Yippie, weekend! You earned it!`, `weekend_edition` on, `weekend_mood` `light`, volume 1. Volume increments only after a one-page PDF. One `editions` row per date, updated to the volume that wrote the files.
- Weekend switch on: sun, that greeting, hobby weights up when mood is `light`, tighter task band. Switch off: weekday page. This week is the seven days after today. Due excludes today and tomorrow. Overdue is `N napja lejárt`, oldest first. Undated tasks use `bármikor`. An event that started earlier and still covers today stays on today.
- Dateline: `Vol. N · {date} · {weekday} · {city} · AS OF hh:mm`. `AS OF` is collection start. Hungarian month and weekday names. City is omitted until one is saved. On this day uses the paper language, falls back to English, and logs that. Name day prints vendored `main` names. MNB rates print with the rate date. Sun and moon need saved coordinates.
- Remember an xkcd id only after the one-page PDF exists.

**Never:**
- Model calls, the worker, FastAPI, CUPS, Dropbox, `cloud.pdf`, OPML, and tables `runs`, `jobs`, `heartbeat`, `alerts`.
- Edits to `scripts/smoke/`, shipped fonts, `@page`, or the 7.63 / 5.06 / 2.48 / 2.57 inch grid. Feed URLs inside fetch functions. A personal server address in defaults. Mini crossword, Jumble, and word search.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Model-off run | Sources that fit one page | `edition.json` and one A4 `print.pdf` from that JSON; mode `off` | No error expected |
| Empty blocks | All blocks empty | Blocks absent; a present column is full width | Snapshot still written |
| One drop | One almanac line over the floor and over one page | Second render is one page; `run.log` names the drop | No error expected |
| Still too long | Still over one page after the floors | Non-zero exit; no `print.pdf`; drops in `run.log` | Delete a partial PDF |
| Bad URL | `file://` feed or helper URL | No request | Source or helper fails; no shell call |
| Weather down | Open-Meteo error | `Forecast unavailable` and no numbers | Other blocks remain |
| xkcd down | Comic fails on Monday | Daily item is sudoku | Run continues |
| Empty `hu` day | Hungarian on-this-day payload empty | English entries; fallback in `run.log` | No invented text |
| Sunday rates | MNB payload dated Friday | Line shows Friday and `MNB` | No invented rate |
| Weekend off | Saturday, switch off | No sun, greeting, or easy-sudoku size | No error expected |

</frozen-after-approval>

## Code Map

- `newspaper/render.py` — `render_html` and `render_edition` take the snapshot. `newspaper-render` stays on the fixture.
- `newspaper/edition_build.py` — Collects, writes `edition.json`, renders `print.pdf` from that file, and remembers an xkcd id only after success.
- `newspaper/http.py` — http and https only, including redirects. No shell.
- `newspaper/overflow.py` — Drop floors, one removal per render.
- `newspaper/db.py` — Settings, feeds, one edition row per date, puzzle history, rate history.
- `newspaper/sources/` — CalDAV, RSS, Open-Meteo, xkcd or sudoku, and the almanac. Do not import `scripts/smoke/`.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- `requests`, `feedparser`, `caldav`, `Pillow`, `astral`, and `newspaper-edition`.
- [x] `.gitignore` and `data/secrets.env.example` -- Ignore `data/secrets.env`, `data/newspaper.db`, `data/editions/`, and `data/cache/`. Example is `CALDAV_PASSWORD=`.
- [x] `newspaper/db.py` -- Settings with five versions, feeds, editions, puzzle history, rate history, and the fresh defaults.
- [x] `newspaper/http.py`, `newspaper/overflow.py`, `newspaper/edition_build.py` -- Allowlisted GET, drop loop, and the build command. `--data-dir` defaults to `data`.
- [x] `newspaper/templates/edition.html.j2` and `newspaper/static/edition.css` -- Weather numbers, string daily item, xkcd figure, sudoku grid, tighter weekend band.
- [x] `newspaper/sources/` and `newspaper/data/nevnapok.json` -- CalDAV, news, weather, daily item, almanac, and the MIT name-day table.
- [x] `tests/test_edition.py`, `tests/test_sources.py`, and `README.md` -- Both matrices, with no network.

**Acceptance Criteria:**
- Given no nickname, when a run builds, then the nameplate is `Your Nickname Times` and an empty motto adds no motto node.
- Given the written JSON, when the PDF is built, then the renderer receives that object.
- Given Saturday, the switch on, and mood `light`, when a run builds, then the page has the sun, the default greeting, and an easy sudoku.
- Given that Saturday with the switch off, when a run builds, then those weekend touches are absent.

## Implementation Notes

- `newspaper-edition` creates the database and `data/secrets.env`, writes `edition.json`, and renders `print.pdf` from that file. Volume starts at 1 and increases only after a one-page PDF. A second success on the same date updates that day's edition row.
- Overflow drops one item at a time down to the floors and logs `drop: {what}`. A failed build leaves no `print.pdf`.
- Collectors fill the snapshot with the model off. An xkcd id is stored only after that PDF exists. An in-progress event stays on today. A failed open task search marks CalDAV failed. On this day is `failed` when a request fails and no text is kept.
- `.venv/bin/python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py`: 45 passed, no network.

## Plan Change Log

- 2026-10-14 — Merged `story-fill-live-sources-plan.md` into this file. Both files carried `ticket: '3'`, so the tree reported two plans for story 1.3. One plan remains.

## Review Triage Log

- 2026-10-14 snapshot quick pass: high=0 medium=2 low=0 false=1 maybe-false=0
- medium / patch — `uv.lock` omitted `requests`. The stale untracked lock was deleted.
- medium / patch — `record_edition` inserted a second row for the same day. One row per date now holds the volume that wrote the files.
- false — Unlinking `print.pdf` when the page count is not 1 matches the rule that a failed build leaves no PDF.
- 2026-10-14 sources quick pass: high=0 medium=4 low=1 false=0 maybe-false=0
- medium / patch — An xkcd id was stored before the PDF existed. It is stored only after `build_edition` returns 0.
- medium / patch — On this day reported `ok` when one language request failed and the other had no text. That case is now `failed`.
- medium / patch — An event that started before today and still covers today was dropped. It stays on today.
- medium / patch — The unscoped task search swallowed errors. That calendar is marked failed.
- low / reject — CalDAV uses `DAVClient` after `check_url` on the host. The plan allows that library.

## Design Notes

Snapshot keys match the Jinja context plus `meta` (`mode`, `model`, `trims`, `sources`, `as_of`, `volume`, `language`, `timezone`). Hobby stems `hobby`, `kert`, `récept`, `tudomány`, `game`, `music` score +1, or +2 in `light` mood. Conflict stems `háború`, `gyilk`, `baleset`, `war`, `kill`, `crash` score -1 on interest and 0 on local. Weekday sudoku has fewer givens than weekend. Name-day credit is `froccsos/nevnapok-json`. MNB URL is `http://www.mnb.hu/arfolyamok.asmx/GetCurrentExchangeRates`.

## Verification

**Commands:**
- `python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py` -- expected: all pass with no network
