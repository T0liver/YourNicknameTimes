## Contract header

- **Task ID:** M0-D-DELIVERY-SMOKE
- **Milestone:** M0
- **Owner subagent:** Agent D (Render/Print/Cloud)
- **Priority:** P0
- **Depends on:** none
- **Spec references:** `newspaper-spec-v1.1.md` sections 7 (LLM layer smoke relevance for OpenRouter test path), 8.2 (Dropbox upload behavior), plus M0 gate in `docs/orchestration/master-gate-checklists.md`

## Scope

### In scope
- Validate OpenRouter test call path returns valid response.
- Validate Dropbox app-folder upload smoke succeeds.
- Provide objective command/log/test outputs and run notes for both checks.

### Out of scope
- Full M1 rendering controls or M3 robust retry/retention implementation.
- Scheduler and dashboard behavior ownership.

## Inputs provided

- Upstream artifacts: `newspaper-spec-v1.1.md`, `docs/orchestration/master-gate-checklists.md`, `docs/orchestration/prompts/agent-D-render-print-cloud.md`
- Interface contracts: `docs/orchestration/contracts/subagent-contract-template.md`
- Configuration assumptions: Valid OpenRouter key path and Dropbox app credentials are available in test environment.
- Test fixtures/sample data: Minimal deterministic smoke payload and upload target.

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
- next handoff notes for Agents E/F/H.