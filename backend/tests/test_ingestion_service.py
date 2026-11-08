import json
from pathlib import Path

import pytest

from app.config import settings
from app.ingestion import ingestion_service as svc
from app.ingestion.vector_indexer import indexed_accessions, search

HTML = "<html><body><p>PART I</p><p>Item 2. MD&amp;A</p><p>Revenue grew strongly this quarter.</p></body></html>"


class FakeClient:
    def __init__(self, tmp):
        self.tmp, self.listed, self.downloaded = tmp, 0, []

    def list_10qs(self, ticker, limit):
        self.listed += 1
        if ticker == "NOPE":
            raise ValueError("not found")
        return [
            {"ticker": ticker, "form": "10-Q", "accession": f"0000-00-{i}", "period_end": f"2025-0{i}-30",
             "filing_date": "2025-01-01", "source_url": "http://x", "company": "X", "cik": "1", "primary_document": "a.htm"}
            for i in (3, 6)
        ]

    def download_filing(self, f, dest=None):
        self.downloaded.append(f["accession"])
        p = self.tmp / f"{f['ticker']}_10-Q_{f['period_end']}.htm"
        p.write_text(HTML)
        p.with_suffix(".json").write_text(json.dumps(f))
        return p

    def close(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.ingestion.vector_indexer import get_collection
    monkeypatch.setattr(settings, "state_file", tmp_path / "state.json")
    return tmp_path, get_collection(tmp_path / "chroma", "svc_test"), FakeClient(tmp_path)


def test_on_demand_then_cached(env):
    tmp, col, client = env
    r1 = svc.ensure_ticker_indexed("zzz", collection=col, client=client)
    assert (r1["source"], r1["new_filings"], r1["total_filings"]) == ("edgar", 2, 2)
    assert indexed_accessions("ZZZ", col) == {"0000-00-3", "0000-00-6"}
    assert search("revenue", 1, "zzz", col)[0]["metadata"]["section"].startswith("Part I Item 2")

    r2 = svc.ensure_ticker_indexed("ZZZ", collection=col, client=client)
    assert r2["source"] == "cache" and client.listed == 1  # no second EDGAR call


def test_only_new_filings_downloaded_on_refresh(env):
    tmp, col, client = env
    svc.ensure_ticker_indexed("ZZZ", collection=col, client=client)
    client.downloaded.clear()
    r = svc.ensure_ticker_indexed("ZZZ", collection=col, client=client, force=True)
    assert r["new_filings"] == 0 and client.downloaded == []


def test_unknown_ticker(env):
    tmp, col, client = env
    with pytest.raises(ValueError):
        svc.ensure_ticker_indexed("NOPE", collection=col, client=client)
