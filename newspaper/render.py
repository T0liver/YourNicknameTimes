"""Render the edition template to a one-page A4 PDF."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from newspaper.fixtures import fixture_edition

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
TEMPLATE_NAME = "edition.html.j2"
BASE_URL = f"{PACKAGE_DIR.as_uri()}/"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )


def render_html(edition: dict | None = None) -> str:
    context = dict(edition if edition is not None else fixture_edition())
    context.setdefault("show_sun", True)
    return _environment().get_template(TEMPLATE_NAME).render(context)


def build_document(edition: dict | None = None):
    html = render_html(edition)
    return HTML(string=html, base_url=BASE_URL).render()


def render_edition(out_path: str | Path, edition: dict | None = None) -> float:
    html = render_html(edition)
    started = time.perf_counter()
    HTML(string=html, base_url=BASE_URL).write_pdf(target=str(out_path))
    return time.perf_counter() - started


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render the fixture edition to one A4 PDF.")
    parser.add_argument("--out", required=True, help="Output PDF path")
    args = parser.parse_args(argv)
    seconds = render_edition(args.out)
    print(f"render_seconds={seconds:.3f}")
