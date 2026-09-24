#!/usr/bin/env python3
"""M1-C layout bootstrap: deterministic fake-HU edition snapshot composer.

Scope: static composition bootstrap only (no live integrations).
Produces render-facing snapshot payloads for Agent D A4 validation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Masthead:
    nickname: str
    motto: str
    city: str



def _build_title(nickname: str) -> str:
    nickname = (nickname or "Your Nickname").strip()
    return f"{nickname} Times"



def _is_weekend(date_iso: str) -> bool:
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    return dt.weekday() >= 5



def compose_snapshot(source: dict[str, Any]) -> dict[str, Any]:
    date_iso = source["date"]
    weekend_by_calendar = _is_weekend(date_iso)

    masthead_input = source["masthead"]
    nickname = masthead_input.get("nickname", "Your Nickname")
    motto_raw = masthead_input.get("motto", "")
    motto = motto_raw.strip()

    weekend_cfg = source.get("weekend", {})
    weekend_enabled = bool(weekend_cfg.get("enabled", False))
    weekend_active = weekend_enabled and weekend_by_calendar

    show_weekend_icon = bool(weekend_cfg.get("show_sun_icon", False)) and weekend_active
    greeting_text = (weekend_cfg.get("greeting") or "").strip()
    show_weekend_greeting = bool(greeting_text) and weekend_active

    snapshot = {
        "schema_version": "m1.layout.bootstrap.v1",
        "edition": {
            "date": date_iso,
            "locale": "hu-HU",
            "mode": "weekend" if weekend_active else "weekday",
            "deterministic": True,
            "data_profile": "fake_hu_m1",
        },
        "masthead": {
            "title": _build_title(nickname),
            "motto": motto,
            "show_motto": bool(motto),
            "motto_collapsed": not bool(motto),
            "city": masthead_input.get("city", "Budapest"),
            "dateline": source.get("dateline", "Vol. 1 · AS OF 06:30"),
            "weekend_sun_icon": show_weekend_icon,
            "weekend_greeting": greeting_text if show_weekend_greeting else "",
            "show_weekend_greeting": show_weekend_greeting,
        },
        "sections": source.get("sections", {}),
        "render_contract": {
            "page_size": "A4",
            "target_pages": 1,
            "glyph_probe": "ŐőŰű",
            "required_milestone_gate": "M1",
            "inputs": {
                "title_source": "nickname + ' Times'",
                "motto_empty_collapses": True,
                "weekend_toggle_drives_icon_and_greeting": True,
            },
        },
        "metadata": {
            "owner": "agent-c-edition-engine",
            "task_id": "M1-C-LAYOUT-BOOTSTRAP",
            "handoff_target": "M1-D-A4-RENDER",
        },
    }

    return snapshot



def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose deterministic M1 layout snapshot")
    parser.add_argument("--input", required=True, help="Input fixture JSON")
    parser.add_argument("--output", required=True, help="Output snapshot JSON")
    return parser.parse_args()



def main() -> int:
    args = _parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        source = json.load(f)

    snapshot = compose_snapshot(source)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
