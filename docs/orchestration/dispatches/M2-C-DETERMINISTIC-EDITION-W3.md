## Contract header

- **Task ID:** M2-C-DETERMINISTIC-EDITION
- **Milestone:** M2
- **Owner subagent:** Agent C (Edition Engine)
- **Priority:** P0
- **Depends on:** M2-B-FULL-SOURCES (accepted)
- **Spec references:** `newspaper-spec-v1.1.md` sections 3, 4, 5.4, 7.1 deterministic mode, M2 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Build deterministic edition assembly using real integrated sources from Agent B (no LLM dependency).
- Implement/verify:
  - daily item logic (sudoku/xkcd) with fallback,
  - canonical `edition.json` snapshot persistence,
  - overflow drop loop with deterministic priority + dropped-item logging.
- Produce sample deterministic editions and logs proving M2 gate criteria.

### Out of scope
- LLM picker/planner integration (M4 scope).
- Print/cloud transport robustness (M3-D scope).
- Dashboard UI/state surfaces (M5/M6 scope).

## Inputs provided

- Upstream artifacts: accepted `M2-B-FULL-SOURCES` normalized contracts, `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-C-edition-engine.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: deterministic mode active; source health states provided by B.
- Test fixtures/sample data: representative source bundles that trigger normal and overflow scenarios.

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
- deterministic real-source edition generation,
- daily-item fallback correctness,
- persisted `edition.json` samples,
- overflow drop-loop logs showing dropped items in priority order,
- clear handoff package for M3/M4/M5 consumers.