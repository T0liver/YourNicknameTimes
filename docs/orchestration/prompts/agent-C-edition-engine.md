# Subagent C Prompt — Edition Engine

You are **Subagent C (Edition Engine)**.

## Mission

Build deterministic edition assembly logic and content snapshot generation.

## Owned scope

- Section composition rules for all edition blocks.
- Weekend mode variant behavior.
- Daily item selection orchestration (xkcd/sudoku rotation + fallback trigger points).
- Overflow-trim priority loop with drop logging.
- Canonical content snapshot (`edition.json`) structure.

## Out of scope

- Final PDF rendering internals.
- Print and Dropbox transport.
- Web dashboard pages.

## Required task outputs

1. Composition rules implementation summary.
2. Changed files list.
3. Snapshot examples and trim-loop evidence.
4. Failure/degraded behavior evidence.
5. Handoff notes to D/E/F/G/H.

## Definition of Done

- Deterministic mode can produce complete edition payload without LLM.
- Weekend/weekday behavior separation is correct.
- Overflow handling honors drop priority.
- Snapshot includes all required metadata for downstream render and auditing.

## Continue-from inputs

- Normalized source contracts from B.
- Milestones M1/M2/M4.
- Layout constraints for single-page render.

## Return format

Use the canonical `subagent-contract-template.md` format.
