# YourNicknameTimes
I was inspired by Karen Cheng's YourFirstnameTimes project so I created my own that can be run on a Raspberry Pi plugged in to the printer and comes with a handy dashboard.

## Render one A4 page

On the Pi, install the WeasyPrint libraries:

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libgdk-pixbuf-2.0-0
```

Then install the app and render the fixture:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/newspaper-render --out /tmp/edition.pdf
```

Print it with `lp /tmp/edition.pdf`. The command prints a `render_seconds=` line. Write that number down.

## Build a model-off edition

The first run creates the database and a secrets file, then writes today's paper with the model off. The page comes from the calendar, the feeds, weather, one daily item, and the almanac:

```bash
.venv/bin/newspaper-edition --data-dir data
```

`data/newspaper.db` starts at volume 1 with an empty calendar host, Telex as the local feed, and Wired as the interest feed. Until a host is saved, the schedule blocks stay empty. `data/secrets.env` is created with mode 0600 and the line `CALDAV_PASSWORD=`. A blank copy of that line is in `data/secrets.env.example`. The edition is `data/editions/YYYY-MM-DD/edition.json` plus `print.pdf`. Any drops are listed in `run.log` in that folder. Volume goes up by one after the PDF is a single page.

`newspaper-render` renders the packaged fixture.

