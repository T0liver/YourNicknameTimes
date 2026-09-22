# Master Backlog

Use this as the central tracking board for the Master agent.

## Status values

- `not_started`
- `in_progress`
- `blocked`
- `in_review`
- `accepted`
- `rework`

## Priority values

- `P0` critical path
- `P1` high
- `P2` medium

## Task Board

| Task ID | Milestone | Wave | Owner | Scope summary | Depends on | Priority | Status | Evidence links | Last update |
|---|---|---|---|---|---|---|---|---|---|
| M0-A-PLATFORM-SMOKE | M0 | W1 | Agent A | Platform prereqs, CUPS baseline, service scaffolding | none | P0 | blocked | blocked evidence: no USB printer + no CUPS destination; non-Pi host cannot satisfy gate proof | 2026-09-22 |
| M0-B-DATA-SMOKE | M0 | W1 | Agent B | CalDAV listing + source adapter smoke checks | none | P0 | in_review | evidence: `caldav_smoke.py` implemented with JSON output + deterministic exits; live Baikal success proof pending | 2026-09-22 |
| M0-D-DELIVERY-SMOKE | M0 | W1 | Agent D | OpenRouter test path support + Dropbox app-folder upload smoke | none | P0 | blocked | blocked evidence: `openrouter_smoke.py`/`dropbox_smoke.py` added; missing `OPENROUTER_API_KEY` + `DROPBOX_ACCESS_TOKEN` | 2026-09-22 |
| M1-C-LAYOUT-BOOTSTRAP | M1 | W1 | Agent C | Static edition composition with fake HU data | M0-A-PLATFORM-SMOKE, M0-B-DATA-SMOKE | P1 | not_started |  |  |
| M1-D-A4-RENDER | M1 | W2 | Agent D | One-page A4 render path and print-fit verification | M1-C-LAYOUT-BOOTSTRAP | P0 | not_started |  |  |
| M2-B-FULL-SOURCES | M2 | W3 | Agent B | Deterministic full source integrations and normalization | M0-B-DATA-SMOKE | P0 | not_started |  |  |
| M2-C-DETERMINISTIC-EDITION | M2 | W3 | Agent C | Full deterministic edition + overflow loop + snapshot | M2-B-FULL-SOURCES | P0 | not_started |  |  |
| M3-E-WORKER-RUNTIME | M3 | W2 | Agent E | Scheduler/state machine/heartbeat/catch-up | M0-A-PLATFORM-SMOKE | P0 | not_started |  |  |
| M3-D-PRINT-UPLOAD-ROBUST | M3 | W3 | Agent D | Print tracking + Dropbox retry + retention hooks | M3-E-WORKER-RUNTIME | P0 | not_started |  |  |
| M4-G-LLM-INTEGRATION | M4 | W4 | Agent G | Picker/planner + schema validation + fallback | M2-C-DETERMINISTIC-EDITION, M3-E-WORKER-RUNTIME | P0 | not_started |  |  |
| M5-F-DASHBOARD-V1-STATUS | M5 | W5 | Agent F | Auth, status tiles, editions list/actions, `/status` | M3-E-WORKER-RUNTIME, M2-B-FULL-SOURCES, M3-D-PRINT-UPLOAD-ROBUST, M4-G-LLM-INTEGRATION | P0 | not_started |  |  |
| M6-F-SETTINGS-V2 | M6 | W5 | Agent F | Full settings/Test flows/OPML/printer/dropbox auth UX | M5-F-DASHBOARD-V1-STATUS | P1 | not_started |  |  |
| M7-A-HARDENING | M7 | W6 | Agent A | HTTPS/rate limit/firewall/setup hardening baseline | M5-F-DASHBOARD-V1-STATUS | P0 | not_started |  |  |
| M7-H-SECURITY-VALIDATION | M7 | W6 | Agent H | Security and resilience verification | M7-A-HARDENING | P0 | not_started |  |  |
| M8-H-BURN-IN | M8 | W6 | Agent H | 7-day hold-mode burn-in + go/no-go report | M6-F-SETTINGS-V2, M7-H-SECURITY-VALIDATION | P0 | not_started |  |  |

## Master cadence notes

- Dispatch only tasks with satisfied dependencies.
- Require 30/70/100 checkpoints for active tasks.
- Move task to `in_review` only after complete evidence package is returned.
- Record evidence links before setting `accepted`.
- If `rework`, create a new row with suffix `-R1` / `-R2` and keep original row immutable.
