# Milestones

Build order and the check that ends each step. The product contract is the kernel and the other companions. This file is the sequence those checks are planned in.

| # | Milestone | Done when |
| --- | --- | --- |
| 0 | Smoke tests | The Pi boots headless. CUPS prints a test page with `lp` on the USB printer. A script lists Baïkal calendars and tasks. The OpenRouter key answers a test call. A Dropbox app-folder upload works. |
| 1 | Static A4 layout | Fake Hungarian data renders as exactly one A4 page. `ő` and `ű` are correct in every font. The title `{Nickname} Times`, the collapsed empty motto, and the weekend sun icon all render. The page prints with sensible margins. Render time on the Pi is measured. |
| 2 | Deterministic edition | Real CalDAV, the Telex and Wired feeds, weather, sudoku, xkcd, sunrise and sunset, moon phase, the vendored name-day table, on this day in the paper language, and the three MNB rates fill the page with no model call. The content snapshot is saved. The overflow loop works. This edition is the fallback paper. |
| 3 | Worker and delivery | A daemon with the SQLite state machine and heartbeat, a config file, weekday and weekend schedules, catch-up after boot, the hold flag, print with job tracking, Dropbox upload, and retention. It runs reliably for days with no UI. |
| 4 | Model layer | News picker and planner with validation, retry, fallback, the on/off switch, weekend mood, and stored prompts. |
| 5 | Dashboard v1 and `/status` | Login, status tiles, the editions list and downloads, approve, reject, regenerate, run now, logs, and `/status`. Killing the worker turns `/status` to down (503) within about 2 minutes. Unplugging the printer turns it degraded. Stopping the web service makes the endpoint unreachable. |
| 6 | Dashboard v2 | Full settings editing with Test buttons, Dropbox authorization, OPML, the printer picker, Hungarian and English UI, the setup checklist, and a layout that works on a phone. |
| 7 | Hardening | Caddy HTTPS, the setup code, rate limiting, the firewall, automatic updates, and the optional status token and status-only HTTP port. |
| 8 | Burn-in | One week of real editions in hold mode, with an external checker polling `/status`. Density and copy are tuned during the week. After the week, decide whether to turn hold mode off. |

Work deferred past this version is listed under Non-goals in the kernel: ntfy, email, and Telegram; a push heartbeat; a newspaper-themed dashboard; a tablet layout; mini crossword and other Hungarian word puzzles; an installable web app.

The exact Brother model number is still recorded at milestone 0, when the printer is plugged in. It does not block the rest of the work.
