---
title: '1.9 Burn in for seven mornings'
type: 'chore'
ticket: '9'
created: '2026-10-15'
status: 'built'
baseline_revision: '0db2736c33d3838dacdc336047e80278db5f5c5d'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/operations.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/status-api.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/milestones.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/edition.md
  - _bmad-output/initiative-your-nickname-times/spec-your-nickname-times/dashboard.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Milestone 8 is the product success signal: seven real hold-mode mornings, each one A4 page, while an external checker polls `/status`. The software is ready, but nothing in the repo tells the operator how to run that week, what to tune, or how to record the result.

**Approach:** Add a short operator runbook and a seven-day log template. Point the README at them. Extend the spec's `operations.md` with the same burn-in rules. No new dashboard fields, endpoints, or capabilities. The operator runs the mornings and the checker. During the week they change only existing density levers (feeds, calendars, extras, weekend mood, regenerate) or copy levers (nickname, motto, greeting, paper language) that they name explicitly; this story does not add knobs or change settings for them.

</frozen-after-approval>

## Implementation Notes

Oneshot: prose and one example file only. The operator owns the seven calendar days and the checker history.

Added `docs/burn-in-week.md`, `docs/burn-in-log.example.md`, **Burn-in week** in spec `operations.md`, and a README pointer. Quick review caught mismatches with the real UI (`awaiting_approval`, `print.pdf` vs Preview, no worker unit in `deploy/`, loopback status URL on home); docs were corrected.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/operations.md` -- Add a **Burn-in week** section: hold on, daily approve flow, what counts as density vs copy, checker expectations, and turning hold off after day seven.
- [x] `docs/burn-in-week.md` -- Mirror the procedure for the operator at the keyboard, with links to `status-api.md` and dashboard settings groups.
- [x] `docs/burn-in-log.example.md` -- Seven rows (date, printed, `/status`, drops, notes) for the operator to copy beside `data/`.
- [x] `README.md` -- One paragraph after install that points to `docs/burn-in-week.md`.

## Review Triage Log

- quick: deploy/install worker claim — high, patch. Install enables `newspaper-web` only; runbook now says to start `newspaper-worker` separately.
- quick: banner text — medium, patch. Use `awaiting_approval` and Approve/Reject wording.
- quick: Preview for held print — high, patch. Direct operator to `print.pdf`; Preview is for cloud copy.
- quick: Editions nav — low, patch. Home page list, not a separate Editions page.
- quick: grammar — low, patch. “an overflow”.
- quick: greeting length / compressed task band — medium, patch. Removed non-settings levers; aligned density lists with dashboard.
- quick: loopback status URL — medium, patch. Document LAN checker URL vs home display.
- quick: auto-approve — medium, patch. Say to leave it off during burn-in.
- quick: edition preview in operations — medium, patch. Say `print.pdf` download instead.

**Acceptance Criteria:**
- Given hold mode is on and the worker is running, when the operator follows `docs/burn-in-week.md` for one morning, then they approve one edition, confirm one A4 print, and know where to note checker polls and `run.log` drops.
- Given the burn-in docs, when the operator reads the density vs copy lists, then every listed lever already exists in dashboard settings and no new capability is required.
- Given seven mornings completed, when the operator uses the log template, then they can record whether hold mode should stay on without opening the codebase.

## Verification

**Commands:**
- None required; no application code changes.

**Manual checks (if no CLI):**
- Read `docs/burn-in-week.md` and confirm it matches `operations.md` and the ticket verify line.
- Confirm the README link resolves.
