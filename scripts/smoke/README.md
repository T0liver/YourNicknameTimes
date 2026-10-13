# Milestone 0 smoke tests (story 1.1)

Scripts for the Raspberry Pi after imaging. They check the baseline host, CUPS printing, Baïkal CalDAV, OpenRouter, and a Dropbox app-folder upload. They do not create `data/newspaper.db` or `data/secrets.env`.

## On the Pi

1. Clone or copy this repo to the Pi.
2. Install system packages if needed: `cups`, `python3-venv`, `python3-pip`.
3. Copy `smoke.env.example` to `smoke.local.env`, fill in credentials, `chmod 600 smoke.local.env`.
4. Make scripts executable: `chmod +x *.sh check_*.py`.
5. Run `./run_smoke.sh`.

`run_smoke.sh` creates a local `.venv` under this folder and installs `requirements.txt`.

## Individual checks

| Script | What it checks |
| --- | --- |
| `check_pi_baseline.sh` | Hostname `newspaper`, LAN addresses, NTP sync, SSH |
| `check_printer.sh` | CUPS running, `lp` test page (set `PRINTER_NAME` if needed) |
| `check_baikal.py` | Lists calendars and task lists; light sample fetch |
| `check_openrouter.py` | One short chat completion |
| `check_dropbox.py` | Uploads `smoke-<timestamp>.txt` to the app folder |

## Handoff to story 1.3

When everything passes, copy `keys-for-1.3.local.md.example` to `keys-for-1.3.local.md` (gitignored) and paste the working URLs, tokens, and printer model. Story 1.3 will move secrets into `data/secrets.env` and create `newspaper.db`.

Record the Brother model from the printer label, `lsusb`, or `lpinfo -m` in that note.

## Environment variables

See `smoke.env.example`. Override the env file with `SMOKE_ENV_FILE=/path/to/file` or the venv with `SMOKE_VENV=/path/to/venv`.
