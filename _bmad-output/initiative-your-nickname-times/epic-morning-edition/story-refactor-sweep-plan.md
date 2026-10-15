---
title: '1.10 Refactor sweep'
type: 'refactor'
ticket: '10'
created: '2026-10-15'
status: 'built'
baseline_revision: '1eac77e1c8d13aa09076a5d0a8298eda7f87099f'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/initiative-your-nickname-times/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Stories 1.1–1.9 left patch items in plan Review Triage Logs. Some fixes landed in later stories; others were marked moot on this loopback or deferred. Story 1.10 must close the rest without new product behavior.

**Approach:** Walk each epic plan triage entry, confirm the fix in tree or record deferral in `deferred-work.md`, then run the same pytest slice used for deterministic edition, held delivery, and `/status`.

</frozen-after-approval>

## Implementation Notes

Sweep started from `baseline_revision` with a clean working tree. No application code changed on this story; patch debt from stories 1.2–1.8 was already on `main`. This artifact records verification and defers the two items in `deferred-work.md`.

## Tasks & Acceptance

**Execution:**
- [x] `story-render-one-static-a4-page-plan.md` triage — Empty weather/almanac blocks and weekend greeting: `edition.html.j2` uses content checks and `greeting` in the masthead.
- [x] `story-build-the-deterministic-edition-plan.md` triage — Lock, `record_edition`, xkcd, on-this-day, spanning events, task search: already described as fixed in that log; confirmed in `db.py`, `edition_build.py`, and edition tests.
- [x] `story-run-the-worker-and-deliver-plan.md` triage — Settings merge, `_edition_exists`, canceled print jobs: `seed()` merges keys; worker and `status_report` share the editions-or-non-failed-run rule; `_print_job` fails on canceled/aborted CUPS state.
- [x] `story-add-the-news-picker-and-planner-plan.md` triage — Stale `llm/` when off: `_clear_stored` in `apply_model`; prompt titles collapsed via `_one_line`. Moot items (secrets rewrite, reasoning unpack, key strip) unchanged.
- [x] `story-serve-the-dashboard-and-status-plan.md` triage — Preview copies, reprint, HEAD `/status`, pending insert, run-now date, timezone, regenerate placement: fixed or moot per that log; `web.py` and `worker.py` match.
- [x] `story-harden-lan-access-plan.md` triage — Boot order, rollback port file, rate-limit lock, reserved ports, nftables before Caddy: `deploy/` and `tests/test_lan.py` assert the intended order and behavior.
- [x] `deferred-work.md` — OpenRouter empty key vs `/status` model check; settings read failure on `/status` token path: remain deferred, not reopened in this sweep.

**Acceptance Criteria:**
- Given each non-moot patch line in epic plans 1.2–1.8, when the codebase is checked, then the described bug is fixed or the item is explicitly moot or listed in `deferred-work.md`.
- Given the verification command below, when it is run, then all listed tests pass with no network.
- Given hold mode and the worker tests, when they run, then held delivery behavior still passes.

## Verification

**Commands:**
- `uv run python -m pytest tests/test_render.py tests/test_edition.py tests/test_sources.py tests/test_worker.py tests/test_llm.py tests/test_status.py tests/test_web.py tests/test_lan.py` — expected: all pass, no network

## Review Triage Log

- quick — render empty rail / greeting: false (reject as open work); template already gates weather, almanac, and greeting.
- quick — build edition triage lines: false; fixes present before this story; log is historical.
- quick — worker seed, edition exists, print terminal states: false; covered by `test_existing_settings_gain_only_missing_delivery_keys`, catch-up tests, and `_print_job` branches.
- quick — llm folder when off, prompt newlines: false; `_clear_stored` and `_one_line` in place.
- quick — dashboard/worker triage (non-moot): false; behavior matches amended plan notes.
- quick — LAN boot, rollback port, rate limit, bad status ports, nftables install order: false; `test_install_enables_avahi_and_security_updates_without_editing_sshd` and related tests.
- quick — deferred OpenRouter `/status` and settings-read token: defer; entries already in `deferred-work.md`, out of scope for a no-behavior sweep.
