# Status API

An external checker, for example Uptime Kuma or any HTTP JSON monitor, polls this endpoint. If it can read a healthy response, the system is healthy. If it cannot reach the endpoint, the system is down. The Pi does not push a heartbeat to the outside.

## Endpoint

- `GET /status` on `https://newspaper.local/status` and on `https://<pi-ip>/status`. `HEAD` answers too.
- The body is JSON. `Cache-Control: no-store`.
- No login by default. An optional token (`Authorization: Bearer ...`) can be turned on in settings. It defaults off.
- The response contains no personal data: no task or event text, no feed URLs, no secrets. Error messages are redacted.
- The payload is computed from the database and the worker heartbeat, and cached for a few seconds, so polling stays cheap.
- An optional plain-HTTP port that serves only this endpoint exists for checkers that cannot accept the internal certificate. It defaults off. Otherwise the checker trusts the certificate or ignores certificate errors.

## HTTP status

| Code | Meaning |
| --- | --- |
| 200 | `status` is `ok` or `degraded`. The service is up. |
| 503 | `status` is `down`. |
| 200 or 503 for degraded | `?strict=1` returns 503 for `degraded` as well, for checkers that alert only on non-200 codes. |
| No response, timeout, connection refused, or 502 | The Pi, the web service, or the proxy is down. The checker treats that as down. |

## Overall status

`down` when any of these is true:

- The worker heartbeat is stale. The default is no beat for 2 minutes.
- The latest acceptable time has passed, no edition was built, and none is in progress or awaiting approval.
- The database is unreadable.
- The clock has not synced after boot, and more than 1 hour has passed.
- Free disk space is under 100 MB.

`degraded` when any of these is true:

- The last edition ended `done_degraded`.
- Any source check is red or yellow: Baïkal, feeds, weather, almanac, the model, or Dropbox.
- The printer reports a problem.
- A run failed, and the service can still run.
- Open warning-level alerts exist.

`ok` is everything else. An edition awaiting approval, by itself, is still `ok`.

## Response shape

Field names stay stable so a checker can assert on one field, for example `status == "ok"` or `checks.printer.status == "ok"`.

```json
{
  "status": "degraded",
  "time": "2026-09-21T06:41:12+02:00",
  "version": "1.0.0",
  "uptime_seconds": 864211,
  "worker": { "alive": true, "last_heartbeat": "2026-09-21T06:41:02+02:00" },
  "schedule": {
    "next_run": "2026-09-22T06:30:00+02:00",
    "mode": "weekday",
    "hold_mode": true,
    "llm_enabled": true
  },
  "last_edition": {
    "date": "2026-09-21",
    "status": "done_degraded",
    "awaiting_approval": true,
    "finished_at": "2026-09-21T06:33:40+02:00"
  },
  "checks": {
    "caldav":  { "status": "ok",       "last_success": "2026-09-21T06:30:03+02:00", "message": null },
    "rss":     { "status": "degraded", "feeds_ok": 9, "feeds_total": 10, "message": "1 feed failing" },
    "weather": { "status": "ok",       "last_success": "2026-09-21T06:30:05+02:00", "message": null },
    "almanac": { "status": "ok",       "last_success": "2026-09-21T06:30:08+02:00", "message": null },
    "llm":     { "status": "ok",       "requests_today": 2, "daily_limit": 1000, "message": null },
    "dropbox": { "status": "ok",       "last_success": "2026-09-20T06:40:11+02:00", "message": null },
    "printer": { "status": "ok",       "state": "idle", "message": null }
  },
  "system": { "disk_free_mb": 21450, "cpu_temp_c": 48.2, "ntp_synced": true },
  "alerts": [
    { "code": "feed_dead", "severity": "warning", "since": "2026-09-19T06:30:00+02:00" }
  ]
}
```

The `version` value in the example is illustrative. The field itself is required.

## Where the checker runs

The checker is on the LAN, or it can reach the LAN through the operator's VPN. A cloud-hosted monitor cannot see a LAN-only Pi, and a port is not opened to make that work.

Reserve a fixed IP for the Pi on the router. `newspaper.local` may fail to resolve over a VPN or on some Android versions, so the IP is the address that always works.

The dashboard records when `/status` was last requested.

A push-style heartbeat, where the Pi pings an outside service, stays optional and later. It would need internet access to that service, and it is a non-goal for this version.
