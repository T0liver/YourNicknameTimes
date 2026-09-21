# Commit Message Template (Master)

Use this format after each completed step that changes files.

## Required format

```gitmsg
Title (this is a small summary of changes)

- changes
- comes
- in a
- bulletlist
```

## Quick rules

- Title: short, specific, action-oriented.
- Bullets: factual summary of what changed in this step.
- Keep one commit per meaningful step.
- Avoid mixing unrelated changes.

## Examples

### 1) Dispatch setup update

```gitmsg
Prepare M0 dispatch contracts and task states

- moved M0 dispatchable tasks to in_progress
- linked subagent prompts to contract template
- updated backlog with dependency-validated assignments
```

### 2) Review decision update

```gitmsg
Record review outcomes for M0 smoke tasks

- scored returned packages with master scorecard
- accepted platform and data smoke tasks
- marked delivery smoke task for focused rework
```

### 3) Rework request update

```gitmsg
Issue targeted rework for Dropbox smoke validation

- documented failed acceptance criteria and evidence gaps
- constrained rework scope to upload flow diagnostics
- preserved unchanged interfaces and prior accepted behavior
```

### 4) Milestone gate update

```gitmsg
Sign off M0 milestone gates with evidence links

- verified all M0 checklist items as passed
- attached smoke-test evidence references in backlog
- advanced execution plan to M1 wave preparation
```

### 5) Risk register update

```gitmsg
Update risk register after M0 completion

- lowered printer support risk after successful test print
- added monitoring note for CalDAV edge-case parsing
- set next risk review targets for M1 and M2
```

### 6) Loop checkpoint update

```gitmsg
Sync orchestration state after daily loop pass

- refreshed task statuses and blocker ownership
- logged review decisions and next actions
- recorded commit metadata in manager cycle output
```
