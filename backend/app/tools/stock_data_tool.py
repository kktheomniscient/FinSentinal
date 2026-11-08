"""Live market data via yfinance. Returns plain dicts; missing fields are None."""

from app.observability import traced
import yfinance as yf


def normalize_symbol(ticker: str) -> str:
    """US tickers need no suffix. 'brk.b' -> 'BRK-B' (Yahoo uses dashes for share classes)."""
    return ticker.strip().upper().replace(".", "-")


@traced("yfinance.get_stock_data")
def get_stock_data(ticker: str) -> dict:
    symbol = normalize_symbol(ticker)
    t = yf.Ticker(symbol)
    info = t.info or {}
    fast = t.fast_info

    def pick(*keys):
        for k in keys:
            if info.get(k) is not None:
                return info[k]
        return None

    price = pick("currentPrice", "regularMarketPrice")
    if price is None:
        try:
            price = fast["last_price"]
        except Exception:
            price = None
    low = pick("fiftyTwoWeekLow")
    high = pick("fiftyTwoWeekHigh")
    if low is None or high is None:
        try:
            low, high = fast["year_low"], fast["year_high"]
        except Exception:
            pass

    data = {
        "symbol": symbol,
        "name": pick("longName", "shortName"),
        "currency": pick("currency"),
        "price": price,
        "pe_trailing": pick("trailingPE"),
        "pe_forward": pick("forwardPE"),
        "week52_low": low,
        "week52_high": high,
        "volume": pick("volume", "regularMarketVolume"),
        "avg_volume": pick("averageVolume"),
        "market_cap": pick("marketCap"),
    }
    if data["price"] is None and data["name"] is None:
        raise ValueError(f"No market data found for {symbol}")
    return data
