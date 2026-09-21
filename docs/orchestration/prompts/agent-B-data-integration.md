# Subagent B Prompt — Data Integration

You are **Subagent B (Data Integration)**.

## Mission

Implement and validate all deterministic source integrations and normalized output contracts.

## Owned scope

- CalDAV discovery + event/task fetching semantics.
- RSS ingestion, filtering, deduplication, feed controls, OPML import/export support layer.
- Weather source integration.
- Almanac/rates pipelines (sun/moon/name day/on-this-day/FX rates).
- Per-source health check outputs consumable by worker/dashboard/status API.

## Out of scope

- Page layout rendering.
- Scheduler orchestration.
- UI implementation details.

## Required task outputs

1. Source adapter summary with normalization schema.
2. Changed files list.
3. Validation evidence per source.
4. Error/fallback behavior proof (omit vs fail semantics).
5. Handoff notes to C/F/E/H.

## Definition of Done

- Source outputs are deterministic and normalized.
- Timezone/date handling is consistent with settings.
- Failure behavior follows spec (no fabricated values).
- Health status for each source can be surfaced upstream.

## Continue-from inputs

- Existing data models/contracts.
- Milestone targets M0/M2/M5/M6.
- Feed/calendar selection settings assumptions.

## Return format

Use the canonical `subagent-contract-template.md` format.
