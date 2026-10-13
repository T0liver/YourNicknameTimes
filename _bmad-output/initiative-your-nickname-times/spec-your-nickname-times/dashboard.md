# Dashboard

The dashboard is mobile-first, responsive, and utilitarian. Pages are server-rendered. All styling goes through CSS variables, so a later newspaper theme can replace colors and fonts. That theme is not part of this version.

Dashboard language is Hungarian or English, chosen separately from the paper language.

One admin password. The site answers at `newspaper.local` and at the Pi's IP address.

## Status (home)

- A banner for the latest edition: done, degraded, failed, or awaiting approval. Approve and Reject are on the banner when an edition is held.
- Tiles for Baïkal, RSS feeds (grouped), weather, almanac and rates, OpenRouter (with requests used today), Dropbox, the printer, the worker, and Pi health (disk, temperature, uptime, Wi-Fi, clock sync). Each tile is green, yellow, red, or unknown, and shows the last success time and a plain-language last error.
- The next scheduled run, and the active mode: weekday or weekend, hold on or off, model on or off.
- A setup checklist while required settings are missing: nickname, city, Baïkal, feeds, printer, Dropbox.
- A monitoring box with the `/status` URL to copy, and the time of the last request, so the operator can see whether a checker is polling.

## Editions

The local retention window, default the last 30 days. Each row has a thumbnail, status flags, and download buttons for both PDFs.

Opening an edition shows the run report, the content snapshot, the prompts and responses, and buttons to reprint and to re-upload.

## Settings

Settings are grouped as below. Each group has a Test button, and values are validated before they are saved.

- **General:** nickname (the title becomes `{Nickname} Times`), optional motto (empty by default), city and coordinates, timezone, paper language, dashboard language, paper size (A4).
- **Schedule:** weekday time, weekend edition switch and time, latest acceptable time, hold mode, auto-approve.
- **Weekend touches:** news mood (`light` or `neutral`), sun icon on or off, greeting text.
- **Delivery:** print, upload, both, or none; cloud trim level; local retention; Dropbox retention.
- **Calendar and tasks:** Baïkal URL, username, and password, all empty on a fresh install; discovery; pickers for calendars and task lists.
- **News:** a feed table with add, edit, test, enable, tag, weight, and language; OPML import and export; quotas.
- **Weather, daily item, and almanac:** location, units, the rotation table, xkcd on or off, and a toggle for each almanac and rate item.
- **Model:** on/off switch, API key, router or a pinned model, the "send descriptions" switch, per-call limits.
- **Dropbox:** guided authorization and folder settings.
- **Printer:** a printer picker from CUPS, duplex, and a test page.
- **System:** admin password, `/status` options (enabled, token, plain-HTTP port), backup and restore of settings with secrets excluded, and a diagnostics bundle download.

Logs are a separate view: recent run logs with a filter, and a diagnostics bundle with secrets redacted.

Actions from the dashboard: Run now (preview only, or build and deliver), reprint a past edition, and live progress through collect, model, render, print, and upload.

## How settings are stored

Settings live in SQLite. The last few versions are kept so a change can be rolled back.

Secrets live in a separate file with mode `chmod 600`. They are never sent to the browser. The UI shows "saved" and offers replace only. Logs and the diagnostics bundle are redacted.
