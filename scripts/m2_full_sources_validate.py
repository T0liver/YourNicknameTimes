#!/usr/bin/env python3
"""M2-B validation harness for deterministic full-source contract.

Generates normalization artifacts and assertions for:
- deterministic per-source output contracts
- CalDAV recurring/date-only handling
- RSS recency + dedup behavior
- weather/almanac/rates omit-on-failure semantics
- OPML import/export support layer
"""

from __future__ import annotations

import json
from pathlib import Path

from m2_full_sources import (
    build_full_sources_contract,
    rss_export_opml,
    rss_import_opml,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "docs" / "orchestration" / "artifacts" / "m2-b"
FIX = ART / "fixtures"
SNAP = ART / "snapshots"


def _load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _assert_ok_contract(ok_contract: dict):
    assert ok_contract["schema_version"] == "m2.full_sources.v1"
    assert ok_contract["deterministic"] is True

    cal = ok_contract["sources"]["caldav"]
    assert cal["omit"] is False
    assert cal["health"]["status"] == "ok"
    assert len(cal["data"]["events"]) == 2
    # date-only event should be tagged all_day and recurring preserved
    weekend_event = [e for e in cal["data"]["events"] if e["id"] == "evt-2"][0]
    assert weekend_event["all_day"] is True
    assert weekend_event["is_recurring_instance"] is True

    overdue_task = [t for t in cal["data"]["tasks"] if t["id"] == "tsk-1"][0]
    assert overdue_task["bucket"] == "overdue"
    assert overdue_task["overdue_days"] == 1
    assert overdue_task["all_day_due"] is True
    anytime_task = [t for t in cal["data"]["tasks"] if t["id"] == "tsk-3"][0]
    assert anytime_task["bucket"] == "anytime"
    assert anytime_task["due"] is None

    rss = ok_contract["sources"]["rss"]
    assert rss["omit"] is False
    assert rss["health"]["status"] == "ok"
    # duplicate URL + old + missing published should leave exactly 2
    assert len(rss["data"]["items"]) == 2
    urls = {x["url"] for x in rss["data"]["items"]}
    assert "https://example.com/local/bikepath" in urls
    assert "https://example.com/tech/meetup" in urls

    weather = ok_contract["sources"]["weather"]
    assert weather["omit"] is False
    assert weather["data"]["today"]["high_c"] == 22.0

    almanac = ok_contract["sources"]["almanac"]
    assert almanac["omit"] is False
    assert len(almanac["data"]["on_this_day"]) == 2

    rates = ok_contract["sources"]["rates"]
    assert rates["omit"] is False
    assert rates["data"]["published_date"] == "2026-09-23"
    assert rates["data"]["values"]["EUR_HUF"] == 398.12


def _assert_failure_contract(f_contract: dict):
    cal = f_contract["sources"]["caldav"]
    assert cal["omit"] is False
    assert cal["health"]["status"] == "ok"

    for source in ("rss", "weather", "almanac", "rates"):
        node = f_contract["sources"][source]
        assert node["omit"] is True
        assert node["data"] is None
        assert node["health"]["status"] == "degraded"
        assert node["health"]["message"]


def _validate_opml_roundtrip():
    feeds = _load(FIX / "rss_feeds_config.json")
    opml = rss_export_opml(feeds)
    imported = rss_import_opml(opml)
    _dump(SNAP / "rss-feeds.opml.json", {"opml": opml, "imported": imported})

    assert len(imported) == 2
    by_name = {x["name"]: x for x in imported}
    assert by_name["Hírek"]["category"] == "local"
    assert by_name["Tech"]["language"] == "en"
    assert by_name["Tech"]["enabled"] is True


def main() -> int:
    ok_bundle = _load(FIX / "full_sources_bundle_ok.json")
    fail_bundle = _load(FIX / "full_sources_bundle_failures.json")

    ok_contract = build_full_sources_contract(ok_bundle)
    fail_contract = build_full_sources_contract(fail_bundle)

    _assert_ok_contract(ok_contract)
    _assert_failure_contract(fail_contract)
    _validate_opml_roundtrip()

    _dump(SNAP / "full-sources-ok.json", ok_contract)
    _dump(SNAP / "full-sources-failures.json", fail_contract)

    report = {
        "status": "ok",
        "task_id": "M2-B-FULL-SOURCES",
        "checks": {
            "deterministic_contract_per_source": True,
            "caldav_recurring_date_handling": True,
            "rss_recency_dedup": True,
            "omit_on_failure_weather_almanac_rates_rss": True,
            "rss_opml_import_export": True,
        },
        "snapshots": [
            str(SNAP / "full-sources-ok.json"),
            str(SNAP / "full-sources-failures.json"),
            str(SNAP / "rss-feeds.opml.json"),
        ],
    }
    _dump(ART / "validation-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())