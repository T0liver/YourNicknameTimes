## Contract header

- **Task ID:** M2-B-FULL-SOURCES-R1
- **Milestone:** M2
- **Owner subagent:** Agent B (Data Integration)
- **Priority:** P0
- **Depends on:** M0-B-DATA-SMOKE (accepted)
- **Spec references:** `newspaper-spec-v1.1.md` sections 6.1-6.5, M2 gate in `docs/orchestration/master-gate-checklists.md`, rework policy in `docs/orchestration/master-rework-policy.md`

## Reason for rework

- Failed criterion: M2 gate requires real-source integration evidence; current package is fixture-dominant.
- Failed criterion: full-integration scope expects live fetch/auth wiring coverage in evidence.

## Delta scope

### In scope
- Add/confirm live fetch/auth wiring for CalDAV, RSS, weather, almanac/on-this-day, and rates.
- Provide objective live-source success evidence for each enabled source path.
- Preserve deterministic normalization contract (`m2.full_sources.v1`) and existing failure semantics.

### Out of scope
- No schema redesign.
- No edition composition, rendering, or dashboard changes.
- No M3/M4 feature work.

## Inputs provided

- Upstream artifacts: prior M2-B outputs + validation harness + `source-license-decisions.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: live credentials/endpoints available in runtime environment.
- Test fixtures/sample data: existing fixture bundles remain for regression safety.

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

## Evidence required (explicit)

- One live success run per source family (CalDAV, RSS, weather, almanac, rates) with objective output.
- At least one live auth/error-path check proving controlled degraded behavior.
- Updated source/license notes where live provider choice/attribution changed.

## Blocked-state rule

If blocked, stop implementation and return:

1. exact blocker,
2. impact,
3. missing dependency/artifact,
4. proposed unblock action.

## Quality self-check before return

- [ ] Stayed within scope
- [ ] Preserved accepted deterministic contracts
- [ ] DoD criteria all addressed
- [ ] Evidence package complete
- [ ] Handoff notes actionable

## Master tracking requirement

Provide explicit 30/70/100 progress checkpoints.
At 100%, include a compact evidence matrix mapping each source family to command/output/exit result.