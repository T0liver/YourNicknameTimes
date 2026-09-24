## Contract header

- **Task ID:** M1-D-A4-RENDER
- **Milestone:** M1
- **Owner subagent:** Agent D (Render/Print/Cloud)
- **Priority:** P0
- **Depends on:** M1-C-LAYOUT-BOOTSTRAP (accepted)
- **Spec references:** `newspaper-spec-v1.1.md` sections 5.1-5.5 (A4 layout, glyph checks, overflow handling baseline constraints), section 8.1 print baseline, plus M1 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope

- Validate one-page A4 render from Agent C snapshot/template path.
- Verify Hungarian glyph rendering for `ő` and `ű` in all used fonts.
- Verify `{Nickname} Times` masthead rendering and empty motto no-gap collapse.
- Validate weekend sun icon + greeting render behavior.
- Validate print margins/output sensibility on target printer.
- Measure and report render time on Raspberry Pi target.

### Out of scope

- Full M3 print lifecycle robustness and Dropbox retry policies.
- Source integration logic and deterministic composition ownership.
- Dashboard/UI feature ownership.

## Inputs provided

- Upstream artifacts: accepted `M1-C-LAYOUT-BOOTSTRAP` outputs, `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-D-render-print-cloud.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: Pi printer baseline from M0-A is available (`newspaper-printer`).
- Test fixtures/sample data: fake HU snapshot from Agent C, plus weekend/empty-motto variants.

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

- one-page A4 proof,
- glyph proof for `ő` and `ű`,
- masthead + empty motto-collapse proof,
- weekend icon/greeting render proof,
- printer margin/output verification,
- measured Pi render time.
