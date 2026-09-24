## Contract header

- **Task ID:** M2-B-FULL-SOURCES
- **Milestone:** M2
- **Owner subagent:** Agent B (Data Integration)
- **Priority:** P0
- **Depends on:** M0-B-DATA-SMOKE (accepted)
- **Spec references:** `newspaper-spec-v1.1.md` sections 6.1-6.5 (CalDAV, RSS, weather, almanac, rates), M2 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Implement deterministic full-source integrations and normalized output contracts for:
  - CalDAV events/tasks,
  - RSS ingest/filter/dedup,
  - weather,
  - almanac (sun/moon/name-day/on-this-day),
  - FX rates (EUR/HUF, USD/HUF, CHF/HUF).
- Implement explicit failure semantics (omit/degraded, never fabricate values).
- Provide source health outputs consumable by worker/dashboard/status layers.
- Document source/license decisions required by M2 gate.

### Out of scope
- Edition composition/overflow policy ownership (Agent C).
- Rendering/print/cloud delivery ownership (Agent D).
- Dashboard UI implementation details (Agent F).

## Inputs provided

- Upstream artifacts: `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-B-data-integration.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: source credentials/settings available via configured environment.
- Test fixtures/sample data: deterministic fixtures and/or recorded payloads for edge cases (date-only/date-time, missing published time, API outage).

## Required outputs

1. Implementation summary
2. Changed files list
3. Validation/test evidence
4. Failure-path verification evidence
5. Known limitations
6. Downstream handoff notes

## Definition of Done

- Functional behavior implemented per scope.
- Failure behavior matches spec and fallback rules.
- Logging/telemetry added where relevant.
- Integration contract unchanged OR migration/update documented.
- Evidence package complete and reproducible.

## Return format (mandatory)

- **Status:** `completed|blocked`
- **What was done:**
- **Files changed:**
- **Evidence:**
- **Failure-path checks:**
- **Known limitations:**
- **Next handoff:**
- **Open risks/blockers:**

## Blocked-state rule

If blocked, stop implementation and return:

1. exact blocker,
2. impact,
3. missing dependency/artifact,
4. proposed unblock action.

## Quality self-check before return

- [ ] Stayed within scope
- [ ] Did not violate ownership boundaries
- [ ] DoD criteria all addressed
- [ ] Evidence package complete
- [ ] Handoff notes actionable

## Master tracking requirement

Provide explicit 30/70/100 progress checkpoints.
At 100%, include evidence specifically covering:
- deterministic output contracts per source,
- CalDAV recurring/date handling correctness,
- RSS recency/dedup behavior,
- weather/almanac/rates omit-on-failure semantics,
- source/license decision record for M2 gate.