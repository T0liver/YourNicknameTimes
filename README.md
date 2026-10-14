# YourNicknameTimes
I was inspired by Karen Cheng's YourFirstnameTimes project so I created my own that can be run on a Raspberry Pi plugged in to the printer and comes with a handy dashboard.

## Render one A4 page

On the Pi, install the WeasyPrint libraries:

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libgdk-pixbuf-2.0-0 poppler-utils
```

Then install the app and render the fixture:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/newspaper-render --out /tmp/edition.pdf
```

Print it with `lp /tmp/edition.pdf`. The command prints a `render_seconds=` line. Write that number down.

## Build an edition

The first run creates the database and a secrets file, then writes today's paper. The page comes from the calendar, the feeds, weather, one daily item, and the almanac. The model switch defaults to on. An empty OpenRouter key leaves the news and the prep list on the deterministic rules and marks the run degraded:

```bash
.venv/bin/newspaper-edition --data-dir data
```

`data/newspaper.db` starts at volume 1 with an empty calendar host, Telex as the local feed, and Wired as the interest feed. Until a host is saved, the schedule blocks stay empty. `data/secrets.env` is created with mode 0600. A fresh file has `CALDAV_PASSWORD=`, `DROPBOX_REFRESH_TOKEN=`, `DROPBOX_APP_KEY=`, `DROPBOX_APP_SECRET=`, and `OPENROUTER_API_KEY=`. The same blank lines are in `data/secrets.env.example`. An existing secrets file keeps its lines and gains `OPENROUTER_API_KEY=` when that line is missing. The edition is `data/editions/YYYY-MM-DD/edition.json` plus `print.pdf`. Any drops are listed in `run.log` in that folder. Volume goes up by one after the PDF is a single page.

`newspaper-render` renders the packaged fixture.

## Run the worker

The worker wakes every 30 seconds. With NTP synced, it builds the edition at 06:30 on weekdays. On Saturday and Sunday it waits until 08:00 when the weekend edition is on, and starts at 06:30 when that edition is off. A missed start still builds if the clock is before 10:00. After 10:00 it records a deadline and does not build.

Hold mode starts on. The build writes `print.pdf`, `cloud.pdf`, and `preview.png` from `edition.json`, then inserts a hold job and stops. Set that job's status to `approved` and the next wake prints and uploads. A pending reject job stops delivery and leaves the files. A pending regenerate job collects again and writes a new `AS OF`.

```bash
.venv/bin/newspaper-worker --data-dir data
```

Printing is `lp` to the saved printer name: A4, grayscale, 100% scale, and duplex when that setting is on. An empty printer name skips `lp`. Upload reads the three Dropbox lines from `data/secrets.env` and sends `cloud.pdf` to `/editions/YYYY-MM-DD.pdf` and `/latest.pdf`. Local edition folders older than 30 days are deleted. The Dropbox copies stay.

