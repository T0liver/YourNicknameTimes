#!/usr/bin/env python3
"""M1-D A4 render validation runner.

Renders Agent C snapshot artifacts to A4 PDFs with WeasyPrint and writes an
evidence report that covers M1 gate checks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Template
from pypdf import PdfReader
from weasyprint import HTML


HTML_TEMPLATE = """<!doctype html>
<html lang="hu">
  <head>
    <meta charset="utf-8" />
    <title>{{ masthead.title }}</title>
    <style>
      @page { size: A4; margin: 0; }
      :root {
        --paper-w: 8.27in;
        --paper-h: 11.69in;
        --content-m: 0.32in;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        width: var(--paper-w);
        min-height: var(--paper-h);
        font-family: "Newsreader", "Libre Franklin", "Noto Serif", serif;
        color: #111;
      }
      .page {
        width: 100%;
        min-height: var(--paper-h);
        padding: var(--content-m);
      }
      .masthead {
        border-bottom: 1px solid #333;
        padding-bottom: 0.10in;
        margin-bottom: 0.12in;
      }
      .title {
        font-family: "Chomsky", "Newsreader", "Noto Serif", serif;
        font-size: 34pt;
        line-height: 1.0;
        margin: 0;
      }
      .motto {
        font-size: 10pt;
        margin-top: 0.03in;
      }
      .motto.collapsed {
        display: none;
      }
      .dateline {
        margin-top: 0.04in;
        font-size: 10pt;
      }
      .weekend {
        margin-top: 0.04in;
        font-size: 10pt;
      }
      .glyph-probe {
        margin-top: 0.05in;
        font-size: 13pt;
        font-family: "Chomsky", "Libre Franklin", "Newsreader", "Noto Serif", serif;
      }
      .section {
        margin-top: 0.10in;
      }
      .section h2 {
        margin: 0 0 0.04in 0;
        font-size: 13pt;
      }
      .item {
        font-size: 10pt;
        margin-bottom: 0.03in;
      }
      .meta {
        color: #444;
      }
    </style>
  </head>
  <body>
    <main class="page">
      <header class="masthead">
        <h1 class="title">{{ masthead.title }}</h1>
        <div class="motto {% if not masthead.show_motto %}collapsed{% endif %}">{{ masthead.motto }}</div>
        <div class="dateline">{{ masthead.dateline }}</div>
        <div class="weekend">
          {% if masthead.weekend_sun_icon %}☀ {% endif %}
          {% if masthead.show_weekend_greeting %}{{ masthead.weekend_greeting }}{% endif %}
        </div>
        <div class="glyph-probe">{{ render_contract.glyph_probe }}</div>
      </header>

      {% if sections.news %}
      <section class="section">
        <h2>Hírek</h2>
        {% for row in sections.news %}
          <div class="item">{{ row.headline }} <span class="meta">— {{ row.publisher }}</span></div>
        {% endfor %}
      </section>
      {% endif %}

      {% if sections.today %}
      <section class="section">
        <h2>Ma</h2>
        {% for row in sections.today %}
          <div class="item">{{ row.time }} · {{ row.title }}</div>
        {% endfor %}
      </section>
      {% endif %}

      {% if sections.almanac %}
      <section class="section">
        <h2>Almanach</h2>
        <div class="item">Napkelte: {{ sections.almanac.sunrise }}, Napnyugta: {{ sections.almanac.sunset }}</div>
        <div class="item">Névnap: {{ sections.almanac.name_day }}</div>
      </section>
      {% endif %}
    </main>
  </body>
</html>
"""


@dataclass(frozen=True)
class VariantResult:
    name: str
    output_dir: str
    render_seconds: float
    print_pdf: str
    cloud_pdf: str
    print_page_count: int
    cloud_page_count: int
    a4_points: tuple[float, float]
    extracted_text: str
    checks: dict[str, bool]
    printer_submission: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render M1 snapshots to A4 PDFs and validate evidence")
    parser.add_argument(
        "--snapshot",
        action="append",
        required=True,
        help="Path to snapshot JSON (repeatable)",
    )
    parser.add_argument(
        "--out-root",
        default="docs/orchestration/artifacts/m1-d-renders",
        help="Output root directory",
    )
    parser.add_argument(
        "--printer",
        default="",
        help="Optional printer name for lp test submission (e.g. newspaper-printer)",
    )
    parser.add_argument(
        "--print-test",
        action="store_true",
        help="If set, submit print.pdf to CUPS using lp",
    )
    parser.add_argument(
        "--report",
        default="docs/orchestration/artifacts/m1-d-renders/verification-report.json",
        help="Path for final JSON report",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def _page_size_points(pdf_path: Path) -> tuple[float, float]:
    reader = PdfReader(str(pdf_path))
    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)
    return (w, h)


def _is_a4_points(size: tuple[float, float], tolerance: float = 2.0) -> bool:
    # A4 in PostScript points: 595.2756 x 841.8898
    targets = ((595.28, 841.89), (841.89, 595.28))
    for tw, th in targets:
        if abs(size[0] - tw) <= tolerance and abs(size[1] - th) <= tolerance:
            return True
    return False


def _cloud_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(snapshot))
    sections = cloned.get("sections", {})
    if isinstance(sections, dict):
        today = sections.get("today")
        if isinstance(today, list):
            for row in today:
                if isinstance(row, dict):
                    # Minimal privacy trim hook for M1 evidence path.
                    row.pop("location", None)
                    row.pop("attendees", None)
    return cloned


def _render_pdf(snapshot: dict[str, Any], out_path: Path) -> tuple[float, str]:
    template = Template(HTML_TEMPLATE)
    html_text = template.render(
        masthead=snapshot.get("masthead", {}),
        sections=snapshot.get("sections", {}),
        render_contract=snapshot.get("render_contract", {}),
    )
    start = time.perf_counter()
    HTML(string=html_text).write_pdf(str(out_path))
    elapsed = time.perf_counter() - start
    return elapsed, html_text


def _submit_print(printer: str, pdf_path: Path) -> dict[str, Any]:
    if not printer:
        return {"attempted": False, "reason": "printer_not_provided"}

    cmd = [
        "lp",
        "-d",
        printer,
        "-o",
        "media=A4",
        "-o",
        "ColorModel=Gray",
        "-o",
        "fit-to-page",
        str(pdf_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {"attempted": False, "reason": "lp_not_found"}

    return {
        "attempted": True,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "ok": proc.returncode == 0,
    }


def _run_variant(snapshot_path: Path, out_root: Path, printer: str, print_test: bool) -> VariantResult:
    snapshot = _load_json(snapshot_path)
    name = snapshot_path.stem
    variant_dir = out_root / name
    variant_dir.mkdir(parents=True, exist_ok=True)

    print_pdf = variant_dir / "print.pdf"
    cloud_pdf = variant_dir / "cloud.pdf"
    render_html_path = variant_dir / "rendered.html"

    render_seconds, html_text = _render_pdf(snapshot, print_pdf)
    cloud_seconds, cloud_html = _render_pdf(_cloud_snapshot(snapshot), cloud_pdf)
    render_html_path.write_text(html_text, encoding="utf-8")
    (variant_dir / "rendered-cloud.html").write_text(cloud_html, encoding="utf-8")

    print_reader = PdfReader(str(print_pdf))
    cloud_reader = PdfReader(str(cloud_pdf))
    print_pages = len(print_reader.pages)
    cloud_pages = len(cloud_reader.pages)
    size = _page_size_points(print_pdf)
    text = _extract_text(print_pdf)

    masthead = snapshot.get("masthead", {})
    contract = snapshot.get("render_contract", {})
    glyph_probe = str(contract.get("glyph_probe", ""))
    title = str(masthead.get("title", ""))
    show_motto = bool(masthead.get("show_motto", False))
    motto = str(masthead.get("motto", ""))
    show_weekend_greeting = bool(masthead.get("show_weekend_greeting", False))
    weekend_greeting = str(masthead.get("weekend_greeting", ""))

    checks = {
        "one_page_print": print_pages == 1,
        "one_page_cloud": cloud_pages == 1,
        "a4_size": _is_a4_points(size),
        "title_present": title in text,
        "glyph_probe_present": glyph_probe in text,
        "motto_present_when_expected": (not show_motto) or (motto in text),
        "motto_absent_when_collapsed": show_motto or (motto == ""),
        "weekend_greeting_present_when_expected": (not show_weekend_greeting) or (weekend_greeting in text),
    }

    printer_submission = {"attempted": False, "reason": "print_test_disabled"}
    if print_test:
        printer_submission = _submit_print(printer=printer, pdf_path=print_pdf)

    return VariantResult(
        name=name,
        output_dir=str(variant_dir),
        render_seconds=render_seconds + cloud_seconds,
        print_pdf=str(print_pdf),
        cloud_pdf=str(cloud_pdf),
        print_page_count=print_pages,
        cloud_page_count=cloud_pages,
        a4_points=size,
        extracted_text=text,
        checks=checks,
        printer_submission=printer_submission,
    )


def main() -> int:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[VariantResult] = []
    for snapshot in args.snapshot:
        result = _run_variant(
            snapshot_path=Path(snapshot),
            out_root=out_root,
            printer=args.printer,
            print_test=args.print_test,
        )
        results.append(result)

    all_checks: dict[str, bool] = {}
    for r in results:
        for key, value in r.checks.items():
            all_checks[f"{r.name}:{key}"] = value

    report = {
        "status": "ok" if all(all_checks.values()) else "degraded",
        "task_id": "M1-D-A4-RENDER",
        "out_root": str(out_root),
        "variants": [
            {
                "name": r.name,
                "output_dir": r.output_dir,
                "render_seconds": r.render_seconds,
                "print_pdf": r.print_pdf,
                "cloud_pdf": r.cloud_pdf,
                "print_page_count": r.print_page_count,
                "cloud_page_count": r.cloud_page_count,
                "a4_points": list(r.a4_points),
                "checks": r.checks,
                "printer_submission": r.printer_submission,
            }
            for r in results
        ],
        "summary": {
            "all_checks_passed": all(all_checks.values()),
            "total_render_seconds": sum(r.render_seconds for r in results),
        },
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["all_checks_passed"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
