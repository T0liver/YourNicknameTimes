# Master Review Scorecard Prompt

Use this prompt whenever a subagent returns a completed task.

---

Review submission for task `{TASK_ID}`.

## Scoring dimensions (0-2 each)

1. **Correctness**
   - 0: incorrect/missing core behavior
   - 1: mostly correct with notable gaps
   - 2: fully correct

2. **Spec Compliance**
   - 0: contradicts spec or ignores required clauses
   - 1: partial compliance
   - 2: fully aligned to referenced spec sections

3. **Reliability / Failure handling**
   - 0: failure paths missing/unsafe
   - 1: partial failure handling
   - 2: robust behavior for expected failures

4. **Security / Privacy**
   - 0: introduces exposure or policy violations
   - 1: acceptable but with concerns
   - 2: secure and compliant

5. **Observability**
   - 0: poor/no logs or diagnostics
   - 1: basic visibility
   - 2: clear actionable logs/metrics/events

6. **Maintainability / Handoff quality**
   - 0: hard to continue/integrate
   - 1: moderate clarity
   - 2: clean handoff with clear contracts

## Evidence sufficiency check

Mark `sufficient` only if submission includes:

- changed files list,
- tests/validation output,
- failure-path verification,
- known limitations,
- downstream handoff notes.

## Decision policy

- **Accept**: total 10-12 and no critical defect.
- **Conditional accept**: total 7-9, only minor defects.
- **Rework**: total <=6 OR any critical defect OR insufficient evidence.

## Review output format

- Task ID:
- Scores by dimension:
- Total:
- Critical defects:
- Minor defects:
- Evidence: `sufficient|insufficient`
- Decision: `accepted|conditional_accept|rework`
- Next action:
