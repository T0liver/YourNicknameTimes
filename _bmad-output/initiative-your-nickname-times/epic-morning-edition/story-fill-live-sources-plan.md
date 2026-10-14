---
title: '1.3 Fill the edition from live sources'
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

**Problem:** The snapshot and overflow loop render fixture content. A morning run cannot yet fill that snapshot from CalDAV, the seed feeds, weather, one daily item, and the almanac.

**Approach:** Collectors behind `newspaper/http.py` and `caldav` fill the existing `edition.json` with the model off. The weekend switch selects the lighter page.

## Boundaries & Constraints

**Always:**
- Model off. Rank news by recency, feed weight, then keyword score. Prep is the plain tomorrow list. Almanac is expanded: up to three on-this-day lines, moon illumination, rate date, and credits.
- http and https only. No shell. Feed URLs come from `feeds`. Telex and Wired are already seeded.
- CalDAV uses `search(expand=True)`, skips completed and cancelled tasks, and keeps the current occurrence. No collection picks means every calendar and task list. Store `VEVENT` and `VTODO`. Password is `CALDAV_PASSWORD`. Empty host leaves those blocks empty.
- RSS keeps 24 hours, drops undated items unless `keep_undated_news` is on, dedupes by URL then title ratio 0.88, caps at 80, and prints 4 interest and 4 local rows.
- Weather failure says `Forecast unavailable` and omits numbers. A failed extra is omitted. No estimated value.
- Rotation: xkcd Mon/Wed/Fri/Sun, sudoku Tue/Thu/Sat. Unseen grayscale comic, English alt text, credit `xkcd.com, CC BY-NC 2.5`. Skip `extra_parts`, an edge over 1400 px, or aspect over 2.2. Comic failure prints sudoku. Sudoku has one solution; weekend is easy and larger.
- Weekend switch on: sun, greeting `Yippie, weekend! You earned it!`, hobby weights up when mood is `light`, tighter task band. Switch off: weekday page.
- This week is the seven days after today. Due excludes today and tomorrow. Overdue is `N napja lejárt`, oldest first. Undated tasks use `bármikor`. Timezone `Europe/Budapest`.
- On this day uses `{lang}.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}`, falls back to English, and logs that. Credit Wikipedia (CC BY-SA). Name day prints vendored `main` names and credits the MIT table. MNB `GetCurrentExchangeRates` supplies EUR, USD, and CHF in HUF with the rate date. Sun and moon need saved coordinates.

**Never:**
- Model calls, the worker, FastAPI, CUPS, Dropbox, `cloud.pdf`, OPML, and a second snapshot format.
- Changing overflow floors, the scheme check, or `newspaper-render`. Mini crossword, Jumble, and word search.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full collect | Fake CalDAV, feeds, weather, xkcd, almanac | Snapshot matches those payloads; mode `off` | No error expected |
| Weather down | Open-Meteo error | `Forecast unavailable` and no numbers | Other blocks remain |
| xkcd down | Comic fails on Monday | Daily item is sudoku | Run continues |
| Empty `hu` day | Hungarian on-this-day payload empty | English entries; fallback in `run.log` | No invented text |
| Sunday rates | MNB payload dated Friday | Line shows Friday and `MNB` | No invented rate |
| Bad feed URL | Feed row is `file://` | No request | `meta.sources` marks it failed |
| Weekend off | Saturday, switch off | No sun, greeting, or easy-sudoku size | No error expected |

</frozen-after-approval>

## Code Map

- `newspaper/edition_build.py` -- Collectors use the existing write-and-render path and `newspaper/http.py`.
- `newspaper/db.py` -- Read settings and feeds. Store xkcd ids in `puzzle_history`. Do not import `scripts/smoke/`.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` -- Add `feedparser`, `caldav`, `Pillow`, and `astral`.
- [ ] `newspaper/data/nevnapok.json` and `newspaper/data/nevnapok-LICENSE` -- Vendor froccsos/nevnapok-json `main` names and the MIT notice.
- [ ] `newspaper/sources/caldav_source.py` -- Today, tomorrow, this week, due, overdue. Basic or Digest auth.
- [ ] `newspaper/sources/news.py` -- Hobby stems `hobby`, `kert`, `récept`, `tudomány`, `game`, `music` are +1, or +2 in `light` mood. Conflict stems `háború`, `gyilk`, `baleset`, `war`, `kill`, `crash` are -1 on interest and 0 on local.
- [ ] `newspaper/sources/weather.py` -- Open-Meteo high, low, Hungarian summary, 3-4 day outlook. Celsius.
- [ ] `newspaper/sources/daily.py` -- Random unused xkcd id, grayscale data URI, unique sudoku.
- [ ] `newspaper/sources/almanac.py` -- Sun, moon, name day, on this day, MNB rates.
- [ ] `newspaper/edition_build.py` and `tests/test_sources.py` -- Wire collectors. A source failure sets `meta.sources` and continues. Tests use fakes, not the network.

**Acceptance Criteria:**
- Given Saturday, the switch on, and mood `light`, when a run builds, then the page has the sun, the default greeting, and an easy sudoku.
- Given that Saturday with the switch off, when a run builds, then those weekend touches are absent.
- Given a one-page collect, when the PDF is written, then it comes from that `edition.json`.

## Implementation Notes

## Plan Change Log

## Review Triage Log

- 2026-10-14 quick pass 1: high=0 medium=4 low=1 false=0 maybe-false=0
- medium / patch — `newspaper/sources/daily.py` `collect_daily` commits an xkcd id before the PDF exists. Verified: `remember_puzzle` runs inside `collect_daily`, and `assemble_snapshot` replaces the daily item with `""` if that insert raises.
- medium / patch — `newspaper/sources/almanac.py` `_on_this_day` returns `ok` when one language request fails and the other has no text. Verified: the final `return [], False, "ok"` runs unless both requests failed.
- medium / patch — `newspaper/sources/caldav_source.py` `_place` keeps an event only when `dtstart` is today or later this week. Verified: `_event` stores the start date and `_place` never reads `dtend`.
- medium / patch — `newspaper/sources/caldav_source.py` `_read` swallows an error from the unscoped task search and leaves `failed` false. Verified: that `except` is `pass`.
- low / reject — `newspaper/sources/caldav_source.py` `connect` uses `caldav.DAVClient` after `check_url` on the host. The plan allows that library. A missing digest challenge is uncommon for this Baïkal, and probing again would add a second request path.

## Design Notes

Weekday sudoku has fewer givens than weekend. Name-day credit is `froccsos/nevnapok-json`. MNB URL is `http://www.mnb.hu/arfolyamok.asmx/GetCurrentExchangeRates`.

## Verification

**Commands:**
- `python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py` -- expected: all pass with no network
