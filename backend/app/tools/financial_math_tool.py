"""Deterministic financial arithmetic. All results use Decimal and are rounded explicitly,
so the LLM never performs arithmetic itself."""

from decimal import Decimal, InvalidOperation

Number = int | float | str | Decimal


def _d(x: Number, name: str) -> Decimal:
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be numeric, got {x!r}") from None


def _round(x: Decimal, places: int) -> float:
    return float(round(x, places))


def debt_to_equity(total_debt: Number, total_equity: Number, places: int = 2) -> float:
    debt, equity = _d(total_debt, "total_debt"), _d(total_equity, "total_equity")
    if equity == 0:
        raise ValueError("total_equity is zero; Debt/Equity undefined")
    return _round(debt / equity, places)


def net_margin(net_income: Number, revenue: Number, places: int = 2) -> float:
    """Net margin in percent."""
    ni, rev = _d(net_income, "net_income"), _d(revenue, "revenue")
    if rev == 0:
        raise ValueError("revenue is zero; net margin undefined")
    return _round(ni / rev * 100, places)


def yoy_growth(current: Number, previous: Number, places: int = 2) -> float:
    """Year-over-year growth in percent. Uses |previous| so growth from a loss is signed sensibly."""
    cur, prev = _d(current, "current"), _d(previous, "previous")
    if prev == 0:
        raise ValueError("previous is zero; growth undefined")
    return _round((cur - prev) / abs(prev) * 100, places)


def yoy_net_margin_growth(
    net_income_current: Number,
    revenue_current: Number,
    net_income_previous: Number,
    revenue_previous: Number,
    places: int = 2,
) -> dict:
    """Net margins for both periods, the change in percentage points, and relative growth."""
    cur = net_margin(net_income_current, revenue_current, 6)
    prev = net_margin(net_income_previous, revenue_previous, 6)
    return {
        "net_margin_current_pct": round(cur, places),
        "net_margin_previous_pct": round(prev, places),
        "change_pp": round(cur - prev, places),
        "relative_growth_pct": yoy_growth(cur, prev, places),
    }


def pct_change_from_52w_high(price: Number, week52_high: Number, places: int = 2) -> float:
    return yoy_growth(price, week52_high, places)
