import pytest

from newspaper.fixtures import edition_with, fixture_edition
from newspaper.render import build_document, main, render_edition, render_html

A4_WIDTH_PX = 210 * 96 / 25.4
A4_HEIGHT_PX = 297 * 96 / 25.4
HYPHEN_MARKS = ("-", "\u00ad", "\u2010")
FIXTURE_HEADLINE = "Megszentségteleníthetetlenségeskedéseitekért"


def _iter_boxes(box):
    yield box
    for child in getattr(box, "children", None) or ():
        yield from _iter_boxes(child)


def page_text_runs(page) -> list[str]:
    root = getattr(page, "_page_box", None)
    if root is None:
        return []
    runs = []
    for box in _iter_boxes(root):
        text = getattr(box, "text", None)
        if text:
            runs.append(text)
    return runs


def test_fixture_pdf_is_one_a4_page(tmp_path):
    out = tmp_path / "edition.pdf"
    render_edition(out)
    document = build_document()
    assert out.is_file()
    assert len(document.pages) == 1
    page = document.pages[0]
    assert page.width == pytest.approx(A4_WIDTH_PX, abs=1)
    assert page.height == pytest.approx(A4_HEIGHT_PX, abs=1)


def test_fixture_page_has_hungarian_glyphs_and_quotes():
    page = build_document().pages[0]
    text = "".join(page_text_runs(page))
    assert "Győző" in text
    assert "ő" in text
    assert "ű" in text
    assert "„" in text
    assert "”" in text


def test_fixture_news_headline_hyphenates():
    runs = page_text_runs(build_document().pages[0])
    joined = "".join(runs)
    stripped = joined.replace("-", "").replace("\u00ad", "").replace("\u2010", "")
    assert FIXTURE_HEADLINE in stripped
    hyphenated = any(
        any(mark in run for mark in HYPHEN_MARKS)
        and FIXTURE_HEADLINE.startswith(run.replace("\u00ad", "").rstrip("-").rstrip("\u2010"))
        for run in runs
        if run.strip()
    )
    assert hyphenated, runs


def test_empty_motto_omits_motto_node():
    html = render_html(fixture_edition())
    assert 'class="motto"' not in html
    masthead_start = html.index('<header class="masthead">')
    nameplate_start = html.index('<div class="nameplate">')
    between = html[masthead_start:nameplate_start]
    assert "motto" not in between


def test_weekend_fixture_includes_sun_icon():
    html = render_html(fixture_edition())
    assert 'class="weekend-sun"' in html
    assert "weekend-sun.svg" in html
    weekday = render_html(edition_with(weekend=False))
    assert "weekend-sun" not in weekday


def test_weasyprint_errors_are_not_swallowed(monkeypatch, tmp_path):
    def boom(self, target=None, **kwargs):
        raise RuntimeError("Pango/HarfBuzz/GDK-Pixbuf absent")

    monkeypatch.setattr("newspaper.render.HTML.write_pdf", boom)
    with pytest.raises(RuntimeError, match="Pango/HarfBuzz/GDK-Pixbuf"):
        render_edition(tmp_path / "fail.pdf")


def test_cli_prints_render_seconds(tmp_path, capsys):
    out = tmp_path / "edition.pdf"
    main(["--out", str(out)])
    captured = capsys.readouterr().out
    assert out.is_file()
    assert "render_seconds=" in captured
