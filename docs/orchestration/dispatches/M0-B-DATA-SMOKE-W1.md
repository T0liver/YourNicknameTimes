## Contract header

- **Task ID:** M0-B-DATA-SMOKE
- **Milestone:** M0
- **Owner subagent:** Agent B (Data Integration)
- **Priority:** P0
- **Depends on:** none
- **Spec references:** `newspaper-spec-v1.1.md` sections 6.1 (CalDAV), 6.2/6.3 high-level source behavior as relevant to smoke, plus M0 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Implement/validate CalDAV listing script that shows calendars/task lists.
- Validate baseline source-adapter smoke behavior needed for M0 data readiness.
- Provide objective run notes and command outputs proving M0 data smoke pass/fail.

### Out of scope
- Full deterministic source integration for M2.
- Rendering, scheduler, dashboard implementation.

## Inputs provided

- Upstream artifacts: `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-B-data-integration.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: Baïkal reachable with configured credentials and timezone defaults.
- Test fixtures/sample data: Live endpoint or representative non-secret test config.

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

Provide explicit 30/70/100 progress checkpoints in your update stream.
At 100%, return complete evidence package with:
- changed files,
- objective command/test outputs,
- failure-path checks,
- known limitations,
- next handoff notes for Agents C/E/F/H.