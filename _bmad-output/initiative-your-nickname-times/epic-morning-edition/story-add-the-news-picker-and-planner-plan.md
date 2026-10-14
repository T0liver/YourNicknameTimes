---
title: 'Add the news picker and planner'
type: 'feature'
ticket: '5'
created: '2026-10-14'
status: 'built'
baseline_revision: 'b66b851d3ea7c5a7d68a327fa4ca2cd22fe39bb0'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/llm.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `assemble_snapshot` still builds with the model off, so the edition never asks OpenRouter to choose news or write tomorrow's notes.

**Approach:** From that compose step, call OpenRouter for news IDs and one prep note per tomorrow item. Retry a failed call once, then use story 1.3's builder for that block. Apply the news quotas in code after the pick. Store each prompt, response, answering model, and the request count in the edition folder. If a planner note is what still spills the page, cut that note and print the page.

## Boundaries & Constraints

**Always:**

- News JSON is `{"picks": [{"id": 12, "category": "interest"}]}`. The page prints the feed headline, publisher, and time.
- Planner JSON is `{"notes": [{"id": 1, "note": "..."}]}`. Drop a note over 120 characters. Keep the item's own line.
- Drop unknown ids. Keep at most four interest and four local picks, in the model's order.
- After a schema or transport failure, retry once with a stricter prompt, then use `rank_news` or the plain prep list for that block. Mark the run degraded. A blank message is a failed attempt. Do not parse a reasoning trace as the JSON.
- The off switch makes no request and still builds a full edition. Titles-only still calls, without snippets or task descriptions. Sending descriptions is the default.
- Store prompts in `data/editions/YYYY-MM-DD/llm/`. Tests inject the poster and make no live call.
- When the page is still over one page, drop planner notes one at a time, last note first, and keep each item's line. Record the drop. A leftover note does not fail the run.

**Never:**

- Do not change worker delivery, overflow floors, cloud trim, or the news row shape.
- Do not resize the comic or the daily item. A page that is still over after the notes are gone fails as it does today.
- No dashboard, `/status`, or model-limit alert.
- Do not import `scripts/smoke/`.
- Do not rewrite an existing secrets file. Append `OPENROUTER_API_KEY=` when that line is missing.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Both calls valid | Model on, key set, valid picks and notes | Quota-limited news from those ids; each prep line gains its note; `llm/` has both calls; `meta.mode` is `on` | No error expected |
| Retry then success | First body fails the schema, second is valid | The second body is used; the request count includes both attempts | No error expected |
| Two failures | Both attempts fail schema or transport | That block uses `rank_news` or the plain prep lines; `sources.model` is `failed`; `meta.mode` is `degraded` | Fallback, run can finish |
| Blank content | `content` empty, reasoning holds example JSON | That attempt fails; one stricter retry; then the deterministic block | Fallback |
| Dirty picks | Unknown ids, a fifth interest pick, a 121-character note | Those picks and that note are absent; valid ones remain | No second call |
| Off | `model_on` false | Full deterministic edition; poster not called; no `llm/` files; `meta.mode` is `off` | No error expected |
| Titles only | `send_task_descriptions` false | Both calls still run; prompts have titles only | No error expected |
| No key | Model on, key empty | No request; deterministic blocks; `meta.mode` is `degraded` | Fallback |
| Spaced key | `OPENROUTER_API_KEY = sk-live` | That key is used | No error expected |
| Note overflow | Page still over one page, one item has a note | Note removed, line stays, trim is `prep note`, render runs again | Fail only if still over after the note is gone |

</frozen-after-approval>

## Code Map

- `newspaper/edition_build.py` — `assemble_snapshot` L77 sets `meta.mode` off. `build_edition` L191 sets it again and calls `drop_one`. Call the model after collect and keep the mode and model it set.
- `newspaper/overflow.py` — `drop_one` L19 drops almanac, extra week rows, extra news, dek, and place, then pops a prep string while more than one remains. Clear a nested note before popping a whole line. Floors stay: week 3, news 4.
- `newspaper/sources/news.py` — `rank_news` L31 is the fallback. Quota 4, pool cap 80. `collect_news` L71 returns printed rows. The picker needs the capped pool and 1-based ids first.
- `newspaper/sources/caldav_source.py` — `_prep_line` L310 is the plain line. `_place` L233 has tomorrow's items.
- `newspaper/db.py` — `DEFAULT_SETTINGS` L19. `seed` L189 fills missing keys. `ensure_secrets` L266 writes only when the file is missing. `read_secrets` L320 keeps the text before `=`.
- `newspaper/http.py` — GET only. Post the OpenRouter chat URL with `check_url` and a 60s timeout. Do not follow redirects.
- `newspaper/templates/edition.html.j2` prints each prep item as a string. `tests/test_edition.py` L221 pops string prep items down to one. `tests/conftest.py` blocks `requests.get` only.

## Tasks & Acceptance

**Execution:**

- [ ] `newspaper/db.py` and `data/secrets.env.example` -- Add `model_on` true, `model_name` `openrouter/free`, and `send_task_descriptions` true. Append the key line. Strip secret keys on read and on the presence check.
- [ ] `newspaper/sources/news.py` and `newspaper/sources/caldav_source.py` -- Expose the capped pool with ids, and tomorrow items with id, title, and description. Keep `rank_news` and `_prep_line`.
- [ ] `newspaper/llm.py` -- Post both calls, validate, retry once, apply quotas, drop long notes, and write the three `llm/` files. Empty content fails the attempt.
- [ ] `newspaper/overflow.py` -- Drop one nested planner note before a whole prep line. Leave the line and the floors.
- [ ] `newspaper/edition_build.py` and `newspaper/templates/edition.html.j2` -- Run the model from compose. Keep `meta.mode` and `meta.model`. Print a note under its line.
- [ ] `tests/test_llm.py`, `tests/conftest.py`, `tests/test_edition.py`, and `tests/test_sources.py` -- Cover the matrix with a fake poster, block `requests.post`, and update mode assertions the new default changes.

**Acceptance Criteria:**

- Given a valid news pick, when the edition is written, then the row's headline, publisher, and time are the feed's, and `llm/news.json` holds the prompt, response, and answering model.
- Given a valid note of at most 120 characters, when the edition is written, then the note sits with its tomorrow item and `llm/requests.json` counts every attempt.

## Implementation Notes

## Plan Change Log

- 2026-10-14 — The review found that a nested planner note could fail the build. The human decided to cut that note and still print. Amended the frozen rules, the matrix, and the overflow task. A leftover planner note must not fail the run. Comic size and the overflow floors stay out of this story.

## Review Triage Log

- 2026-10-14 quick pass: high=0 medium=3 low=1 false=0 maybe-false=0
- medium / patch — `newspaper/db.py` `ensure_secrets` rewrites an existing secrets file with `write_text`, which truncates before the new bytes land. A crash in that window drops the CalDAV password and the Dropbox tokens. The task says to append the missing line. Moot on this loopback.
- low / patch — `_secret_defined` strips the key and `read_secrets` does not. `OPENROUTER_API_KEY = sk-live` counts as present, then `run` misses `OPENROUTER_API_KEY` and the edition degrades with no request. Moot on this loopback.
- medium / patch — `newspaper/llm.py` `_unpack` parses the full `reasoning` string as the answer when `content` is blank. A trace that repeats the prompt's example object is accepted, `meta.mode` stays `on`, and there is no retry. The smoke script only prints the first line of reasoning. Moot on this loopback.
- medium / intent_gap — `drop_one` cannot clear a nested planner note. With one tomorrow item left, a note that still overflows makes `build_edition` return 1 and the worker stores the run as failed. Frozen text says to print the note and not to change overflow floors, and it does not say whether the note is dropped to keep the page.
- 2026-10-14 quick pass 2: high=0 medium=1 low=1 false=0 maybe-false=0
- medium / patch — `apply_model` returns before `_store` when the model is off or the key is empty, and nothing removes `editions/YYYY-MM-DD/llm/`. A later same-day build, including regenerate, keeps the previous prompt files while `meta.mode` is `off` or `degraded`. The off row says that folder is absent.
- low / patch — `_news_prompt` and `_planner_prompt` put the title on the numbered line. `_entries` and `_summary` only strip, so an internal newline stays, while snippets and descriptions are collapsed. That title splits the list the model picks from.

## Design Notes

`seed` adds the three settings to an existing database. Mood is `light` only when the weekend light flag is already set, otherwise `normal`. Notes are Hungarian when `language` is `hu`.

`meta.model` is the distinct answering models in call order, comma-separated, or null. A news id is the pool index. After a note is dropped, that item is a plain string again. `llm/requests.json` is `{"count": N}`. Each call file stores `prompt`, `response`, and `model` per attempt. An empty key writes no `llm/` files.

## Verification

**Commands:**

- `.venv/bin/python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py tests/test_worker.py tests/test_llm.py` -- expected: all pass with no network
