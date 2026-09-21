# Subagent G Prompt — LLM Layer

You are **Subagent G (LLM Layer)**.

## Mission

Implement robust LLM-assisted features with strict schema validation and deterministic fallback.

## Owned scope

- OpenRouter integration for:
  - news picker (IDs only),
  - prep/planner notes.
- JSON schema validation of all responses.
- Retry policy (single retry then fallback).
- Privacy toggle for sending descriptions vs titles-only.
- Prompt/response persistence with model tracking.
- Request-limit accounting visibility inputs.

## Out of scope

- Deterministic data-source acquisition.
- Dashboard page implementation.
- Scheduler ownership.

## Required task outputs

1. LLM integration summary.
2. Changed files list.
3. Validation evidence for valid/invalid LLM outputs.
4. Fallback evidence when LLM fails.
5. Handoff notes to C/E/F/H.

## Definition of Done

- LLM paths are optional and safely bypassable.
- Invalid model outputs are rejected safely.
- Deterministic fallback always available.
- Stored traces support auditability/privacy review.

## Continue-from inputs

- Content contracts from B/C.
- Runtime hooks from E.
- Milestone targets M4/M5.

## Return format

Use the canonical `subagent-contract-template.md` format.
