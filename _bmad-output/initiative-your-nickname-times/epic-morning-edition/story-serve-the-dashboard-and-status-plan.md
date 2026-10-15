---
title: '1.6 Serve the dashboard and /status'
type: 'feature'
ticket: '6'
created: '2026-10-15'
status: 'built'
baseline_revision: 'a3582ba4ab1883fa0d926d390bf797f0c85df02a'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 2
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/status-api.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/dashboard.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/stack.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The worker holds an edition and writes a heartbeat, but nothing on this machine lets the operator sign in and approve it, and a checker has no `/status` to read.

**Approach:** A localhost web process reads the story 4 database. Signed-in pages update the hold job and insert reject, regenerate, `run_now`, `preview`, `reprint`, and `reupload` jobs. The worker consumes them. `GET` and `HEAD /status` stay open and follow status-api.md.

**Decision:** The web process inserts `run_now`, `reprint`, and `reupload`, and this story teaches the worker to consume them. The web process never calls `lp`. `run_now` builds today's edition even when one exists, then uses the existing hold and delivery path. Preview inserts kind `preview`, builds the same way, and records the run finished with no hold job, no `lp`, and no upload. `reprint` prints that edition's existing `print.pdf` through the worker's CUPS client and does not rebuild. `reupload` uploads that edition's existing `cloud.pdf` through the worker's Dropbox client and does not rebuild. A second click does not insert another pending row of the same kind for the same date. Reprint and re-upload leave a finished run's status unchanged.

## Boundaries & Constraints

**Always:** Listen on `127.0.0.1:8080` only. The web process never calls `lp`, CUPS, or Dropbox. Approve sets the pending `hold` job to `approved`. Reject, regenerate, `run_now`, `preview`, `reprint`, and `reupload` insert one pending row of that kind. The worker consumes those rows. `/status` uses the status-api.md names, `Cache-Control: no-store`, 200 for `ok` and `degraded`, 503 for `down`, and `?strict=1` returns 503 for `degraded`. The body has no task or event text, feed URLs, secrets, alert message text, or nickname. PDF downloads require a session. One admin password is stored as a scrypt hash in `secrets.env`. POSTs use a session cookie and CSRF. Pages are server-rendered, styled with CSS variables, and the banner polls run status with HTMX. Checks come from the latest heartbeat, the latest run's `sources`, alerts, and settings. The payload is cached for a few seconds. Each `/status` request records its time for the home page.

**Never:** No settings forms. No setup checklist, phone-layout pass, or Hungarian UI (story 7). No Caddy, bearer token, extra status port, or login rate limit (story 8). Do not add `run_events`, `health_checks`, or `admin`. Do not print or upload from the web process. Do not change how hold, reject, and regenerate already behave.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sign in | Matching password | Session and the home page | A mismatch stays on the login form |
| Approve | Pending hold for today | That job becomes `approved`; the banner polls `awaiting_approval`, then `delivering`, then `done` or `failed` | The web process does not call `lp` |
| Reject | Operator rejects the held edition | One pending `reject` row | A second click does not insert another pending reject |
| Regenerate | Operator regenerates | One pending `regenerate` row | A second click does not insert another pending regenerate |
| Run now | Pending `run_now` | Worker builds even when today's edition exists, then holds or delivers from settings | The web process does not call `lp` |
| Preview | Pending `preview` | Files are written; no hold job, no `lp`, no upload | A failed build prints nothing |
| Reprint | Pending `reprint` and `print.pdf` exists | Worker submits one `lp` of that file and leaves a finished run's status unchanged | A missing PDF marks the job failed and does not call `lp` |
| Re-upload | Pending `reupload` and `cloud.pdf` exists | Worker uploads that file and leaves a finished run's status unchanged | A missing PDF marks the job failed |
| PDF | Logged out, then logged in | Logged out is sent to login; logged in receives `print.pdf` or `cloud.pdf` | Missing file is 404 |
| Open status | No cookie | 200 JSON when the rules say `ok` | `HEAD` matches the status and headers and has an empty body |
| Held edition | Heartbeat under 2 minutes, `ntp_synced` 1, disk at least 100 MB, `printer_state` contains ` is idle`, sources `ok`, no warning alert, run `awaiting_approval` | `status` `ok` and HTTP 200 | The hold alone does not degrade |
| Worker down | Newest heartbeat older than 2 minutes | HTTP 503, `status` `down`, `worker.alive` false | A stopped web process never answers |
| Printer | `printer_state` is `unknown` or has no ` is idle` | HTTP 200, `degraded`; `?strict=1` is 503 | Empty state is `unknown` and stays `ok`. `checks.printer.state` is `idle` or `problem` |
| Deadline | Past `latest_acceptable`, no edition, no `delivering` or `awaiting_approval` run | HTTP 503, `down` | |
| Disk or clock | `disk_free_mb` under 100, or `ntp_synced` 0 with uptime over 1 hour | HTTP 503, `down` | |
| Bad database | SQLite cannot be read | HTTP 503, `status` `down` | Body has no path and no SQL |
| Private text | Run sources and edition text include a feed URL and a calendar title | Those strings are absent from `/status` | Alert `message` values are absent too |

</frozen-after-approval>

## Code Map

- `newspaper/worker.py` — `_insert_hold` L567 writes `hold`/`pending`. Delivery finishes a hold only when status is `approved` (L397). `_reject_pending` L537 and `_run_regenerate` L245 consume pending rows. `_print_job` L407 sets the run to `delivering`, so reprint must not call it. `_upload` L448 increments `upload_attempts` on the run. `_heartbeat` L676 stores `recorded_at`, `ntp_synced`, `printer_state`, `disk_free_mb`. `SystemCups.printer_state` L67 returns `""`, the first `lpstat -p` line, or `unknown`. `lp_argv` builds the `lp` argument list. Add consumers for `run_now`, `preview`, `reprint`, and `reupload` without changing hold, reject, or regenerate.
- `newspaper/db.py` — `SCHEMA` L87, `connect` L176, `ensure_secrets` L270, `read_secrets` L339, `load_settings` L234. Append `ADMIN_PASSWORD_HASH=` and `SESSION_SECRET=` the same way `OPENROUTER_API_KEY` is appended. Do not rewrite an existing secrets file. `connect` sets `timeout` and `PRAGMA journal_mode=WAL` so the web process and the worker can share the file.
- `newspaper/edition_build.py` — `meta.sources` L177. `caldav` is `ok` or `failed`. `feeds` is `failed` or a name-to-`ok`/`failed` map. `weather`, `daily`, and `almanac` children use `failed`. `llm.py` L79 sets `sources.model` to `failed`. `llm/requests.json` is `{"count": N}`.
- `tests/test_edition.py` L470 — tables must stay disjoint from `run_events`, `health_checks`, and `admin`. L478 compares `secrets.env` to `SECRETS_TEXT`.
- `tests/conftest.py` L7 blocks `newspaper.http` `requests.get` and `requests.post`.
- `pyproject.toml` — scripts L21. Jinja2 is already a dependency. FastAPI is not.

## Tasks & Acceptance

**Execution:**
- [ ] `newspaper/db.py` and `data/secrets.env.example` -- Append the admin hash and session secret lines, and open SQLite with a timeout and WAL. -- Login can start without a settings form, and both processes can write.
- [ ] `newspaper/status_report.py` -- Build the status-api.md object and HTTP code from a connection, clock, uptime, and temperature. -- The matrix stays free of the request layer.
- [ ] `newspaper/worker.py` and `tests/test_worker.py` -- Consume pending `run_now`, `preview`, `reprint`, and `reupload` in `cycle`. -- The web process inserts those rows and the worker prints or uploads.
- [ ] `newspaper/web.py`, `newspaper/templates/`, `newspaper/static/dashboard.css`, and `pyproject.toml` -- `newspaper-web` on `127.0.0.1:8080`: login, home, editions, actions, PDF downloads, `/status`. -- The process inserts the jobs and does not print.
- [ ] `tests/test_status.py`, `tests/test_web.py`, `tests/test_edition.py`, and `README.md` -- Cover the matrix with a fake clock and TestClient. Document the command and the one-time password line. -- No network.

**Acceptance Criteria:**
- Given a held edition and a signed-in operator, when they approve it, then the pending hold job is `approved` and the banner shows the run status changing.
- Given the worker heartbeat is older than two minutes, when a checker calls `GET /status`, then the response is 503 and `status` is `down`.
- Given a heartbeat whose printer state is not idle, when a checker calls `GET /status`, then the response is degraded, and `?strict=1` is 503.
- Given the operator stops the web process, when a checker calls `/status`, then the connection fails.

## Implementation Notes

- Reprint keeps the CUPS job id on a finished run and stamps the pending job, so the next cycle polls that id after the worker process restarts. A new reprint still submits once, because a fresh job has matching created and updated times.

## Plan Change Log

- 2026-10-15 — Quick review: a preview inserted a second run, so reject, regenerate, and the banner followed that row and a held edition no longer behaved as before. Amended the design notes so a preview refreshes `cloud.pdf` and `preview.png`, and inserts a finished run only when that date has no non-failed run. Reprint stores its CUPS id in `reprint.cups` beside the PDF and does not write `runs.cups_job_id`. Known-bad state avoided: reject marking the hold done while the held run stays `awaiting_approval`, and a second `lp` after a worker restart. KEEP: localhost bind, scrypt login, CSRF, open `/status` rules, one pending job per kind and date, `run_now` through `_after_build`, and reprint leaving a finished run's status unchanged.
- 2026-10-15 — Quick review, second pass: a pending preview from yesterday built the new day and inserted a finished run, so the scheduled edition did not run. Amended the design notes. `run_now` and `preview` run only when NTP is synced and the job date is the cycle's date. Other pending rows stay pending. `HEAD /status` sends `Content-Type: application/json` and `Cache-Control: no-store` with an empty body. Pending inserts use `BEGIN IMMEDIATE`. A failed reprint deletes `reprint.cups`. An empty `printer_name` does not call `lp`. Known-bad state avoided: the morning build skipped, two reprints from one double click, and a later reprint polling a dead CUPS id. KEEP the previous list.

## Review Triage Log

- 2026-10-15 quick pass: high=1 medium=2 low=0 false=1 maybe-false=0
- medium / patch — `newspaper/worker.py` `_run_preview` never calls `copy_fn`. `build_edition` writes `edition.json` and `print.pdf` only. A later re-upload can send an older `cloud.pdf`. Moot on this loopback.
- high / bad_plan — `_insert_finished_run` adds a second run. `_reject_pending` and the banner use the newest row, so reject marks the hold done and leaves the held run `awaiting_approval`. `_edition_exists` then skips the scheduled build.
- medium / bad_plan — `_reprint` keeps the CUPS id in memory, and writes `runs.cups_job_id` only for a finished run. A restart while reprinting a held edition calls `lp` again. Comparing `updated_at` to `created_at` also misses a save when both stamps share a second.
- false — `status_report.py` does not map `daily` or `xkcd`. status-api.md has no check for them. A held run stays `awaiting_approval`, and `_overall` degrades a run only at `failed` or `done_degraded`. A failed feed still degrades through `checks.rss`.
- 2026-10-15 quick pass 2: high=1 medium=4 low=0 false=0 maybe-false=0
- medium / patch — `_reprint` marks a missing PDF failed and leaves `reprint.cups`. The next reprint reads that id and does not call `lp`. `job_state` also stays `processing` when the id is gone from `lpstat`, so that row never finishes. Moot on this loopback.
- low / patch — `HEAD /status` omits `Content-Type: application/json`. `Cache-Control: no-store` is present, and `Content-Length: 0` matches the empty body. Moot on this loopback.
- high / bad_plan — `_run_now` and `_run_preview` build `moment.date()` with no NTP check. A preview still pending after midnight inserts a finished run for the new day, and `_edition_exists` then skips the scheduled build.
- medium / patch — `_insert_pending` checks then inserts with no immediate transaction. Two overlapping posts can both insert. Moot on this loopback.
- medium / patch — `_reprint` calls `lp` when `printer_name` is empty. Delivery does not. Moot on this loopback.
- 2026-10-15 quick pass 3: high=1 medium=3 low=0 false=0 maybe-false=0
- high / patch — Run now and Preview posted the latest run date. After yesterday's edition, the worker left today's click pending. The forms now post the dashboard's today.
- medium / patch — `_now` was fixed to Europe/Budapest. It now uses `settings["timezone"]`.
- medium / patch — Regenerate on an older edition page rebuilt today, because the worker already ignores the job date. Regenerate now sits on the home page for today. Reprint and re-upload stay on the edition page.
- defer — An empty OpenRouter key sets `meta.mode` to `degraded` and does not set `sources.model`. `/status` stays ok. That flag is story 5's, and this story reads `sources.model`.

## Design Notes

On first start, an empty `ADMIN_PASSWORD_HASH` gets a generated password, the hash is written, and `admin password:` is printed once. An empty `SESSION_SECRET` is generated the same way and is not printed.

`/status` `version` is the installed `newspaper` version. `down` wins over `degraded`. A check status of `unknown` is neither red nor yellow, so it does not degrade the result. Empty `printer_state` is that case: story 4 writes `""` when `printer_name` is empty, and `SystemCups` writes `unknown` when `lpstat` returns no line. Warning and error alerts are severity `warning` and make the result degraded. The worker stores `deadline`, `degraded`, and `awaiting_approval` as `info`, so those rows do not. Deadline `down` is computed from the clock, `latest_acceptable`, and runs, using the same edition test as `_edition_exists`. `last_success` is the latest run's `finished_at` when that check is `ok`, otherwise null. Feed messages are counts only. `checks.printer.message` and other messages stay null. `daily_limit` is null. Wi-Fi on the home page is `unknown`. CPU temperature is null when the thermal file is missing. The route cache is a few seconds. Tests build the app with the cache off. `HEAD /status` is registered on its own. Heartbeat timestamps are offset-aware.

The home page lists editions inside `local_retention_days`, with both PDF links, run fields, `edition.json`, and `llm/` files behind login. The banner names the latest run and offers Approve and Reject while a hold is pending. Run now and Preview sit on the home page. Reprint and re-upload sit on the edition page.

`run_now` and `preview` run before the scheduled build, and only when NTP is synced and the job's `edition_date` is the cycle's date. Otherwise the row stays `pending` and does not change that day's run. Both call the existing builder. `run_now` then calls `_after_build`. After a successful preview, call the copy function so `cloud.pdf` and `preview.png` match that build. If that date already has a non-failed run, do not insert another `runs` row. The banner, reject, and regenerate keep that row, and the hold job stays as it was. If no such run exists, insert one finished run, `done` or `done_degraded`, with no hold job, so the scheduled build does not also run. A failed preview still prints nothing and inserts a failed run only when the date has no non-failed run.

Reprint calls `cups.submit` with `lp_argv` on `print.pdf`. An empty `printer_name` marks the job `failed` and does not call `lp` or raise a printer alert. While CUPS still reports processing, the reprint job stays `pending`. Write the CUPS id to `reprint.cups` in that edition directory and read it on the next cycle, including after a restart. Do not write `runs.cups_job_id` and do not change the run status. Delete `reprint.cups` whenever the job becomes `done` or `failed`, including a missing PDF. If `lpstat` no longer lists that id, mark the job `failed` and delete the file. Re-upload calls `dropbox.upload` on `cloud.pdf`. A failure marks the job `failed` and raises the existing printer or Dropbox alert. It does not use `_print_job` or `_upload`.

`HEAD /status` uses `Content-Type: application/json` and `Cache-Control: no-store`, with an empty body. Inserting a pending job takes `BEGIN IMMEDIATE` before the existence check, so two overlapping posts leave one row.

## Verification

**Commands:**
- `.venv/bin/python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py tests/test_worker.py tests/test_llm.py tests/test_status.py tests/test_web.py` -- expected: all pass with no network

**Manual checks (if no CLI):**
- Unplug the printer, leave the worker running, and confirm `GET /status` becomes `degraded` from the new heartbeat. Plug it back in and confirm a later heartbeat returns the printer check to `ok`.
