# Stack

How the system runs. Product rules that this stack has to satisfy are in the kernel and the other companions.

## Processes

Two systemd services, each with `Restart=always`.

- **Worker.** Wakes every 30 seconds, reads the schedule from SQLite, and runs an edition when it is due. On boot it checks for a missed run and catches up if the time is still before the latest acceptable time. Each cycle it writes a heartbeat: a timestamp and a health snapshot. It refuses to build until NTP sync is confirmed.
- **Web service.** Serves the dashboard and `/status`. It reads the heartbeat to decide whether the worker is alive. It does not print.

Jobs for "Run now", "Reprint", and "Approve" are rows in SQLite. The web service inserts a row. The worker picks it up and writes progress events that the dashboard shows live.

The app process binds to localhost. Only Caddy listens on the LAN.

## Libraries

Python 3.11 or newer. FastAPI, Jinja2, and HTMX, with no Node build step. SQLite. WeasyPrint for the PDF. `caldav`, `feedparser`, `requests`, and Pillow. An astronomy library for sun and moon times. The Dropbox SDK, or plain HTTP against the Dropbox API.

Caddy terminates HTTPS. CUPS prints. Avahi advertises `newspaper.local`.

## Data layout

```plain
data/
  newspaper.db        # settings, feeds, editions, runs, events, health, alerts, jobs
  secrets.env         # chmod 600
  cache/              # xkcd images, feed ETags, almanac and rate caches
  editions/2026-09-21/
    print.pdf  cloud.pdf  preview.png
    edition.json      # content snapshot
    llm/              # prompts and responses
    run.log
```

Main tables: `settings`, `feeds`, `editions`, `runs`, `run_events`, `health_checks`, `alerts`, `jobs`, `puzzle_history`, `rate_history`, `heartbeat`, `admin`.

`edition.json` is the content snapshot. It holds the masthead, news items, today, the week, weather, prep, due-this-week, overdue, the daily item, almanac and rates, and metadata: mode, the model used, and trims. Both PDFs are rendered from this file.

Settings rows keep their last few versions for rollback. Secrets stay in `secrets.env` and are not in the database.
