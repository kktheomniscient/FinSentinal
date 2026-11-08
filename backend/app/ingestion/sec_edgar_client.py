"""Minimal SEC EDGAR client: ticker -> CIK, list 10-Q filings, download primary documents.

SEC fair-access policy: descriptive User-Agent required, <=10 requests/second.
"""

import argparse
import json
import re
import threading
import time
from pathlib import Path

import httpx

from app.config import settings

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"


class EdgarClient:
    def __init__(self, user_agent: str | None = None, max_rps: float | None = None):
        self._client = httpx.Client(
            headers={"User-Agent": user_agent or settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=30,
            follow_redirects=True,
        )
        self._min_interval = 1.0 / (max_rps or settings.sec_max_rps)
        self._last = 0.0
        self._lock = threading.Lock()
        self._tickers: dict | None = None

    def _get(self, url: str, retries: int = 3) -> httpx.Response:
        for attempt in range(retries):
            with self._lock:
                wait = self._min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            resp = self._client.get(url)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    def get_cik(self, ticker: str) -> str:
        """Return zero-padded 10-digit CIK."""
        if self._tickers is None:
            self._tickers = {v["ticker"].upper(): v for v in self._get(TICKERS_URL).json().values()}
        entry = self._tickers.get(ticker.upper().replace("-", "."))
        entry = entry or self._tickers.get(ticker.upper())
        if not entry:
            raise ValueError(f"Ticker {ticker!r} not found in SEC company_tickers.json")
        return f"{int(entry['cik_str']):010d}"

    def list_10qs(self, ticker: str, limit: int = 4) -> list[dict]:
        """Most recent 10-Q filings (newest first). Older filings beyond the 'recent' block are not paged."""
        cik = self.get_cik(ticker)
        data = self._get(SUBMISSIONS_URL.format(cik=cik)).json()
        recent = data["filings"]["recent"]
        out = []
        for i, form in enumerate(recent["form"]):
            if form != "10-Q":
                continue
            acc = recent["accessionNumber"][i]
            doc = recent["primaryDocument"][i]
            out.append(
                {
                    "ticker": ticker.upper(),
                    "company": data.get("name"),
                    "cik": cik,
                    "form": form,
                    "accession": acc,
                    "filing_date": recent["filingDate"][i],
                    "period_end": recent["reportDate"][i],
                    "primary_document": doc,
                    "source_url": ARCHIVE_URL.format(
                        cik_int=int(cik), acc_nodash=acc.replace("-", ""), doc=doc
                    ),
                }
            )
            if len(out) >= limit:
                break
        return out

    def recent_forms(self, ticker: str) -> dict[str, int]:
        """Count of form types in the company's recent EDGAR filings (e.g. {'20-F': 4, '6-K': 27})."""
        from collections import Counter

        data = self._get(SUBMISSIONS_URL.format(cik=self.get_cik(ticker))).json()
        return dict(Counter(data["filings"]["recent"]["form"]))

    def download_filing(self, f: dict, dest: Path | None = None) -> Path:
        """Save one filing (a dict from ``list_10qs``) as ``{TICKER}_10-Q_{period_end}.htm`` + ``.json`` sidecar."""
        dest = dest or settings.raw_filings_dir
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{f['ticker']}_10-Q_{f['period_end']}.htm"
        if not path.exists():
            path.write_bytes(self._get(f["source_url"]).content)
        path.with_suffix(".json").write_text(json.dumps(f, indent=2))
        return path

    def download_10qs(self, ticker: str, limit: int = 4, dest: Path | None = None) -> list[Path]:
        return [self.download_filing(f, dest) for f in self.list_10qs(ticker, limit)]

    def close(self):
        self._client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Download recent 10-Qs from SEC EDGAR")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()
    c = EdgarClient()
    for t in args.tickers:
        for p in c.download_10qs(t, args.limit):
            print("saved", p)
    c.close()
