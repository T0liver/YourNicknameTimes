---
type: epic
title: The Pi prints the morning edition
parent: initiative-your-nickname-times
covers: [CAP-1, CAP-2, CAP-3, CAP-4, CAP-5, CAP-6, CAP-7, CAP-8, CAP-9, CAP-10, CAP-11, CAP-12]
after: []
assignee: ""
risk: high
---

# The Pi prints the morning edition

## Description

This epic delivers CAP-1 through CAP-12 on one Raspberry Pi. The spec and its companions are the contract: a morning paper, a LAN dashboard, and an external checker.

## Outcome

The operator's Pi prints the morning edition. The signal is the spec's Success signal.

## Requirements

The kernel's CAP-1 through CAP-12. This epic owns each of them.

- CAP-1: story 2 the page geometry and empty-block collapse; story 3 the overflow loop and a failed render; story 4 the worker prints nothing when the page still will not build; story 9 the week of real pages.
- CAP-2: story 2 the masthead on the page; story 3 the dateline and the lighter weekend page; story 7 nickname, motto, and weekend settings.
- CAP-3: story 3 the CalDAV rules; story 7 the server settings and collection pickers.
- CAP-4: story 3 the feed rules and the Telex and Wired seed rows; story 7 the feed editor and OPML.
- CAP-5: story 3 the extras and their failure behavior; story 7 the toggles.
- CAP-6: story 3 the rotation, comic, and puzzle; story 7 the rotation editor.
- CAP-7: story 3 the model-off paper; story 5 the model calls, retry, and stored prompts; story 7 the model settings.
- CAP-8: story 4 print, upload, hold, and retention; story 6 approve, reject, regenerate, reprint, and re-upload; story 7 delivery settings and Dropbox authorization.
- CAP-9: story 4 the schedule, catch-up, and print and upload switches; story 7 the schedule settings.
- CAP-10: story 6 login, the home page, the editions list, actions, and logs; story 7 settings, the checklist items, and the phone layout; story 8 HTTPS in front of the app.
- CAP-11: story 6 the `/status` rules; story 8 the optional token and a 502 when the app behind Caddy is down.
- CAP-12: story 3 http and https fetches with no shell; story 6 login on PDF downloads and an open `/status`; story 8 Caddy, the setup code, rate limits, the firewall, SSH keys, and automatic updates.

Story 1 proves the Pi, the printer, Baïkal, OpenRouter, and Dropbox, and cites no capability. Story 10 only cleans up recorded debt.

## Done when

1. Seven consecutive real mornings in hold mode each produce one A4 page.
2. A checker on the LAN or VPN can tell ok, degraded, and down from `/status` without a login and without personal data.
3. The operator can configure sources and switches from the LAN dashboard and can hold print and upload until they approve.
4. With the model off, the deterministic edition still fills one page. With it on, a bad model response falls back and the run can finish.
5. The Pi is not reachable from the public internet.

## Boundaries

This epic is the whole product on one Pi: the worker, the dashboard, and `/status`. The kernel's non-goals stay out. Touch points are named on the initiative. The name-day table is vendored here.

## References

- parent — _bmad-output/initiative-your-nickname-times/initiative-your-nickname-times.md
- spec — _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/spec-your-nickname-times.md, Capabilities
- constraint — the same spec, Constraints and Non-goals
- companion — edition.md, data-sources.md, llm.md, delivery.md, dashboard.md, status-api.md, architecture-diagrams.md, stack.md, operations.md, and milestones.md, in that spec folder

## Notes

- Decision: story ids 1 through 9 are milestones 0 through 8, in that build order, and each story's covers cites the CAP ids it implements (user, 2026-10-13).
- Decision: story 10, Refactor sweep, stays and runs last (user confirmed the set, 2026-10-13).
- Decision: story 1 is the device check placed first. Story 2 is the first path through the renderer. Story 6 is the first build that connects collection, the worker, the dashboard, and `/status`. Story 9 is the success signal (user, 2026-10-13).
- The stories at high risk are 3, 4, 7, and 8. Story 9, the week of real editions with the external checker, is the check outside their own verify lines.
