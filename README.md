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

`data/newspaper.db` starts at volume 1 with an empty calendar host, Telex as the local feed, and Wired as the interest feed. Until a host is saved, the schedule blocks stay empty. `data/secrets.env` is created with mode 0600. A fresh file has `CALDAV_PASSWORD=`, `DROPBOX_REFRESH_TOKEN=`, `DROPBOX_APP_KEY=`, `DROPBOX_APP_SECRET=`, `OPENROUTER_API_KEY=`, `ADMIN_PASSWORD_HASH=`, `SESSION_SECRET=`, `STATUS_BEARER_TOKEN=`, and `SETUP_CODE_HASH=`. The same blank lines are in `data/secrets.env.example`. An existing secrets file keeps its lines and gains any of those that are missing. The edition is `data/editions/YYYY-MM-DD/edition.json` plus `print.pdf`. Any drops are listed in `run.log` in that folder. Volume goes up by one after the PDF is a single page.

`newspaper-render` renders the packaged fixture.

## Run the worker

The worker wakes every 30 seconds. With NTP synced, it builds the edition at 06:30 on weekdays. On Saturday and Sunday it waits until 08:00 when the weekend edition is on, and starts at 06:30 when that edition is off. A missed start still builds if the clock is before 10:00. After 10:00 it records a deadline and does not build.

Hold mode starts on. The build writes `print.pdf`, `cloud.pdf`, and `preview.png` from `edition.json`, then inserts a hold job and stops. Set that job's status to `approved` and the next wake prints and uploads. A pending reject job stops delivery and leaves the files. A pending regenerate job collects again and writes a new `AS OF`.

```bash
.venv/bin/newspaper-worker --data-dir data
```

Printing is `lp` to the saved printer name: A4, grayscale, 100% scale, and duplex when that setting is on. An empty printer name skips `lp`. Upload reads the three Dropbox lines from `data/secrets.env` and sends `cloud.pdf` to `/editions/YYYY-MM-DD.pdf` and `/latest.pdf`. Local edition folders older than 30 days are deleted. The Dropbox copies stay.

A pending `run_now` or `preview` job runs only when NTP is synced and the job date is today. Run now then holds or delivers from the settings. Preview refreshes `cloud.pdf` and `preview.png` and adds a finished run only when that date does not already have one. Reprint writes the CUPS id to `reprint.cups` and leaves the run status unchanged. An empty printer name does not call `lp`. Re-upload sends the existing `cloud.pdf`.

## Serve the dashboard

`newspaper-web` listens on `127.0.0.1:8080`. Caddy serves `https://newspaper.local` and `https://<pi-ip>` with an internal certificate and proxies to that address. The browser warns once, until you install the local root. Stopping the app makes Caddy return 502.

The first start with no admin hash prints `setup code:` once and stores the hash in `data/secrets.env`. The form asks for that code and a new password. A wrong code leaves the password hash empty. Later starts ask for the password. An empty `SESSION_SECRET=` is filled and is not printed.

```bash
.venv/bin/newspaper-web --data-dir data
```

Sign in with that password. Approve and Reject sit on the banner while a hold is pending. Run now and Preview are on the home page. Reprint and re-upload are on the edition page. Those actions insert a job. The worker prints and uploads.

`GET /status` and `HEAD /status` stay open while the bearer switch is off. With the switch on, the request needs `Authorization: Bearer` matching `STATUS_BEARER_TOKEN`. A missing token, a wrong token, or an empty secret is 401 with an empty body. Login allows 5 failures from one address in 15 minutes, and `/status` allows 60 requests from one address in one minute. The next call is 429. Those counts clear when the web process restarts. A system save writes `data/status-http.port`. A number in that file is plain HTTP and answers only `/status`. An empty file closes the port.

On the Pi, with the hostname `newspaper` and the venv already installed, the install uses this checkout's `data/` directory. Set `NEWSPAPER_DATA_DIR` first if the database lives somewhere else.

```bash
sudo ./deploy/install.sh
```

Avahi publishes `newspaper.local`. The install enables Avahi and unattended security upgrades. SSH stays keys-only. The firewall allows TCP 443 and TCP 22 from the LAN, UDP 5353 to the mDNS group, and the status port only while `data/status-http.port` has a number.

## Burn-in week

After install, run seven real mornings in hold mode with your checker polling `/status`. Copy [docs/burn-in-log.example.md](docs/burn-in-log.example.md) beside `data/`, follow [docs/burn-in-week.md](docs/burn-in-week.md), and turn hold mode off when the week looks good.

