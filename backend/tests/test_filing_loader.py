from app.ingestion.filing_loader import _quarter_from_period, html_to_text, split_sections

HTML = """<html><head><title>x</title></head><body>
<table><tr><td>Item 2.</td><td>MD&amp;A</td><td>5</td></tr></table>
<p>PART I</p><p>Item 1. Financial Statements</p><p>Revenue was $ 100 million.</p>
<table><tr><td>Net income</td><td>$</td><td>20</td><td>)</td></tr></table>
<p>Item 2. Management&#8217;s Discussion</p><p>Margins improved.</p>
<p>PART II</p><p>Item 1A. Risk Factors</p><p>Tariffs may hurt.</p></body></html>"""


def test_sections_and_tables():
    text = html_to_text(HTML)
    assert "Net income | 20" in text
    secs = dict(split_sections(text))
    assert "Part I Item 1 – Financial Statements" in secs
    assert "Margins improved." in secs["Part I Item 2 – Management’s Discussion"]
    assert "Tariffs may hurt." in secs["Part II Item 1A – Risk Factors"]
    assert not any("MD&A | 5" in k for k in secs)  # TOC row is not a heading


def test_quarter():
    assert _quarter_from_period("2026-06-27") == "CQ2"
