---
title: 'Harden LAN access'
type: 'feature'
ticket: '8'
created: '2026-10-15'
status: 'built'
baseline_revision: 'f97a22e81faa495b404f89fbc337a9adcf94c03d'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The app listens on `127.0.0.1:8080`. Story 7 stores `status_token_enabled`, `status_http_port`, and `STATUS_BEARER_TOKEN`, and the app ignores them. The LAN has no HTTPS name, and a stopped app does not show up as 502.

**Approach:** Caddy serves `newspaper.local` and the Pi address with an internal certificate and proxies to the localhost app. Avahi publishes the name. A first start with no admin hash prints a setup code; the form asks for that code and a new password. Login and `/status` are rate-limited. `/status` requires the stored bearer token when the switch is on. A set `status_http_port` serves only `/status` over plain HTTP. The firewall allows 443 and 22 from the LAN, plus that port only while it is set, and UDP 5353 from the LAN to the mDNS group so the name resolves. Security updates install on their own. SSH stays keys-only, as already set.

## Boundaries & Constraints

**Always:** The app stays on `127.0.0.1:8080`. Caddy is the LAN listener. The token and setup code stay in `secrets.env`, out of SQLite, HTML, logs, and backups. An enabled token with an empty secret returns 401. PDF downloads still require a session. The setup code prints once on stdout. Inbound rules take LAN sources and reject public addresses. A system save records the status port for Caddy and the firewall. UDP 5353 from the LAN to the mDNS group stays open with 443 and 22.

**Never:** Do not change sshd, bind the app on `0.0.0.0`, request a public certificate, or pass a settings value through a shell. Do not rename story 7's settings or change the `/status` JSON.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LAN dashboard | Caddy up, app up | `https://newspaper.local` and `https://<pi-ip>` reach the app; first visit warns on the internal CA | No error expected |
| App stopped | Caddy up, port 8080 closed | HTTPS returns 502 | Checker treats 502 as down |
| Token off | switch false | `GET` and `HEAD /status` stay open | No error expected |
| Token on | bearer matches the secret | `/status` returns the usual JSON | Missing or wrong bearer is 401 with an empty body |
| Status port | port set or empty | Set: that TCP port serves only `/status`. Empty: the port is closed | Other paths on that port are refused |
| First claim | no password hash | stdout prints `setup code:`; the form asks for the code and a password | Wrong code leaves the hash empty |
| Later sign-in | hash stored | Password form only | Wrong password stays on the form |
| Flood | many calls from one address | Later login or `/status` calls from that address get 429 | 429 |
| Firewall | port empty, then set | Inbound 443 and 22 from the LAN, plus UDP 5353 to the mDNS group; the status port opens only after it is set | Public sources stay denied |

</frozen-after-approval>

## Code Map

- `newspaper/web.py` — bind `127.0.0.1:8080`; `ensure_admin` prints `admin password:` when the hash is empty; `login_submit`; open `status`. Reuse `hash_password`, `verify_password`, `_write_secret`.
- `newspaper/db.py` — status keys and `STATUS_BEARER_TOKEN` already exist. Add the setup-code secret beside them.
- `newspaper/dashboard_settings.py` — `system` branch saves the switch, port, and bearer. After that save, write the port file. Leave `settings_system.html` alone.
- `newspaper/templates/dashboard/login.html` — password field only. Show the setup code when no hash exists.
- `tests/test_web.py` — `_prepare` writes a hash, so current login tests stay. Keep `test_serve_binds_localhost`.
- `tests/test_status.py` — `/status` is open. Add bearer and 429 cases.
- `tests/test_settings_web.py` — keep the test that the secret is stored and absent from HTML.
- `README.md` — serve section still says `admin password:` and that `/status` stays open. No `deploy/` files exist yet.

## Tasks & Acceptance

**Execution:**
- [ ] `newspaper/web.py` -- Setup-code claim, rate limits, bearer check. `Secure` cookie when `X-Forwarded-Proto` is `https`.
- [ ] `newspaper/db.py` -- Store the setup-code secret. Leave the status keys unchanged.
- [ ] `newspaper/dashboard_settings.py` -- On a system save, write `data/status-http.port`.
- [ ] `newspaper/lan.py` -- Render Caddy and nftables: internal cert, proxy to `127.0.0.1:8080`, status-only site when the port is set, and UDP 5353 to the mDNS group.
- [ ] `deploy/` -- `newspaper-web` unit, Caddy, Avahi, unattended security upgrades, and a root sync that reloads Caddy and nftables when the port file changes.
- [ ] `newspaper/templates/dashboard/login.html` -- Setup-code field only before a password exists.
- [ ] `tests/test_web.py`, `tests/test_status.py`, `tests/test_lan.py` -- Cover the matrix rows that do not need a live Pi.
- [ ] `README.md` -- Setup code, LAN URL, token, and the install command.

**Acceptance Criteria:**
- Given a password hash exists, when `/login` is opened, then the form asks for the password and no new setup code is printed.
- Given the rendered Caddy site, when nothing listens on 8080, then the proxy target is `127.0.0.1:8080` and a dead upstream is 502.
- Given a null status port, when nftables is rendered, then inbound traffic from the LAN is TCP 443, TCP 22, and UDP 5353 to the mDNS group.
- Given the Pi install finishes, when services are checked, then Avahi and unattended security upgrades are enabled and sshd was not edited.

## Implementation Notes

- The install uses the checkout's `data/` directory unless `NEWSPAPER_DATA_DIR` is set, so the status port file is the one the dashboard writes.
- nftables starts with `flush ruleset`. DHCP replies, DHCPv6 replies, neighbor discovery, and ICMP unreachable stay accepted so the Pi keeps its address and outbound fetches. The sync loads nftables before it reloads Caddy.

## Plan Change Log

## Review Triage Log

- quick, boot ordering: high, patch. `newspaper-lan-sync.service` is `Before=caddy.service` and its command runs `systemctl reload-or-restart caddy`, so Caddy waits for the sync unit while the sync unit waits for Caddy.
- quick, setup code in the journal: false, reject. The frozen intent prints `setup code:` on stdout, and the spec shows that line on the console or in the log. The journal is that log. The same sentence keeps the code out of SQLite, HTML, and backups.
- quick, rollback and restore leave the port file: high, patch. `settings_rollback` and `restore_settings` call `save_settings` and never `write_status_port`, so the firewall and Caddy keep the previous port.
- quick, overlapping rate-limit checks: medium, patch. `login_submit` checks the cap, awaits the form, then records. `_over_limit` updates `app.state.hits` with no lock. Overlapping calls can all pass the same count.
- quick, settings read failure skips the token: maybe-false, defer, medium if true. A thrown `load_settings` returns not-denied. The following `build_report` turns a still-failing database into the down shell, not the usual ok JSON. The usual JSON appears only if that second read succeeds. A test of that split would settle it.
- quick, certificate keeps the old DHCP address: low, reject. The spec tells the operator to reserve a fixed address. A watcher for address changes is more than a direct correction, and everyday use does not move the address.
- quick, status port 80 or 443: high, patch. The system save accepts 1–65535, and `render_caddy` adds `http://:<port>` next to the site that already uses 443 and the HTTP redirect on 80. A reload then fails and the dashboard stops. Port 22 would take the SSH socket the same way.
- quick, Caddy package starts before nftables: medium, patch. `deploy/install.sh` installs Caddy, which starts the default site, before `nft -f` loads the drop policy.

## Design Notes

The app writes `data/status-http.port` as an integer or an empty file. A root path unit runs the sync, which checks the port, writes the Caddy and nftables files, and reloads those services with fixed commands.

Caddy uses `tls internal`. The browser warns once, until that local root is installed.

LAN means sources that are not publicly routable: IPv4 RFC1918 and link-local, IPv6 ULA and link-local. Established and outbound traffic stay open. UDP 5353 to the mDNS group is open from those sources. Port 631 stays closed.

Rate limits sit in the web process and clear on restart. Login: 5 failures from one address in 15 minutes. `/status`: 60 requests from one address in one minute. Then 429.

The setup code is printed once and checked as a hash. An existing password hash skips claim.

## Verification

**Commands:**
- `uv run pytest tests/test_web.py tests/test_status.py tests/test_settings_web.py tests/test_lan.py` -- expected: pass

**Manual checks (if no CLI):**
- On the Pi: `https://newspaper.local` warns once and shows the dashboard; stopping `newspaper-web` returns 502; the status port appears in `nft list ruleset` only after one is saved, and that port answers only `/status`.
