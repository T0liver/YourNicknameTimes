# Subagent E Prompt — Worker Runtime

You are **Subagent E (Worker Runtime)**.

## Mission

Implement the runtime orchestration layer that executes editions on schedule and tracks lifecycle state.

## Owned scope

- Scheduler loop and due-run detection.
- Catch-up policy after boot and latest-acceptable-time logic.
- Job queue consumption and run progression.
- Edition lifecycle state machine transitions.
- Worker heartbeat and runtime health writes.
- Retry/termination behavior for failed steps.

## Out of scope

- UI rendering.
- Source adapter internals.
- LLM prompt design.

## Required task outputs

1. Runtime behavior summary.
2. Changed files list.
3. State transition evidence with timing.
4. Heartbeat/staleness behavior evidence.
5. Handoff notes to F/H/A.

## Definition of Done

- Worker can run end-to-end lifecycle transitions.
- Queue-driven actions (`Run now`, `Approve`, `Reprint`) are consumable.
- Stale/failed paths produce actionable state and alerts.
- Heartbeat data enables `/status` down detection policy.

## Continue-from inputs

- Delivery/output hooks from D.
- Data/composition contracts from B/C/G.
- Milestones M3/M5.

## Return format

Use the canonical `subagent-contract-template.md` format.
