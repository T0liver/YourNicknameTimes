---
id: SPEC-your-nickname-times
companions:
  - edition.md
  - data-sources.md
  - llm.md
  - delivery.md
  - dashboard.md
  - status-api.md
  - architecture-diagrams.md
  - stack.md
  - operations.md
  - milestones.md
sources:
  - ../../../newspaper-spec-v1.1.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Your Nickname Times

## Why

This is a vision to realize: a morning paper that a Raspberry Pi prints for one operator. The Pi collects that person's calendar, tasks, news, weather, almanac, currency rates, and one comic or puzzle, lays them on a single A4 page, prints it, and can upload a copy. A dashboard on the local network configures the system and shows whether it is healthy. An external checker reads `/status` and treats a missing response as down. The paper and the dashboard default to Hungarian. Planning for this version is finished, and the software is not built yet.

## Capabilities

- **CAP-1**
  - **intent:** The system can produce one A4 morning edition that contains the day's news, calendar, tasks, weather, almanac, rates, and a single comic or puzzle.
  - **success:** A run with fixture or live data yields exactly one A4 page. Empty blocks collapse, neighbors widen, and the page does not print "None". Overflow drops items in the order in edition.md and records every drop. If the PDF cannot be built, or still exceeds one page after that trimming, the run fails and nothing prints.

- **CAP-2**
  - **intent:** The operator can set the nameplate to `{Nickname} Times`, an optional motto, and a lighter Saturday and Sunday edition.
  - **success:** Until a nickname is saved, the title is "Your Nickname Times". An empty motto leaves no gap under the nameplate. The dateline shows volume, date, weekday, city, and the time collection started, in the paper's language. With the weekend switch on, Saturday and Sunday follow the lighter rules in edition.md, including the default 08:00 start and the greeting "Yippie, weekend! You earned it!". With the switch off, those days use the weekday edition.

- **CAP-3**
  - **intent:** The operator can discover calendars and task lists on their CalDAV server, choose which to include, and see today, the coming week, tomorrow's preparation, tasks due this week, and overdue tasks on the page.
  - **success:** Calendar and tasks come from one CalDAV server, entered in settings. A fresh install has no host filled in. Discovery lists collections with `VEVENT` and `VTODO` support. Recurring events expand to occurrences. Completed and cancelled tasks are omitted, and a recurring task shows the current occurrence. Date-only and date-time values appear in the configured timezone, default Europe/Budapest. Undated open tasks sit on an "anytime" line. Overdue tasks are oldest first and show how many days late.

- **CAP-4**
  - **intent:** The operator can add, edit, test, enable, tag, weight, and import or export RSS feeds, and the edition can print recent headlines in each feed's own language.
  - **success:** Feed URLs live in settings, not in the fetch code. A fresh install starts with Telex (`https://telex.hu/rss`, local) and Wired (`https://www.wired.com/feed/rss`, interest). An OPML file round-trips through import and export. The edition keeps entries from the last 24 hours, drops entries with no publish time unless that filter is turned off, and collapses duplicates by URL and then by fuzzy title. About four interest items and about four local items appear, and code enforces that quota. The printed line is the fetched headline, publisher, and time.

- **CAP-5**
  - **intent:** The operator can show today's weather and a short outlook, and can toggle sunrise and sunset, moon phase, name day, on this day, and the EUR, USD, and CHF rates against HUF.
  - **success:** All five extras start enabled, each with its own toggle. A weather failure prints "Forecast unavailable" and no invented numbers. A failed extra is omitted and no estimated value is substituted. Name days come from the static table in data-sources.md. On-this-day text follows the paper language, and falls back to English when that language has no feed. Rates are the MNB daily quotes for EUR, USD, and CHF in HUF, printed with value, date, and source. A weekend or holiday shows the last published date. Sunrise, sunset, and moon phase still compute from local coordinates when the network is down.

- **CAP-6**
  - **intent:** The operator can set a weekday rotation so each edition includes exactly one daily item, either a comic or a puzzle.
  - **success:** The default rotation is xkcd on Monday, Wednesday, Friday, and Sunday, and sudoku on Tuesday, Thursday, and Saturday. The comic is a previously unseen xkcd strip, in grayscale, with its English alt text as the caption and the credit `xkcd.com, CC BY-NC 2.5`. Interactive, very tall, and very wide strips are skipped. If the fetch fails, that day prints the puzzle instead. Sudoku is generated in code with one verified solution, at easy difficulty on weekend editions.

- **CAP-7**
  - **intent:** The operator can let a language model pick news item IDs and write one preparation note per tomorrow item from that item's own text, or turn the model off and still receive a full edition.
  - **success:** With the model on, a response that fails the schema in llm.md is retried once with a stricter prompt, then that block uses the deterministic fallback. Unknown IDs are dropped, quotas apply after the pick, and over-length notes are rejected. The global off switch builds the whole paper without a model call: news ranked by recency, feed weight, and keyword score; a plain tomorrow list; an expanded almanac. Prompts, responses, and the model that answered are stored with the edition. The titles-only switch sends titles and omits task descriptions. Sending descriptions is the default.

- **CAP-8**
  - **intent:** The operator can print the full edition, upload a copy at a chosen detail level, and hold both until they approve.
  - **success:** `print.pdf` is the full edition and `cloud.pdf` comes from the same snapshot. The cloud copy is trimmed unless the level is set to full, omitting task descriptions, event locations, attendees, and prep notes. Hold mode defaults on and blocks print and upload. Approve delivers the built files. Reject stops delivery. Regenerate collects again and sets a new collection time. Auto-approve defaults off. A print failure leaves the PDF for reprint, and the run counts as printed only after the queue reports the job finished. An upload failure retries on the next cycle and raises an alert after three failures. Dropbox stores `editions/YYYY-MM-DD.pdf` and a fixed `latest.pdf`. Local PDFs, previews, and snapshots are removed after the retention period, default 30 days. Dropbox retention defaults to indefinite.

- **CAP-9**
  - **intent:** The operator can set when the edition starts, and the system can catch up after a reboot when the clock is synced and the latest acceptable time has not passed.
  - **success:** The weekday build starts at 06:30 by default. Delivery follows a successful build, or approval when hold mode is on. The latest acceptable time defaults to 10:00. A missed run is built on boot only before that time. A build does not start until NTP sync is confirmed. Print and upload can each be on or off, including a one-day skip and a one-day upload-only override.

- **CAP-10**
  - **intent:** An operator on the local network can sign in, configure sources and switches, and see the latest edition, dependency health, logs, and live job progress.
  - **success:** One admin password unlocks the dashboard at `newspaper.local` and at the Pi's IP address. Dashboard language is Hungarian or English, independent of the paper language. The home page shows edition state, source tiles, the next run, the active mode, a setup checklist while required settings are missing, and the last time `/status` was requested. The editions list covers the local retention window and offers both PDFs, the run report, the content snapshot, stored prompts, reprint, and re-upload. Each settings section in dashboard.md validates before save and can be tested. Secrets stay out of the browser and out of logs. Run now can preview, or build and deliver, and the page shows progress through collect, model, render, print, and upload.

- **CAP-11**
  - **intent:** A checker that can reach the Pi can read whether the system is ok, degraded, or down, without a login and without personal data in the response.
  - **success:** `GET` and `HEAD /status` return the JSON shape in status-api.md with `Cache-Control: no-store`. HTTP 200 means ok or degraded. HTTP 503 means down. `?strict=1` returns 503 for degraded as well. No response, a timeout, connection refused, or 502 means down. The down and degraded rules in status-api.md hold, and an edition waiting for approval is still ok. Killing the worker yields 503 within about two minutes. Unplugging the printer yields degraded. Stopping the web service makes the endpoint unreachable.

- **CAP-12**
  - **intent:** The operator can keep the dashboard on the LAN or their own VPN, with HTTPS, one admin login, and a first-run code so another device on the network cannot claim the admin account.
  - **success:** The service is not reachable from the public internet. HTTPS serves `newspaper.local` and the Pi's IP with an internal certificate, and a first-visit browser warning is accepted. PDF downloads require login. `/status` is the only route without login unless a bearer token is turned on, and that token defaults off. The first-run setup code appears on the Pi console or in the log. Login attempts are rate-limited. Outbound fetches accept only http and https URLs, and no user-supplied value is passed to a shell command. SSH accepts keys only. The firewall allows 443 and 22 from the LAN, plus the optional status port when that port is enabled. Security updates install automatically. Alerts in this version appear on the dashboard and in `/status`.

## Constraints

- The edition is one A4 page. Body type stays at its set size when content overflows, and items drop in the order in edition.md.
- The page is rendered with WeasyPrint from the local kit's HTML template, table grid, CSS, and fonts. A browser is not the renderer. The folder `The-Firstname-Times-Setup-Kit-v17.3/` stays on this machine and out of git. The app uses its masthead faces, table grid, and CSS, refit to one A4 page. Avatars, generated art, and the kit's four-page Letter edition stay in the kit.
- Duplex printing is on by default. The operator can turn it off.
- Paper language and dashboard language default to Hungarian and are separate settings. A headline prints in the language of its feed.
- The target machine is a Raspberry Pi 3B+. Output is a Brother printer driven through CUPS. A printer that only works with a Windows host-based driver cannot be the output device. The exact model is recorded when it is plugged in.
- The Pi has no battery-backed clock. Edition build waits until NTP sync is confirmed.
- News selection that uses a model returns IDs only. Code applies the interest and local quotas and prints the original headline, publisher, and time.
- The scheduler and the dashboard are separate processes, as drawn in architecture-diagrams.md. A stopped dashboard does not stop a scheduled print. A stopped scheduler is visible on the dashboard and on `/status`.
- Remote use is through the operator's VPN, which must route the LAN subnet. A port is not opened so a cloud monitor can reach `/status`.
- Hold mode defaults on and applies to print and upload together. Auto-approve at a chosen time defaults off.
- `/status` defaults to no login and returns no personal data. Secrets are stored outside the browser and shown in the UI as saved, with replace as the only edit.
- The cloud PDF defaults to trimmed and is rendered from the same content snapshot as the print PDF.
- A missing weather value or extra is omitted. No guessed number is printed in its place.
- Weekend planner notes may be warmer. They still follow the copy rules in llm.md.
- Local edition files are kept 30 days by default. Dropbox copies are kept indefinitely. Both periods are settings. Dashboard history matches the local period.
- Name day is included by default because it is one of the extras. The operator can turn it off.
- Alert delivery in this version is the dashboard and `/status`. The checks and banners are listed in operations.md.

## Non-goals

- Multiple users.
- Exposing the Pi to the public internet.
- Editing the page grid in the UI beyond section toggles and item counts.
- Reading email.
- Generating images.
- ntfy, email, and Telegram notifications. A notifier interface may exist so those channels can be added later. They are not part of this version.
- A push heartbeat from the Pi to an outside service.
- A newspaper-themed dashboard. Styling goes through CSS variables so a later theme can replace colors and fonts.
- A tablet layout. This version is one A4 PDF.
- Mini crossword, Jumble, and word search. They need a Hungarian word list with diacritics and a compatible license.
- An installable web app.
- Puzzles written by a model, unless code verifies the puzzle.

## Success signal

For seven consecutive mornings the Pi produces a real edition in hold mode, each one A4 page, while an external checker on the LAN or VPN polls `/status`. After that week the operator decides whether to turn hold mode off.
