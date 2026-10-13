---
type: initiative
title: Your Nickname Times
parent: none
covers: [CAP-1, CAP-2, CAP-3, CAP-4, CAP-5, CAP-6, CAP-7, CAP-8, CAP-9, CAP-10, CAP-11, CAP-12]
after: []
assignee: ""
risk: high
---

# Your Nickname Times

## Description

The Pi collects one person's calendar, tasks, news, weather, almanac, currency rates, and one comic or puzzle, lays them on a single A4 page, prints it, and can upload a copy. A dashboard on the local network configures the system, and an external checker reads `/status`. The contract is `spec-your-nickname-times.md` and its companions.

## Outcome

The spec's success signal is the measure: seven consecutive hold-mode mornings, each one A4 page, with a checker on the LAN or VPN polling `/status`, after which the operator decides whether to turn hold mode off.

## Done when

1. Seven consecutive real mornings in hold mode each produce one A4 page.
2. A checker on the LAN or VPN can tell ok, degraded, and down from `/status` without a login and without personal data.
3. The operator can configure sources and switches from the LAN dashboard and can hold print and upload until they approve.
4. The Pi is not reachable from the public internet.

## Boundaries

The whole product on one Pi, with one owner. The kernel's non-goals stay out. The path through this initiative is milestones 0 through 8 inside `epic-morning-edition`. The Hungarian name-day table is vendored into that epic from froccsos/nevnapok-json. The operator imports `latest.pdf` into a reMarkable by hand, and that device is out of scope.

- Touch point: Baïkal — CalDAV calendars and tasks, configured, not built; owner: epic-morning-edition
- Touch point: RSS publishers — Telex and Wired on a fresh install, and any feed the operator adds; owner: epic-morning-edition
- Touch point: Open-Meteo — weather, consumed, not built; owner: epic-morning-edition
- Touch point: Wikipedia — the on-this-day feed, consumed, not built; owner: epic-morning-edition
- Touch point: MNB — daily EUR, USD, and CHF rates in HUF, consumed, not built; owner: epic-morning-edition
- Touch point: xkcd — the comic JSON API, consumed, not built; owner: epic-morning-edition
- Touch point: OpenRouter — the news picker and planner, consumed, not built; owner: epic-morning-edition
- Touch point: Dropbox — app-folder upload, configured, not built; owner: epic-morning-edition
- Touch point: CUPS and the Brother USB printer — configured, not built; owner: epic-morning-edition
- Touch point: Raspberry Pi OS Lite — imaged and configured, not built; owner: epic-morning-edition
- Touch point: Caddy, Avahi, and systemd — configured on the Pi; owner: epic-morning-edition
- Touch point: the gitignored layout kit (`The-Firstname-Times-Setup-Kit-v17.3/`) — the app uses its HTML template, table grid, CSS, and masthead fonts; avatars, generated art, and the four-page Letter edition stay in the kit; owner: epic-morning-edition
- Touch point: the operator's VPN and the router's reserved address — the operator runs these; owner: epic-morning-edition
- Touch point: the external status checker — any HTTP JSON monitor on the LAN or VPN; owner: epic-morning-edition

## References

- spec — _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/spec-your-nickname-times.md, Capabilities
- constraint — the same file, Constraints and Non-goals

## Notes

- Decision: one epic, one owner, and the story sequence is milestones 0 through 8 (user, 2026-10-13).
- Decision: no separate platform-baseline epic. This spec has no CI pipeline. Milestone 0 and the app scaffold inside milestone 1 are the baseline, as the first stories of the only epic (user, 2026-10-13).
