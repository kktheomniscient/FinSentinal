"""Parse SEC 10-Q HTML into section-aware chunks with citation metadata.

Metadata comes from the ``.json`` sidecar written by the EDGAR client when present, otherwise
from the filename ``{TICKER}_10-Q_{YYYY-MM-DD}.htm``.
"""

import json
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

FILENAME_RE = re.compile(r"^(?P<ticker>[A-Za-z0-9-]+)_10-Q_(?P<period>\d{4}-\d{2}-\d{2})$")
PART_RE = re.compile(r"^PART\s+(I{1,2})\b", re.I)
ITEM_RE = re.compile(r"^ITEM\s+(\d+[A-C]?)\s*[\.\-–—:]?\s*(.*)$", re.I)


def html_to_text(html: str | bytes) -> str:
    """Flatten a filing to text: one line per block element, tables as ' | ' joined rows."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)  # inline-XBRL filings are XHTML
        soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for tag in soup.find_all(re.compile(r"^ix:header$", re.I)):  # hidden inline-XBRL metadata
        tag.decompose()
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c and c not in ("$", ")", "%")]
        tr.replace_with(soup.new_string(" | ".join(cells) + "\n"))
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split into ``(section_label, text)`` using 'Part X' / 'Item N' heading lines."""
    part, section = "", "Preamble"
    buf: list[str] = []
    out: list[tuple[str, str]] = []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            out.append((section, body))
        buf.clear()

    for line in text.splitlines():
        if len(line) < 120 and " | " not in line:  # headings are short, and TOC table rows contain ' | '
            if m := PART_RE.match(line):
                flush()
                part = f"Part {m.group(1).upper()}"
                section = part
            elif m := ITEM_RE.match(line):
                flush()
                label = f"Item {m.group(1).upper()}"
                if m.group(2):
                    label += f" – {m.group(2).strip().rstrip('.')[:60]}"
                section = f"{part} {label}".strip()
        buf.append(line)
    flush()
    return out


def _quarter_from_period(period_end: str) -> str:
    """Calendar quarter of the period end. Fiscal quarters differ for non-calendar FYs (e.g. AAPL)."""
    return f"CQ{(int(period_end[5:7]) - 1) // 3 + 1}"


def load_filing_metadata(path: Path) -> dict:
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        f = json.loads(sidecar.read_text())
        return {
            "ticker": f["ticker"],
            "form": f["form"],
            "period_end": f["period_end"],
            "filing_date": f["filing_date"],
            "accession": f["accession"],
            "source_url": f["source_url"],
        }
    m = FILENAME_RE.match(path.stem)
    if not m:
        raise ValueError(f"{path.name}: expected {{TICKER}}_10-Q_{{YYYY-MM-DD}}.htm or a .json sidecar")
    return {"ticker": m["ticker"].upper(), "form": "10-Q", "period_end": m["period"]}


def load_filing_chunks(path: Path, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[dict]:
    """Return ``[{"id", "text", "metadata"}]`` for one 10-Q HTML file."""
    meta = load_filing_metadata(path)
    meta["year"] = meta["period_end"][:4]
    meta["quarter"] = _quarter_from_period(meta["period_end"])
    meta["source"] = path.name
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
    )
    text = html_to_text(path.read_bytes())
    chunks: list[dict] = []
    for section, body in split_sections(text):
        for piece in splitter.split_text(body):
            chunks.append(
                {
                    "id": f"{path.stem}_{len(chunks)}",
                    "text": piece,
                    "metadata": {**meta, "section": section},
                }
            )
    return chunks


def load_directory(directory: Path | None = None) -> list[dict]:
    directory = directory or settings.raw_filings_dir
    chunks: list[dict] = []
    for f in sorted([*directory.glob("*.htm"), *directory.glob("*.html")]):
        chunks.extend(load_filing_chunks(f))
    return chunks
