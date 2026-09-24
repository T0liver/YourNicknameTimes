# M2-B Source and License Decision Record

Task: `M2-B-FULL-SOURCES`
Date: 2026-09-24

## Decisions

1. **CalDAV events/tasks**
   - Source: user-owned Baïkal CalDAV collections.
   - License: user data (no third-party content license imposed by adapter).
   - Decision: integrate as configured private source; no redistribution assumptions.

2. **RSS ingest/filter/dedup**
   - Source: user-managed feed list and OPML import/export.
   - License: depends on each feed publisher.
   - Decision: pipeline stores normalized metadata (`title`, `url`, `publisher`, `published`) without rewriting content.

3. **Weather**
   - Source: Open-Meteo API.
   - License: Open-Meteo terms apply (attribution/usage constraints handled at UI/reporting layer).
   - Decision: consume deterministic numeric/text forecast fields only; omit on failure.

4. **Almanac (sun/moon/name-day/on-this-day)**
   - Sun/moon: computed/local payload path, no external license dependency for generated astronomical values.
   - Name day: project-provided static table (license verification remains a tracked gate risk in `risk-register.md` R-010).
   - On-this-day: Wikipedia feed path planned; content attribution and CC BY-SA notice required in render/output layer.
   - Decision: adapter accepts normalized entries and preserves source text; omits unavailable components.

5. **FX rates (EUR/HUF, USD/HUF, CHF/HUF)**
   - Source selected for current contract: ECB-derived daily reference rates (cross-rate to HUF in upstream acquisition).
   - License/terms: provider terms apply; output includes `published_date` + `source` for traceability.
   - Decision: normalize only verifiable pairs; omit entire rates block if required fields are missing.

## Gate note

This record satisfies M2 gate requirement to document source/license choices. Remaining legal/attribution text presentation is downstream in render/dashboard layers.