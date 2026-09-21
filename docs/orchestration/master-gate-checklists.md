# Milestone Gate Checklists (M0-M8)

Use these as hard pass/fail criteria before milestone sign-off.

---

## M0 — Smoke tests

- [ ] Pi boots headless and service prerequisites are installable.
- [ ] USB printer detected and CLI/CUPS test print succeeds.
- [ ] CalDAV listing script shows calendars/task lists.
- [ ] OpenRouter test call returns valid response.
- [ ] Dropbox app-folder upload succeeds.

Evidence required: command/test outputs and run notes.

## M1 — Static A4 layout

- [ ] Fake Hungarian data renders to exactly one A4 page.
- [ ] Hungarian glyphs (`ő`, `ű`) are correct in all used fonts.
- [ ] `{Nickname} Times` masthead renders correctly.
- [ ] Empty motto collapses without layout gap.
- [ ] Weekend sun icon + greeting render behavior validated.
- [ ] Print margins/output are sensible on target printer.
- [ ] Render time measured on Pi.

Evidence required: PDFs/screenshots + measurements.

## M2 — Deterministic edition

- [ ] Real CalDAV/RSS/weather/almanac/rates integrated without LLM.
- [ ] Sudoku/xkcd daily item logic works with fallback.
- [ ] Content snapshot (`edition.json`) persisted.
- [ ] Overflow drop loop works and logs dropped items.
- [ ] Data source/license decisions documented where required.

Evidence required: sample editions, logs, source notes.

## M3 — Worker and delivery

- [ ] Worker daemon scheduler loop operates reliably.
- [ ] Catch-up after boot works with cutoff policy.
- [ ] Hold mode lifecycle works (`awaiting_approval` path).
- [ ] Print delivery tracks actual job result.
- [ ] Dropbox upload + retry path works.
- [ ] Retention pruning executes correctly.

Evidence required: lifecycle traces + delivery logs.

## M4 — LLM layer

- [ ] News picker and planner calls implemented.
- [ ] JSON schema validation enforced.
- [ ] One retry then deterministic fallback works.
- [ ] Global LLM on/off behavior validated.
- [ ] Weekend `light` mood behavior validated.
- [ ] Prompts/responses and model used are persisted.

Evidence required: call traces + fallback cases.

## M5 — Dashboard v1 + /status

- [ ] Login/authentication works.
- [ ] Status tiles and edition states displayed correctly.
- [ ] Approve/reject/regenerate actions work.
- [ ] Edition downloads and logs are accessible.
- [ ] `/status` returns proper JSON shape and semantics.
- [ ] Worker stop transitions `/status` to down within target window.
- [ ] Printer fault appears as degraded.
- [ ] Web service stop makes endpoint unreachable.

Evidence required: endpoint outputs + UI action traces.

## M6 — Dashboard v2

- [ ] Full settings sections implemented with validation.
- [ ] Test buttons work per integration section.
- [ ] Dropbox auth flow works.
- [ ] OPML import/export works.
- [ ] Printer picker and test page flow work.
- [ ] Setup checklist and mobile usability validated.

Evidence required: settings walkthrough + test outputs.

## M7 — Hardening

- [ ] HTTPS via Caddy configured.
- [ ] First-run setup code flow in place.
- [ ] Login rate limiting active.
- [ ] Firewall policy applied (LAN scope + optional status port).
- [ ] Auto-updates/security posture documented.
- [ ] Optional `/status` token mode works.

Evidence required: config proofs + security checks.

## M8 — Burn-in

- [ ] One week hold-mode run completed.
- [ ] External checker polls `/status` continuously.
- [ ] Alerts/noise tuned.
- [ ] Density/copy adjustments documented.
- [ ] Final go/no-go recommendation issued.

Evidence required: burn-in report + incident summary.
