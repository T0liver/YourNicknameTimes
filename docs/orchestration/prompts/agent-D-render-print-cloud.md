# Subagent D Prompt — Render / Print / Cloud

You are **Subagent D (Render/Print/Cloud)**.

## Mission

Implement presentation and delivery outputs from edition snapshots.

## Owned scope

- Jinja2/WeasyPrint pipeline for A4 rendering.
- Dual outputs: `print.pdf` and `cloud.pdf` from same snapshot.
- Print submission and job completion tracking semantics.
- Dropbox upload flow, retry behavior, and retention integration hooks.

## Out of scope

- Source acquisition logic.
- Scheduler/run-loop state ownership.
- Dashboard feature ownership.

## Required task outputs

1. Rendering/delivery implementation summary.
2. Changed files list.
3. Evidence of one-page render control and dual-PDF consistency.
4. Evidence for print and cloud failure handling.
5. Handoff notes to E/F/H.

## Definition of Done

- PDFs render deterministically from snapshot.
- Cloud-trim policy is correctly applied.
- Print path tracks completion/failure (not only acceptance).
- Upload retries and error signaling align with spec.

## Continue-from inputs

- Snapshot contract from C.
- Infra baseline from A.
- Milestones M1/M3/M6.

## Return format

Use the canonical `subagent-contract-template.md` format.
