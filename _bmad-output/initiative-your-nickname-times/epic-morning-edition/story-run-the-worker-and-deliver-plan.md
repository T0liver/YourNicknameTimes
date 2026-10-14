---
title: '1.4 Run the worker and deliver'
type: 'feature'
ticket: '4'
created: '2026-10-14'
status: 'built'
baseline_revision: 'c62bb7b03de6fada2344aa90bdf51f58fb0cf60a'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/delivery.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/stack.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A finished `edition.json` and `print.pdf` sit on disk. Nothing schedules a run, holds it, prints it when CUPS finishes, or uploads the cloud copy.

**Approach:** Extend the story 3 database with runs, jobs, heartbeat, and alerts. A worker with no web service renders `cloud.pdf` and `preview.png` from that `edition.json`, then delivers from hold jobs and the print and upload switches.

## Boundaries & Constraints

**Always:** Both PDFs come from the written `edition.json`. Trimmed cloud output drops `dek`, `place`, `attendees`, and prep notes; `cloud_level` `full` keeps them. `preview.png` is the full print page. The run is printed when CUPS reports the job finished. Hold, reject, and regenerate are job rows. The worker inserts the hold row, and a hold row marked `approved` delivers. Reject stops delivery and leaves the files. Regenerate collects again and writes a new `AS OF`. Weekday start 06:30; weekend start 08:00 when that edition is on, otherwise 06:30. Catch-up runs after NTP sync and before 10:00. Print and upload each have a switch and a one-day override. Local files expire after 30 days. Dropbox keeps `editions/YYYY-MM-DD.pdf` and `latest.pdf`. Duplex, grayscale, A4, 100% scale. Wake every 30 seconds. The third failed upload raises an alert and the next cycle tries again. A failed page build prints nothing and raises an alert.

**Never:** No web process, dashboard, `/status`, systemd unit, or Caddy. Do not import `scripts/smoke/`, pass settings through a shell, add `run_events`, `health_checks`, or `admin`, collect attendees, or delete Dropbox files while retention is indefinite. Leave `newspaper-render` on the fixture.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Approved | Hold job `approved`, switches on, CUPS completed | One `lp`; dated PDF and `latest.pdf` uploaded; run printed | No error expected |
| Accepted | CUPS job still processing | Unprinted; poll the same id next cycle | No second `lp` |
| Held | Fresh build, hold on | Copies exist; no print or upload; hold job pending | Info alert after 1 hour |
| Reject | Pending reject job | No delivery; PDFs stay; run `rejected` | No `run_failed` |
| Regenerate | Pending regenerate job | New `AS OF`; hold again when hold is on | Failed rebuild prints nothing |
| Bad page | `build_edition` returns 1 | No `print.pdf`, no `lp` | `run_failed` |
| Clock | NTP off, or past 10:00 with no edition | No catch-up | `deadline` only past 10:00 with NTP on |
| Catch-up | NTP on, missed 06:30, now 09:00 | One build | Skip when today's edition exists |
| Override | Upload-only for today, job approved | Upload; no `lp` | Missing token is an upload failure |
| Retention | Local 30 days, Dropbox indefinite | Expired local directory deleted | Dropbox files stay |
| Trim | Trimmed snapshot with `place`, `dek`, prep | Cloud HTML omits them; print keeps them | `full` keeps them |
| Uploads | Three failures | Alert `dropbox`; retry next cycle | PDF kept |

</frozen-after-approval>

## Code Map

- `newspaper/db.py` — `DEFAULT_SETTINGS` L14, `SCHEMA` L62, `init_data` L112, `ensure_secrets` L191. Add the four tables. Keep the five-version prune. Do not rewrite an existing secrets file.
- `newspaper/edition_build.py` — `run` L243 writes the JSON and `print.pdf`, then records the edition. Worker calls it, then renders copies from the loaded JSON before `lp`.
- `newspaper/render.py` — Reuse `build_document` L33 and `render_edition` L38 for `cloud.pdf`. `preview.png` is the full snapshot.
- `newspaper/sources/caldav_source.py` — `_today_row` L288, `_week_row` L300, `_due_line` L316. Keep print strings. Add `place` on a week row when set, and `detail` when a due item has a description. The template prints `item.text` for a mapping. Cloud trim clears `prep` and drops `place`, `dek`, `detail`, `attendees`, and a week suffix ` ({place})`.
- `newspaper/http.py` — GET only. Upload POSTs to `https://api.dropboxapi.com` and `https://content.dropboxapi.com`.
- `tests/test_edition.py` L366 forbids the four new tables; update it. L376 compares settings to `DEFAULT_SETTINGS`.
- `tests/conftest.py` blocks `requests.get`. Inject CUPS and Dropbox. Copy `lpstat`, the refresh-token POST, and `timedatectl show -p NTPSynchronized` from `scripts/smoke/`. Do not import those files.

## Tasks & Acceptance

**Execution:**
- [x] `newspaper/db.py` and `data/secrets.env.example` -- Add the four tables, delivery settings, and Dropbox secret lines.
- [x] `newspaper/render.py`, `newspaper/sources/caldav_source.py`, and `newspaper/templates/edition.html.j2` -- Render trimmed `cloud.pdf` and a full-page `preview.png` from `edition.json`.
- [x] `newspaper/worker.py` and `pyproject.toml` -- `newspaper-worker` cycle: NTP, schedule, catch-up, jobs, CUPS, Dropbox, heartbeat, alerts, local retention.
- [x] `tests/test_worker.py`, `tests/test_edition.py`, and `README.md` -- Cover the matrix with fakes, and document the worker command plus the secret lines.

**Acceptance Criteria:**
- Given no web process and a hold job marked approved, when CUPS finishes, then the dated PDF and `latest.pdf` are uploaded and the run is printed.
- Given NTP is synced and the clock is before 10:00, when today's edition is missing, then one catch-up build runs.
- Given local retention has expired, when a cycle runs, then those local files are gone and the Dropbox copies remain.

## Implementation Notes

- `newspaper-worker` runs `cycle` every 30 seconds. Tests call `cycle` with a clock, a CUPS fake, and a Dropbox poster. `.venv/bin/python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py tests/test_worker.py`: 75 passed.
- `preview.png` is a PNG of the full print page via `pdftocairo` (`poppler-utils`). The README apt line includes that package. A missing binary fails the copy step, raises `run_failed`, and does not print.
- `dropbox_retention_days` is stored and unused. The worker does not delete Dropbox files.
- A due item's print sentence stays in the cloud copy after the `detail` key is removed. `dek`, `place`, `attendees`, and prep notes are omitted.

## Plan Change Log

## Review Triage Log

- 2026-10-14 quick pass: high=2 medium=1 low=0 false=0 maybe-false=0
- high / patch — `seed` writes delivery defaults only into an empty settings table. `load_settings` returns the stored JSON, so an existing story 3 row has no `hold_mode`, `print_enabled`, `upload_enabled`, or `local_retention_days`. Those `.get` calls then skip hold, print, upload, and pruning, and the run is stored as done.
- high / patch — `_edition_exists` treats any `runs` row as today's edition. A failed page build inserts that row and does not call `record_edition`, so a later cycle before 10:00 does not catch up and the deadline alert is suppressed. The matrix skips a build only when today's edition exists.
- medium / patch — `_print_job` submits `lp` again when the previous submit raised before a job id was stored. A canceled or aborted job stays `delivering` with `printed` 0, so the run never reaches `done`, `done_degraded`, or `failed`. Delivery leaves the PDF for a manual reprint.

## Design Notes

Settings keys: `weekday_start` `06:30`, `weekend_start` `08:00`, `latest_acceptable` `10:00`, `hold_mode` true, `auto_approve` false, `auto_approve_time` `""`, `print_enabled` true, `upload_enabled` true, `override_date` `""`, `override_print` null, `override_upload` null, `cloud_level` `trimmed`, `local_retention_days` 30, `dropbox_retention_days` null, `duplex` true, `printer_name` `""`. Override matches `override_date`. Empty `printer_name` skips `lp`.

Job kinds: `hold`, `reject`, `regenerate`. Status: `pending`, `approved`, `done`, `failed`. A missing copy skips delivery, writes `run_failed`, and leaves `print.pdf` for the next cycle.

`lp` list: `-d` printer, `-o media=A4`, `-o ColorModel=Gray`, `-o print-scaling=none`, `-o sides=two-sided-long-edge` or `sides=one-sided`. Store the job id. Canceled or aborted raises `printer`.

Secrets `DROPBOX_REFRESH_TOKEN`, `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`. Upload `cloud.pdf` to `/editions/YYYY-MM-DD.pdf` and `/latest.pdf`, overwrite. Heartbeat stores time, `ntp_synced`, printer state, `disk_free_mb`. Alerts: `run_failed`, `printer`, `dropbox`, `awaiting_approval`, `deadline`, `degraded`. Source `failed` ends `done_degraded`. NTP command has no shell; tests pass a boolean.

## Verification

**Commands:**
- `.venv/bin/python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py tests/test_worker.py` -- expected: all pass with no network
