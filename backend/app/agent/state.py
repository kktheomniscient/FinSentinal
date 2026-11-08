import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    ticker: str | None            # may be supplied by the UI; otherwise resolved by the router
    plan: dict[str, Any]          # router output: needs_docs, needs_market, calculation
    chunks: list[dict]            # retrieved passages (text + metadata)
    market: dict | None           # yfinance snapshot
    calcs: list[dict]             # deterministic calculation results + grounded inputs
    notes: Annotated[list[str], operator.add]  # limitations the memo must state (e.g. no 10-Qs for this ticker)
    memo: str
    citations: list[dict]
    verification: dict
    error: str | None
    trace: Annotated[list[dict], operator.add]   # step log for the UI's execution badges
