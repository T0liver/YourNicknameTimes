# Burn-in week (seven mornings)

This is milestone 8: seven real mornings with hold mode on, one A4 page each, while your checker polls `/status`. You run the Pi, approve each edition, and run the checker. This repo does not ship checker software.

The spec contract lives in [_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/operations.md](../_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/operations.md) under **Burn-in week**. The status JSON rules are in [status-api.md](../_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/status-api.md). Dashboard groups are in [dashboard.md](../_bmad-output/initiative-your-nickname-times/spec-your-nickname-times/dashboard.md).

## Before day one

1. Finish the setup checklist on the home page (nickname, city, Baïkal, feeds, printer, Dropbox).
2. In **Settings → Schedule**, leave **Hold mode** on and **Auto-approve** off.
3. Start `newspaper-worker` and `newspaper-web`. `deploy/install.sh` enables `newspaper-web` (and Caddy) only; run the worker yourself, for example `sudo systemctl start newspaper-worker` if you added a unit, or `.venv/bin/newspaper-worker --data-dir data` in a separate session.
4. Point your checker at `https://newspaper.local/status` (or `https://<pi-ip>/status`). Use the optional plain-HTTP status port if the checker cannot trust the internal certificate. Turn the bearer token on only if you configure the same token on the checker.
5. Copy [burn-in-log.example.md](burn-in-log.example.md) to a file beside your data directory, for example `data/burn-in-log.md`, and fill it as you go.

## Each morning

1. After the scheduled build (weekday 06:30, or weekend 08:00 when the weekend edition is on), the home banner shows run status `awaiting_approval` and **Approve** / **Reject**.
2. On the home page, open today's **print.pdf** link (or open the date row for the run report and PDFs). Check that the file is one A4 page. **Preview** only refreshes `cloud.pdf` and `preview.png`; use it when you want a quick cloud copy, not to judge the held print.
3. **Approve** on the banner when the page is good. The worker prints and uploads on the next wake. Confirm the physical page.
4. If the page is wrong, **Reject** or change settings and use **Regenerate** (or **Run now** after a same-day rebuild). Do not approve an overflow or layout you do not want on paper.
5. Read `data/editions/YYYY-MM-DD/run.log` for `drop:` lines. Write drops and any checker alert in your log.

The home page shows when `/status` was last polled. That line uses the app's loopback URL (`http://127.0.0.1:8080/status`). Point the checker at `https://newspaper.local/status` (or your Pi IP / status port), not the loopback address.

## What you may change during the week

Change only settings you name for density or copy. Everything below already exists in the dashboard.

| Kind | Where | What it affects |
| --- | --- | --- |
| Density | Calendar and tasks | Fewer calendars or lists means less on the page. |
| Density | News | Fewer or lighter feeds, weights, quotas, disabled rows. |
| Density | Weather, daily item, and almanac | Turn extras off, trim the rotation, or disable exchange rates. |
| Density | Weekend touches | Mood `light` vs `neutral`. |
| Density | Model | Off uses deterministic news and prep; on uses the picker. |
| Density | (action) | **Regenerate** after you save a settings change. |
| Copy | General | Nickname, motto, city label on the dateline. |
| Copy | General | Paper language (labels and quotes). |
| Copy | Weekend touches | Greeting text and sun icon. |

`cloud_level` in **Delivery** trims the Dropbox PDF only; it does not change `print.pdf`. Use it if you care about the cloud copy during the week.

Do not ask for new features during burn-in. If something is missing, log it and handle it after the week.

## After day seven

1. Count seven consecutive mornings with one approved A4 print each.
2. Open your checker history: you want steady reachability, and `ok` or explainable `degraded` (for example a known feed glitch), not silent `down` or 502 from Caddy.
3. In **Settings → Schedule**, turn **Hold mode** off when you trust automatic print and upload. Leave it on if you still need daily eyes on the page.

Keep the log with your decision (hold on or off) and any follow-up tweaks.
