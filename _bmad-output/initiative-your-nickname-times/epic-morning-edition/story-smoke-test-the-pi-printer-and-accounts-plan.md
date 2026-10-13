---
title: '1.1 Smoke-test the Pi, printer, and accounts'
type: 'chore'
ticket: '1'
created: '2026-10-13'
status: 'built'
baseline_revision: '97f277960da2b6124892087c815f9988d7dbe8b1'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['self']
review_loop_iteration: 0
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/milestones.md
  - newspaper-spec-v1.1.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Milestone 0 is not checked in until the Pi, CUPS printer, Baïkal CalDAV, OpenRouter, and Dropbox app folder are proven on the device. There is no app yet, so the operator needs runnable smoke scripts on the Pi.

**Approach:** Add `scripts/smoke/` with small checks the operator runs on the Pi after imaging. Credentials load from a local `smoke.local.env` (gitignored), not from `data/secrets.env`. After a successful run, copy working values into `keys-for-1.3.local.md` for story 1.3. Do not create `newspaper.db` or `data/secrets.env`.

</frozen-after-approval>

## Implementation Notes

Oneshot: scripts only; operator runs on the Pi.

- Added `scripts/smoke/` with `run_smoke.sh`, per-check scripts, `smoke.env.example`, and `keys-for-1.3.local.md.example` (gitignored local copy for story 1.3 handoff).
- No `data/newspaper.db` or `data/secrets.env` created.
