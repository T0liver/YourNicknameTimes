# Risk Register

Use this register to track delivery, architecture, integration, and operational risks.

## Severity scale

- `High` = likely milestone blocker or major reliability/security impact.
- `Medium` = meaningful delay or quality reduction.
- `Low` = manageable issue with limited impact.

## Status values

- `open`
- `monitoring`
- `mitigating`
- `closed`

## Risk Table

| Risk ID | Category | Description | Severity | Likelihood | Owner | Mitigation plan | Contingency | Trigger / early signal | Target date | Status | Last update |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R-001 | Hardware/Printer | USB printer model may have poor Linux driver support or weak status reporting | High | Medium | Agent A | Validate via CUPS/OpenPrinting early in M0; lock known-good settings | Choose compatible replacement printer profile or fallback print settings | Test page fails or job state unavailable | M0 end | open |  |
| R-002 | Data/CalDAV | Baïkal task/event structures may vary; discovery and parsing edge cases | Medium | Medium | Agent B | Build robust discovery + normalize date-only/date-time + recurrence handling | Disable failing list/calendar and continue degraded | Parse errors, missing recurring instances | M2 mid | open |  |
| R-003 | LLM/Quality | Free model variability may produce invalid JSON or weak Hungarian outputs | Medium | High | Agent G | Enforce strict schemas + retry + deterministic fallback | Force LLM-off mode for stable daily operation | Repeated schema rejections or quality complaints | M4 end | open |  |
| R-004 | Performance | Pi 3B+ render/runtime latency may exceed morning window | High | Medium | Agent D | Benchmark render and worker timings in M1/M3; optimize templates and caching | Earlier schedule start or reduced content density | Render > target budget consistently | M3 end | open |  |
| R-005 | Security | Misconfigured `/status` or dashboard auth may leak info on LAN | High | Low | Agent F | Enforce no-personal-data status payload + auth/CSRF/rate limit checks | Enable optional token + strict firewall policy | Security check failures in M7 | M7 end | open |  |
| R-006 | Reliability | Worker heartbeat/state drift could cause false `down`/`degraded` signals | Medium | Medium | Agent E | Add robust heartbeat writes and staleness logic tests | Increase grace thresholds temporarily with alerting | Inconsistent status vs actual run state | M5 end | open |  |
| R-007 | External APIs | Weather/rates/on-this-day source instability or quota changes | Medium | Medium | Agent B | Add caching/backoff/source health checks and graceful omission | Switch provider implementation behind same contract | Frequent fetch failures over 3 days | M2 end | open |  |
| R-008 | Delivery/Cloud | Dropbox auth token refresh or upload failures reduce reliability | Medium | Medium | Agent D | Implement refresh/retry/error surfacing + re-upload action | Keep print path independent; manual upload fallback | 3+ consecutive upload failures | M3 end | open |  |
| R-009 | Project/Coordination | Multi-agent contract drift causes integration delays | High | Medium | Master | Version interface contracts + strict review gates | Pause dispatch and run contract alignment checkpoint | Rework loops increase across tasks | continuous | open |  |
| R-010 | Content/License | Name-day or historical source licensing unclear | Medium | Low | Agent B / Master | Record source/license decision during M2 | Disable unresolved item toggle by default | Missing verifiable license metadata | M2 end | open |  |

## Review routine

- Review top 3 highest severity open risks at each milestone transition.
- Escalate any High+High risk immediately.
- Every closed risk must include closing evidence and date.
