"""Pre-seed the vector DB with large, frequently queried companies.

Usage: python -m app.ingestion.seed_universe [TICKER ...]   (defaults to settings.seed_tickers)
"""

import sys

from app.config import settings
from app.ingestion.ingestion_service import ensure_ticker_indexed
from app.ingestion.sec_edgar_client import EdgarClient


def main(tickers: list[str]) -> None:
    client = EdgarClient()
    for t in tickers:
        try:
            r = ensure_ticker_indexed(t, seed=True, client=client)
            print(f"{r['ticker']}: {r['source']}, +{r['new_filings']} new, {r['total_filings']} total")
        except Exception as e:  # keep seeding the rest
            print(f"{t}: FAILED – {e}")
    client.close()


if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]] or settings.seed_tickers)
