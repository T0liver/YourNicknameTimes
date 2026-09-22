## Contract header

- **Task ID:** M0-A-PLATFORM-SMOKE
- **Milestone:** M0
- **Owner subagent:** Agent A (Platform/Infra)
- **Priority:** P0
- **Depends on:** none
- **Spec references:** `newspaper-spec-v1.1.md` sections 2 (Architecture), 8.1 (Print), 14 (USB printer notes), plus M0 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Validate Pi headless boot + installability of service prerequisites for app stack.
- Validate USB printer detection and CUPS/CLI test print baseline.
- Prepare minimal service scaffolding evidence relevant to M0 smoke readiness.
- Provide objective run notes and command outputs for all smoke checks.

### Out of scope
- Business logic, edition composition, dashboard feature implementation.
- Non-M0 hardening expansions beyond smoke-test baseline.

## Inputs provided

- Upstream artifacts: `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-A-platform-infra.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: Raspberry Pi target, USB printer attached, LAN-only baseline.
- Test fixtures/sample data: N/A (environment/system smoke checks).

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
- objective command/test outputs,
- failure-path checks,
- known limitations,
- next handoff notes for Agents D/E/F/H.