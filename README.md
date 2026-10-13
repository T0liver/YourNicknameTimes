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

