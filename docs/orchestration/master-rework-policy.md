# Master Rework Policy Prompt

Use this to issue focused rework when a task is not acceptable.

---

You are issuing a **targeted rework** for task `{TASK_ID}`.

## Rework principles

1. Rework scope must be **minimal delta**.
2. Preserve already accepted behavior.
3. Keep ownership unchanged unless escalated.
4. Every rework item must map to a failed criterion.

## Defect classes

- **Critical**: blocks milestone gate, violates core spec, severe security/privacy risk, data corruption risk.
- **Major**: important behavior incorrect or fragile.
- **Minor**: polish/documentation/non-blocking clarity issue.

## Rework prompt structure

1. **Reason for rework**
   - list failed scorecard criteria
   - list failed milestone gate checks
2. **Delta scope**
   - exact fixes required
   - explicit non-goals
3. **Unchanged constraints**
   - contracts/interfaces that must remain stable
4. **Evidence required**
   - exact tests and outputs needed
5. **Deadline/priority**

## Escalation rule

- If task fails rework twice, escalate to architecture review.
- Architecture review may:
  - split task,
  - adjust interface contract,
  - re-sequence dependencies,
  - reassign ownership (with rationale).

## Rework output format required from subagent

- Fixed items vs requested deltas
- Evidence for each fixed item
- Residual risk
- Ready for re-review: yes/no
