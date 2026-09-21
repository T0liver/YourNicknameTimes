# Subagent Task Contract Template

Use this template for every dispatched subagent task.

---

## Contract header

- **Task ID:**
- **Milestone:**
- **Owner subagent:**
- **Priority:**
- **Depends on:**
- **Spec references:**

## Scope

### In scope
- 

### Out of scope
- 

## Inputs provided

- Upstream artifacts:
- Interface contracts:
- Configuration assumptions:
- Test fixtures/sample data:

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
