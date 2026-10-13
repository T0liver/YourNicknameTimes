# Operations

Security, health checks, alerts, and the machine the software runs on.

## Health checks

- **Printer.** CUPS status, polled every minute. State, and reasons such as paper out or low toner when the printer reports them. A USB printer may reveal a jam only when a job fails.
- **Other sources.** Checked during a run, from the Test buttons, and by an hourly light check. A feed that has just failed is retried about once a minute until it recovers or the dead-feed alert fires.
- **Pi.** Disk space, CPU temperature, uptime, Wi-Fi signal, NTP sync. Disk low is under 500 MB free. Disk critical is under 100 MB free.
- **Worker.** Age of the heartbeat.

## Alerts

Shown on the Status page with a severity. The operator can dismiss or acknowledge one. Until a later version, this page and `/status` are the only channels. ntfy, email, and Telegram sit behind a notifier interface so they can be added later. They are not part of this version.

| Alert | Trigger |
| --- | --- |
| Worker not responding | Heartbeat is stale |
| No edition by deadline | No edition built by the latest acceptable time |
| Run failed | Any failed run |
| Degraded edition | A fallback was used |
| Printer problem | CUPS error, or a job failed |
| Dropbox problem | 3 failed uploads, or the authorization expired |
| Feed dead | A feed has been failing for 6 minutes |
| Waiting for approval | An edition has been held for more than 1 hour (information, not a failure) |
| Model limit | Today's model requests have reached 20, or 80% of the daily limit, whichever comes first |
| Disk low | Free space is under 500 MB |

The status endpoint's own `down` rules, including a stale heartbeat of 2 minutes, a clock still unsynced after 1 hour, and disk space under 100 MB, are in status-api.md.

## Security

- LAN only. No port forwarding. Remote access is the operator's VPN, and that VPN must route the LAN subnet.
- HTTPS through Caddy, with an internal certificate for `newspaper.local` and the Pi's IP. A one-time browser warning is expected. Installing Caddy's root certificate on a device removes it.
- The app binds to localhost. Only Caddy listens on the LAN.
- One admin password, stored hashed. Session cookies, CSRF protection, and login rate limiting.
- A first-run setup code is shown on the Pi's console or in the log, so the first person on the Wi-Fi cannot claim the dashboard.
- PDF downloads require login.
- `/status` is the only route without login. It returns no personal data. An optional token and a rate limit apply to it. The token defaults off.
- Outbound fetches accept only `http` and `https` URLs. No user input is passed to a shell command.
- SSH is by key only. The firewall allows only 443 and 22 from the LAN, plus the optional status port when it is enabled. Automatic security updates are on.

## The Pi

Raspberry Pi OS Lite, 64-bit, headless, written with Imager: Wi-Fi, SSH, hostname `newspaper`, timezone Europe/Budapest.

The 3B+ has 1 GB of RAM and a modest CPU. That is enough for one page render, the web service, and Caddy. Rendering is slower than on a laptop. Milestone 1 measures the render time.

Packages: CUPS, the Pango, HarfBuzz, and GDK-Pixbuf libraries, a Python venv, Caddy, and Avahi for `.local` names.

Use a decent SD card. Keep logs small and rotated, to limit write wear.

## USB printer

The printer is a Brother, on USB, driven by CUPS. The exact model number is written down when it is plugged in, because the driver depends on it.

- Many Brother printers work in CUPS with no extra driver, over IPP. Many Brother lasers also work with the `printer-driver-brlaser` package.
- Some host-based (GDI-style) models work only with a vendor Windows driver and are unreliable on Linux.

Milestone 0 confirms this unit: CUPS detects it, and `lp` prints a test page. Checking the model on the OpenPrinting driver database is worth doing once the model number is known.

A laser printer is more dependable for a once-a-day job because its output does not dry out. An inkjet's nozzles can clog when it sits unused. The printer also needs to accept A4 and grayscale, and it should not enter a deep sleep that ignores USB wake-ups. That sleep behavior varies by model.
