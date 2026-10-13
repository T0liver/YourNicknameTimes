# Delivery

Run states are drawn in architecture-diagrams.md. A run ends as `done`, `done_degraded`, or `failed`. Every run record stores per-step timing, the result of each source, the model used, the items trimmed, and the delivery result.

## Failure policy

- A source fails: that block falls back or collapses, and the run continues as degraded.
- The model fails after one retry: that block uses its deterministic fallback, and the run continues as degraded.
- The PDF cannot be built, or still exceeds one page after trimming: the run fails, nothing prints, and an alert is raised.
- Print fails: an alert is raised, and the PDF stays available for a manual reprint.
- Dropbox fails: the upload is retried on the next worker cycle. An alert appears after three failures.

An edition that is waiting for approval counts as produced for monitoring. A wait longer than 1 hour raises an information alert, not a failure.

## Schedule

The configured time is when the build starts. Delivery follows when the build succeeds, or when the operator approves, in hold mode.

- Weekday start: 06:30 by default.
- Weekend start: 08:00 by default, used only when the weekend edition is on.
- Latest acceptable time: 10:00 by default. On boot, a missed run is caught up only if the clock is still before this time.
- The worker does not build until NTP sync is confirmed. The Pi 3B+ has no real-time clock, and a wrong clock would make `AS OF` and the day boundary wrong.

Print and upload each have an on/off switch, so the edition can do both, one, or neither. One-day overrides cover "skip tomorrow" and "upload only tomorrow".

## Print

- CUPS `lp`, A4, grayscale, 100% scale. Duplex is on by default, and the operator can turn it off.
- The worker follows the CUPS job until it completes or fails. "Accepted by CUPS" is not treated as printed.
- The dashboard can print a test page and can reprint an edition.

## Dropbox

- A Dropbox app with app-folder access, so the Pi can write only inside its own folder.
- Authorization is the headless flow: open a link, approve, paste the code back. A refresh token is stored.
- Files: `editions/YYYY-MM-DD.pdf` plus a fixed `latest.pdf`. The fixed name keeps the reMarkable import path stable. That import is pull-based: browse, long-press, import.
- Retention defaults to keep forever, and the period is a setting.

## Hold mode

Hold mode is on by default. The edition builds at the scheduled time and waits as `awaiting_approval`.

Dashboard actions on a held edition: Approve, Reject, Regenerate, and Download preview.

- Approve prints and uploads the files that were built.
- Reject stops delivery.
- Regenerate fetches fresh data and sets a new `AS OF` time. Use it when the held data is hours old.
- An optional auto-approve time exists and defaults off.

## Retention

Local files default to 30 days. Dropbox defaults to forever. Both are editable. Local pruning deletes the PDFs, previews, and snapshots of expired editions. The editions list on the dashboard follows the local period.
