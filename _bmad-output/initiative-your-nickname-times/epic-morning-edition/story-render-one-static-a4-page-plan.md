---
title: '1.2 Render one static A4 page'
type: 'feature'
ticket: '2'
created: '2026-10-13'
status: 'built'
baseline_revision: '7500a0eb5824f6f88ad42ed94f2674321d05c80d'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/edition.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Later stories have no A4 template to fill, and there is no Python package or WeasyPrint path yet. Milestone 1 is the first printed page.

**Approach:** Add the app package and WeasyPrint libraries, ship the kit's OFL fonts, and turn its table grid and CSS into one Jinja2 A4 template that later stories fill. Fixture Hungarian copy proves glyphs, quotes, and hyphenation. The operator prints that PDF on the Pi and writes down the CLI render time.

## Boundaries & Constraints

**Always:**
- One A4 page via WeasyPrint. `@page { size: A4; margin: 0 }`. Content width 7.63 in (0.32 in side margins). 6 columns of about 1.197 in, 0.09 in gutters. Span-4 about 5.06 in, span-2 about 2.48 in, span-2 with hairline 2.57 in so 5.06 + 2.57 = 7.63.
- Keep the kit's table grid, type classes, and masthead faces. Copy Chomsky, Libre Franklin, and Newsreader into the app with OFL 1.1 files. Do not commit `The-Firstname-Times-Setup-Kit-v17.3/`.
- `lang="hu"`. Nameplate `{Nickname} Times`. Fixture nickname includes `ő`. Copy includes `ű`, Hungarian quotes `„ ”`, and a long headline that hyphenates. Empty motto omits the motto node so no gap remains. Weekend fixture shows the static sun icon beside the dateline.
- The same template is what story 1.3 fills. Empty blocks are omitted so neighbors can widen.
- CLI prints elapsed render seconds. Operator prints with `lp` and records that number.

**Never:**
- Collectors, `newspaper.db`, `data/secrets.env`, FastAPI, the worker, overflow dropping, `cloud.pdf`, live CalDAV/RSS/weather, Chrome as renderer, generated art, or edits to `scripts/smoke/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fixture weekday/weekend page | Packaged Hungarian fixture, weekend on | Exactly one A4 page; nameplate has `ő`; body has `ű` and `„ ”`; a news headline hyphenates; sun icon is present | Render error fails the command |
| Empty motto | `motto` empty | Motto row absent; nameplate sits under the top of the masthead with no extra gap | No error expected |
| Missing WeasyPrint libs | Pango/HarfBuzz/GDK-Pixbuf absent | Command exits non-zero with the library error | Do not catch and hide WeasyPrint import/runtime errors |

</frozen-after-approval>

## Code Map

- `The-Firstname-Times-Setup-Kit-v17.3/layout/edition.css` -- Letter source to copy and retune. Keep masthead, type, list, weather, band. Drop page 2 to 4 puzzle, jumble, and comic-strip rules. `.hed-a1` is `hyphens: none`; news heads here are `auto`.
- `The-Firstname-Times-Setup-Kit-v17.3/layout/template.html` -- Masthead + span-4 lead + span-2 rail + 3-col `.band` only. Ignore pages 2 to 4 and placeholder copy. WeasyPrint ignores `td` padding; keep nested inset/margin.
- `The-Firstname-Times-Setup-Kit-v17.3/fonts/` -- Copy `@font-face` files; skip unused `NewsreaderDisplayBold.ttf`. Chomsky has `őűŐŰ` and `”`, not `„`. Nameplate: `"Chomsky", "Libre Franklin", serif`. Quotes stay in Newsreader.
- `The-Firstname-Times-Setup-Kit-v17.3/requirements.txt` -- `weasyprint==69.0`. Pyphen ships `hu_HU`.
- `scripts/smoke/` -- Do not change. Story 1.3 still owns `newspaper.db`.
- `.gitignore` -- Kit stays ignored. Do not ignore shipped app fonts.
- `README.md` -- Add Pi packages, render, `lp`, and where to write the time.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` -- Add the `newspaper` package (Python 3.11+), `weasyprint==69.0`, Jinja2, pytest, and a `newspaper-render` console script -- first app scaffold; pin the kit's WeasyPrint.
- [ ] `newspaper/static/fonts/` and `newspaper/static/licenses/` -- Copy kit `@font-face` files and add each family's OFL 1.1 text -- app ships fonts; kit stays gitignored.
- [ ] `newspaper/static/edition.css` -- A4 `@page`, `.sheet`/`.canvas` 7.63 in, span-4/span-2 retune, masthead/type/list/weather/band kept, news heads `hyphens: auto`, Chomsky fallback stack -- edition.md grid.
- [ ] `newspaper/static/icons/weekend-sun.svg` -- Small black-on-white sun -- static asset; kit has none.
- [ ] `newspaper/templates/edition.html.j2` -- One `.sheet`; `lang="hu"`; masthead (nameplate, optional motto, rules, dateline, optional sun); lead/rail/band slots for News, Today, This week, Weather, Prep, Due, Overdue, Daily item, Almanac -- later stories fill these; omit empty slots.
- [ ] `newspaper/fixtures.py` and `newspaper/render.py` -- Hungarian fixture (`ő` in the nickname, `ű` and `„ ”` in copy, long hyphenating headline, weekend on). Jinja2 + WeasyPrint to PDF; print `render_seconds=` -- no DB.
- [ ] `tests/test_render.py` -- I/O matrix: one A4 page, extracted glyphs and quotes, hyphen in the fixture headline, omitted motto node, sun when weekend.
- [ ] `README.md` -- Pi packages, `pip install -e .`, render, `lp`, write down `render_seconds`.

**Acceptance Criteria:**
- Given the packaged fixture, when `newspaper-render` writes a PDF, then it is exactly one A4 page, the nameplate reads `{Nickname} Times` with `ő`, the page shows `ű` and `„ ”`, and a news headline is hyphenated.
- Given an empty motto, when the template renders, then no motto element is in the HTML and the nameplate has no extra gap above it.
- Given Pango, HarfBuzz, and GDK-Pixbuf on the Pi, when the operator runs the render command, then stdout includes `render_seconds=` and `lp` can print the PDF with usable margins; the operator writes that time down.

## Implementation Notes

- Added `newspaper/` with WeasyPrint 69, Jinja2, the A4 CSS/template, shipped OFL fonts, `weekend-sun.svg`, the Győző fixture, and `newspaper-render`.
- `tests/test_render.py`: 7 passed in `.venv` (`python -m pytest tests/test_render.py`).
- Operator still prints with `lp` on the Pi and writes down `render_seconds`.
- A longer nickname than `Győző` can overflow the 62pt nowrap nameplate.

## Plan Change Log

## Review Triage Log

- 2026-10-13 quick pass 1: high=0 medium=1 low=1 false=0 maybe-false=0
- medium / patch — `newspaper/templates/edition.html.j2` empty Almanac/Weather dicts still print headings. Verified: `has_almanac = almanac` is true for `{"lines": []}`, so the Almanach label still renders and the rail does not widen. Same for a weather dict with empty strings. Empty lists do omit. Later stories that pass a dict with no inner content would print a hollow block, against the empty-block rule.
- low / patch — `newspaper/templates/edition.html.j2` weekend masthead has no greeting line. Verified: only the sun img is gated on `weekend and show_sun`; fixtures have no greeting key. This story's AC names the sun, not the greeting, but the template is what story 1.3 fills and edition.md puts a greeting beside the dateline.

## Design Notes

Blocks on the kit A1 frame: News, Today, This week in the span-4 lead; Weather and Almanac in the span-2 rail; Prep, Due/Overdue, and Daily item in the band. Fixture: nickname `Győző`, volume 1, dateline `Vol. 1 · 2026. szeptember 21. · hétfő · Budapest · AS OF 06:30`. Sheet padding stays 0.28 / 0.32 / 0.50. Letter CSS 7.86 / 5.21 / 2.56 / 2.65 becomes 7.63 / 5.06 / 2.48 / 2.57.

## Verification

**Commands:**
- `python -m pytest tests/test_render.py` -- expected: all I/O cases pass
- `newspaper-render --out /tmp/edition.pdf` -- expected: one PDF and a `render_seconds=` line

**Manual checks (if no CLI):**
- On the Pi: install `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libgdk-pixbuf-2.0-0`, render, `lp /tmp/edition.pdf`, confirm margins, write down `render_seconds`.
