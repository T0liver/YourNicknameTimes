## Contract header

- **Task ID:** M1-C-LAYOUT-BOOTSTRAP
- **Milestone:** M1
- **Owner subagent:** Agent C (Edition Engine)
- **Priority:** P1
- **Depends on:** M0-A-PLATFORM-SMOKE, M0-B-DATA-SMOKE (accepted)
- **Spec references:** `newspaper-spec-v1.1.md` sections 4 (edition content structure), 5.1-5.5 (layout/render constraints), weekend behavior in 4.3, plus M1 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Build static edition composition bootstrap for fake Hungarian data.
- Produce deterministic snapshot payload suitable for one-page A4 render testing.
- Validate masthead/title/motto collapse behavior in snapshot/template inputs.
- Validate weekend icon + greeting toggle behavior at composition layer.
- Provide render-facing metadata needed by Agent D for M1-D.

### Out of scope
- Final printer-fit validation and Pi render-time benchmarking (M1-D ownership).
- Real-source deterministic integrations (M2 scope).
- LLM integration behavior (M4 scope).

## Inputs provided

- Upstream artifacts: `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-C-edition-engine.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: fake HU fixtures are permitted for M1 static layout validation.
- Test fixtures/sample data: representative fake Hungarian edition data covering weekdays/weekends, empty motto case, HU diacritics (`ő`, `ű`).

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
- fake HU edition composition snapshot,
- diacritic-safe content path for `ő` and `ű`,
- empty motto collapse behavior,
- weekend sun icon + greeting behavior inputs,
- handoff package for M1-D render verification.