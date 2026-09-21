# Orchestration Prompt Pack

This folder contains a ready-to-run Master/Subagent orchestration pack for implementing **Your Nickname Times** from `newspaper-spec-v1.1.md`.

## Structure

- `master-kickoff.md` — Master mission, constraints, and startup flow
- `master-daily-loop.md` — dispatch/check/review cadence
- `master-review-scorecard.md` — objective scoring rubric and decision policy
- `master-rework-policy.md` — rework and escalation rules
- `master-gate-checklists.md` — milestone gates M0–M8
- `contracts/subagent-contract-template.md` — canonical subagent contract template
- `prompts/agent-A-platform-infra.md`
- `prompts/agent-B-data-integration.md`
- `prompts/agent-C-edition-engine.md`
- `prompts/agent-D-render-print-cloud.md`
- `prompts/agent-E-worker-runtime.md`
- `prompts/agent-F-web-dashboard-status.md`
- `prompts/agent-G-llm-layer.md`
- `prompts/agent-H-qa-hardening.md`

## Global rules

1. Master never writes implementation code.
2. Subagents only work inside their owned scope.
3. Every delivery must include objective evidence.
4. All acceptance is tied to milestone gates and spec requirements.
5. Master creates a git commit after each completed step that changes files, using:

```gitmsg
Title (this is a small summary of changes)

- changes
- comes
- in a
- bulletlist
```
