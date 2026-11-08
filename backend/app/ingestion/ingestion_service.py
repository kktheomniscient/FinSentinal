"""On-demand ingestion: make sure a ticker's recent 10-Qs are indexed before the agent searches.

Only tickers that are actually asked about (plus the seed list) end up in the vector DB.
"""

from app.observability import traced
import json
import threading
import time
from collections import defaultdict

from app.config import settings
from app.ingestion.filing_loader import load_filing_chunks
from app.ingestion.sec_edgar_client import EdgarClient
from app.ingestion.vector_indexer import default_collection, index_chunks, indexed_accessions

class NoQuarterlyFilings(ValueError):
    """Ticker exists at the SEC but has no 10-Q filings (e.g. foreign private issuers file 20-F / 6-K)."""


_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_state_lock = threading.Lock()


def _load_state() -> dict:
    try:
        return json.loads(settings.state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _mark_checked(ticker: str, seed: bool) -> None:
    with _state_lock:
        state = _load_state()
        entry = state.setdefault(ticker, {})
        entry["checked_at"] = time.time()
        entry["seed"] = entry.get("seed", False) or seed
        settings.state_file.parent.mkdir(parents=True, exist_ok=True)
        settings.state_file.write_text(json.dumps(state, indent=2))


@traced("ingestion.ensure_ticker_indexed")
def ensure_ticker_indexed(
    ticker: str,
    limit: int | None = None,
    force: bool = False,
    seed: bool = False,
    collection=None,
    client: EdgarClient | None = None,
) -> dict:
    """Fetch, parse and index any of ``ticker``'s latest ``limit`` 10-Qs that are not indexed yet.

    Returns ``{"ticker", "source": "cache"|"edgar", "new_filings", "total_filings"}``.
    Raises ``ValueError`` for tickers not found at the SEC. Blocking; run in a threadpool from async code.
    """
    ticker = ticker.strip().upper()
    limit = limit or settings.filings_per_ticker
    collection = collection or default_collection()

    with _locks[ticker]:  # a concurrent query for the same ticker waits, then sees it as cached
        have = indexed_accessions(ticker, collection)
        checked_at = _load_state().get(ticker, {}).get("checked_at", 0)
        fresh = (time.time() - checked_at) < settings.refresh_after_hours * 3600
        if have and fresh and not force:
            return {"ticker": ticker, "source": "cache", "new_filings": 0, "total_filings": len(have)}

        own_client = client is None
        client = client or EdgarClient()
        try:
            filings = client.list_10qs(ticker, limit)  # ValueError if unknown ticker
            if not filings:
                forms = client.recent_forms(ticker)
                other = [f for f in ("20-F", "6-K", "40-F", "10-K") if f in forms]
                hint = (
                    f" It files {', '.join(other)} instead"
                    + (" (typical of a foreign private issuer), which this system does not ingest." if "20-F" in other or "6-K" in other else ".")
                    if other
                    else ""
                )
                raise NoQuarterlyFilings(f"{ticker} has no 10-Q filings on SEC EDGAR.{hint}")
            new = [f for f in filings if f["accession"] not in have]
            for f in new:
                path = client.download_filing(f)
                index_chunks(load_filing_chunks(path), collection)
        finally:
            if own_client:
                client.close()
        _mark_checked(ticker, seed)
        return {
            "ticker": ticker,
            "source": "edgar",
            "new_filings": len(new),
            "total_filings": len(have) + len(new),
        }
