"""LangGraph nodes: router -> retriever -> market -> calc -> synthesizer -> verifier."""

import inspect
import json
import re
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import prompts
from app.agent.llm import get_llm, get_memo_llm, memo_uses_openrouter
from app.agent.state import AgentState
from app.config import settings
from app.ingestion.ingestion_service import NoQuarterlyFilings, ensure_ticker_indexed
from app.ingestion.vector_indexer import indexed_periods, latest_period, search
from app.tools import financial_math_tool as fm
from app.tools.stock_data_tool import get_stock_data

CALC_TOOLS = {
    "debt_to_equity": fm.debt_to_equity,
    "net_margin": fm.net_margin,
    "yoy_growth": fm.yoy_growth,
    "yoy_net_margin_growth": fm.yoy_net_margin_growth,
}
MARKET_WORDS = re.compile(r"\b(price|p/e|pe ratio|52[- ]week|volume|market cap|trading at|valuation multiple|live|current(ly)? trad)", re.I)
LATEST_WORDS = re.compile(r"\b(latest|most recent|current|last quarter|this quarter|newest)\b", re.I)
FIN_WORDS = re.compile(r"\b(revenues?|net sales|sales|net income|earnings|profit|margin|growth|eps)\b", re.I)
BALANCE_WORDS = re.compile(r"\b(debt|equity|liabilit\w+|assets?|leverage|balance sheet)\b", re.I)
DATE_RE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})", re.I)
# Keyword fallbacks so a requested metric is never dropped when the router LLM misses it
CALC_KEYWORDS = [
    ("net_margin", re.compile(r"net (profit )?margin", re.I)),
    ("yoy_growth", re.compile(r"(revenue|sales|income|earnings)\s+growth|year[- ]over[- ]year|\byoy\b", re.I)),
    ("debt_to_equity", re.compile(r"debt[- /]to[- /]equity|\bd/e\b", re.I)),
]
# Searches phrased like the statement tables they should hit (semantic search alone often misses them)
CALC_QUERIES = {
    "debt_to_equity": "BALANCE SHEETS (In millions) Total liabilities Long-term debt Current portion of long-term debt Total stockholders' equity Total liabilities and stockholders' equity",
    "net_margin": "INCOME STATEMENTS (In millions, except per share amounts) Three Months Ended Revenue Total revenue Total cost of revenue Gross margin Operating income Net income",
    "yoy_growth": "INCOME STATEMENTS (In millions, except per share amounts) Three Months Ended Revenue Total revenue Gross margin Operating income Net income",
    "yoy_net_margin_growth": "INCOME STATEMENTS (In millions, except per share amounts) Three Months Ended Revenue Total revenue Gross margin Operating income Net income",
}
INCOME_Q = CALC_QUERIES["net_margin"]
BALANCE_Q = CALC_QUERIES["debt_to_equity"]


def _step(node: str, detail: str, **extra) -> dict:
    return {"node": node, "detail": detail, **extra}


def _emit(event: dict) -> None:
    """Send a live event to the streaming client (no-op outside streaming)."""
    try:
        from langgraph.config import get_stream_writer

        get_stream_writer()(event)
    except Exception:
        pass


def parse_json(text: str) -> dict | None:
    """Pull the first JSON object out of an LLM reply (tolerates code fences / stray prose)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- router
def router_node(state: AgentState) -> dict:
    query = state["query"]
    plan = None
    try:
        resp = get_llm(thinking=False, max_tokens=200).invoke(
            [SystemMessage(prompts.ROUTER_SYSTEM), HumanMessage(query)], config={"run_name": "router-llm"}
        )
        plan = parse_json(resp.content)
    except Exception as e:  # LLM down -> fall back to heuristics rather than failing the request
        _emit({"event": "warning", "detail": f"router LLM failed: {e}"})
    fallback = plan is None
    plan = plan or {}

    ticker = state.get("ticker") or plan.get("ticker")
    ticker = ticker.strip().upper().replace("$", "") if isinstance(ticker, str) and ticker.strip() else None
    needs_market = bool(plan["needs_market"]) if "needs_market" in plan else bool(MARKET_WORDS.search(query))
    needs_docs = bool(plan["needs_docs"]) if "needs_docs" in plan else True

    raw = plan.get("calculations", plan.get("calculation") or [])
    raw = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    calcs = [c for c in dict.fromkeys(raw) if c in CALC_TOOLS]
    for name, rx in CALC_KEYWORDS:  # never drop a metric the user named
        if rx.search(query) and name not in calcs:
            calcs.append(name)
    calcs = calcs[:3]

    # Anything about results/balance sheet needs the filings, whatever the LLM said
    if calcs or FIN_WORDS.search(query) or BALANCE_WORDS.search(query):
        needs_docs = True
    if not needs_docs and not needs_market:
        needs_docs = True

    out_plan = {"ticker": ticker, "needs_docs": needs_docs, "needs_market": needs_market, "calculations": calcs}
    update: dict = {
        "ticker": ticker,
        "plan": out_plan,
        "trace": [_step("router", f"ticker={ticker} docs={needs_docs} market={needs_market} calcs={calcs or 'none'}"
                        + (" (heuristic fallback)" if fallback else ""), plan=out_plan)],
    }
    if not ticker:
        update["error"] = "Could not identify a US ticker in the question. Please specify a company or ticker."
    return update


# ------------------------------------------------------------- retriever
def named_period(query: str, ticker: str) -> str | None:
    """If the question names a period end date that we have indexed (e.g. 'quarter ended June 27, 2026')."""
    for mon, day, year in DATE_RE.findall(query):
        iso = datetime.strptime(f"{mon.title()} {day} {year}", "%B %d %Y").date().isoformat()
        if iso in indexed_periods(ticker):
            return iso
    return None


def retriever_node(state: AgentState) -> dict:
    ticker, query, plan = state["ticker"], state["query"], state["plan"]
    _emit({"event": "ingesting", "ticker": ticker})
    try:
        ing = ensure_ticker_indexed(ticker)
    except NoQuarterlyFilings as e:
        # Not fatal: keep going (live market data may still answer part of the question) and say so in the memo
        return {"chunks": [], "notes": [f"No filing data available: {e}"],
                "trace": [_step("retriever", f"no 10-Qs for {ticker}; continuing without filings")]}
    except ValueError as e:
        return {"error": str(e), "trace": [_step("retriever", f"ingestion failed: {e}")]}
    period = named_period(query, ticker) or (latest_period(ticker) if LATEST_WORDS.search(query) else None)
    hits = search(query, k=settings.retrieval_k, ticker=ticker, period_end=period)
    stmt_qs = list(dict.fromkeys(CALC_QUERIES[c] for c in plan.get("calculations") or []))
    if not stmt_qs:
        if BALANCE_WORDS.search(query):
            stmt_qs = [BALANCE_Q]
        elif FIN_WORDS.search(query):
            stmt_qs = [INCOME_Q]
    seen = {h["text"] for h in hits}
    extra_k = settings.retrieval_k_calc - settings.retrieval_k
    for q in stmt_qs:
        for h in search(q, k=extra_k, ticker=ticker, period_end=period or latest_period(ticker)):
            if h["text"] not in seen:
                seen.add(h["text"])
                hits.append({**h, "stmt": True})
    chunks = [{"tag": f"S{i}", **h} for i, h in enumerate(hits, 1)]
    detail = f"{ing['source']} ({ing['new_filings']} new filings); retrieved {len(chunks)} passages"
    if period:
        detail += f" from period {period}"
    return {"chunks": chunks, "trace": [_step("retriever", detail, ingestion=ing)]}


# ---------------------------------------------------------------- market
def market_node(state: AgentState) -> dict:
    try:
        data = get_stock_data(state["ticker"])
        return {"market": data, "trace": [_step("market", f"yfinance snapshot for {data['symbol']}")]}
    except Exception as e:
        return {"market": None, "notes": [f"Live market data was unavailable: {e}"],
                "trace": [_step("market", f"yfinance failed: {e}")]}


# ------------------------------------------------------------------ calc
def _grounded(value, corpus: str) -> bool:
    """True if the number appears verbatim (ignoring sign and thousands separators) in the excerpts.

    Only the number's own exact form counts (36629.0 -> "36629"); rounded forms would let a value like
    0.3967 "match" any stray 0 in the text."""
    try:
        num = abs(float(value))
    except (TypeError, ValueError):
        return False
    form = str(int(num)) if num == int(num) else f"{num:.10g}"
    return re.search(rf"(?<![\d.]){re.escape(form)}(?![\d]|\.\d)", corpus) is not None


YTD_WORDS = re.compile(r"year[- ]to[- ]date|\bytd\b|six months|nine months|six-month|nine-month|cumulative", re.I)


def _guidance(query: str) -> str:
    """Instructions identical for every calculator in one query (kept right after the excerpts so the
    server's prompt cache covers excerpts + guidance and only the short per-tool line differs)."""
    scope = ("the year-to-date (cumulative) columns" if YTD_WORDS.search(query)
             else "the most recent THREE-MONTH quarter columns (not six/nine-month year-to-date columns)")
    return (f"Use {scope}. Column order differs by company: read the column headers to tell the latest period from the same "
            "period a year earlier. Tables often show quarter columns first and cumulative columns after them, e.g. a row "
            "'Total net sales | 109,417 | 94,036 | 364,357 | 313,695' under headers 'Three Months Ended' then 'Nine Months Ended' means "
            "the quarter is 109,417 (now) vs 94,036 (a year earlier); the last two numbers are year-to-date.")


def _tool_line(tool_name: str, query: str) -> str:
    """Short, question-free, per-calculator instruction (the full question made the model 'answer' instead)."""
    metric = ""
    if tool_name == "yoy_growth":
        if re.search(r"net income|earnings|profit", query, re.I) and not re.search(r"revenue|sales", query, re.I):
            metric = " The metric is net income (the 'Net income' line)."
        else:
            metric = " The metric is total revenue / net sales (the revenue line), NOT a margin or ratio."
    return f"Extract the inputs for {tool_name}({prompts.CALC_ARGS[tool_name]}).{metric}"


def _run_one_calc(tool_name: str, query: str, context: str, corpus: str) -> tuple[dict | None, str]:
    expected = [p for p in inspect.signature(CALC_TOOLS[tool_name]).parameters if p != "places"]
    user = f"Excerpts:\n{context}\n\n{_guidance(query)}\n\n{_tool_line(tool_name, query)}"
    parsed: dict = {}
    args: dict = {}
    problem = ""
    for attempt in range(2):  # one retry when the inputs are mis-named or not found in the excerpts
        msg = user if attempt == 0 else user + f"\n\nYour previous answer was rejected: {problem} Fix it, using only numbers printed in the excerpts."
        try:
            resp = get_llm(thinking=False, max_tokens=300).invoke([SystemMessage(prompts.CALC_SYSTEM), HumanMessage(msg)], config={"run_name": f"calc-extract:{tool_name}"})
        except Exception as e:
            return None, f"{tool_name} skipped: LLM error {e}"
        parsed = parse_json(resp.content) or {}
        args = parsed.get("args")
        if not isinstance(args, dict) or not args:
            return None, f"{tool_name} skipped: required figures not found in the retrieved excerpts"
        if set(args) != set(expected):
            problem = f"argument names must be exactly {expected}, got {sorted(args)}."
            continue
        ungrounded = [k for k, v in args.items() if not _grounded(v, corpus)]
        if ungrounded:
            problem = f"{ungrounded} do not appear verbatim in the excerpts."
            continue
        problem = ""
        break
    if problem:
        return None, f"{tool_name} skipped: {problem}"
    try:
        result = CALC_TOOLS[tool_name](**args)
    except (TypeError, ValueError) as e:
        return None, f"{tool_name} failed: {e}"
    return {"tool": tool_name, "inputs": args, "result": result}, f"{tool_name}({args}) = {result}"


def calc_node(state: AgentState) -> dict:
    chunks = state.get("chunks") or []
    if not chunks:
        return {"calcs": [], "trace": [_step("calc", "skipped: no filing context")]}
    if settings.calc_statement_chunks_only:
        chunks = [c for c in chunks if c.get("stmt")] or chunks
    context = "\n\n".join(f"[{c['tag']}] ({c['metadata']['period_end']}, {c['metadata']['section']})\n{c['text']}" for c in chunks)
    corpus = context.replace(",", "")
    calcs, lines, notes = [], [], []
    for name in state["plan"]["calculations"]:
        res, line = _run_one_calc(name, state["query"], context, corpus)
        lines.append(line)
        if res:
            calcs.append(res)
        else:
            notes.append(f"Could not compute {name.replace('_', ' ')}: the needed figures were not found verbatim in the retrieved filing passages.")
    return {"calcs": calcs, "notes": notes, "trace": [_step("calc", "; ".join(lines))]}


# ------------------------------------------------------------ synthesizer
def _fmt_context(state: AgentState) -> str:
    parts = []
    for c in state.get("chunks") or []:
        m = c["metadata"]
        parts.append(f"[{c['tag']}] {m['ticker']} 10-Q, period ended {m['period_end']}, {m['section']}\n{c['text']}")
    if state.get("market"):
        parts.append("[M] Live market data (yfinance): " + json.dumps(state["market"]))
    for i, c in enumerate(state.get("calcs") or [], 1):
        parts.append(f"[C{i}] Deterministic calculation {c['tool']} with inputs {json.dumps(c['inputs'])} = {c['result']}")
    return "\n\n".join(parts)


def synthesizer_node(state: AgentState) -> dict:
    context = _fmt_context(state)
    notes = state.get("notes") or []
    if not context:
        memo = "## Executive Summary\n" + ("\n".join(notes) if notes else "No supporting data could be retrieved for this question.")
        return {"memo": memo, "citations": [], "trace": [_step("synthesizer", "no context available")]}
    user = f"Question: {state['query']}\n\nSOURCES:\n{context}"
    if notes:
        user += "\n\nLIMITATIONS (state these plainly in the memo):\n" + "\n".join(f"- {n}" for n in notes)
    messages = [SystemMessage(prompts.SYNTH_SYSTEM), HumanMessage(user)]
    note = ""
    memo = ""
    if memo_uses_openrouter():
        try:
            memo = get_memo_llm(settings.synth_max_tokens).invoke(messages, config={"run_name": "memo-openrouter"}).content.strip()
            note = f" via OpenRouter ({settings.memo_model})" if memo else " (OpenRouter returned nothing; used local model)"
        except Exception as e:  # free tier can rate-limit or error: fall back to the local model
            note = f" (OpenRouter failed: {type(e).__name__}; used local model)"
    if not memo:
        # local model: thinking only pays off when reasoning over filing text; market/calc-only memos are short lookups
        thinking = settings.synth_thinking and bool(state.get("chunks"))
        memo = get_llm(thinking=thinking, max_tokens=settings.synth_max_tokens).invoke(messages, config={"run_name": "memo-local"}).content.strip()
        if not memo and thinking:  # reasoning consumed the whole token budget -> retry without thinking
            memo = get_llm(thinking=False, max_tokens=1500).invoke(messages, config={"run_name": "memo-local-retry"}).content.strip()
            note += " (thinking exhausted budget; retried without thinking)"
    if not memo:
        return {"memo": "The model returned no answer. Please retry.", "citations": [],
                "trace": [_step("synthesizer", "empty LLM response")]}
    memo = re.sub(r"\s*\[LIMITATIONS\]", "", memo)  # the model sometimes "cites" the limitations block
    memo = re.sub(r"(\[(?:S\d+|M|C\d+)\])(?:\s*\1)+", r"\1", memo)  # collapse repeated identical tags
    cited = set(re.findall(r"\[(S\d+)\]", memo))
    citations = [
        {"tag": c["tag"], "cited": c["tag"] in cited, "ticker": c["metadata"]["ticker"],
         "period_end": c["metadata"]["period_end"], "section": c["metadata"]["section"],
         "accession": c["metadata"].get("accession"), "source_url": c["metadata"].get("source_url"),
         "excerpt": c["text"][:300]}
        for c in state.get("chunks") or []
    ]
    return {"memo": memo, "citations": citations,
            "trace": [_step("synthesizer", f"memo written ({len(memo)} chars, {len(cited)} sources cited){note}")]}


# --------------------------------------------------------------- verifier
# Not claims: "52-week", "52 weeks", "20-F", "10-Q" (units of time and SEC form names)
NUM_RE = re.compile(r"(?<![\w.\[])\$?(\d[\d,]*(?:\.\d+)?)(?!(?:-|\s)?(?:week|day|month|year|quarter)s?\b|-[A-Z]s?\b|K\b|Q\d)")
SCALES = (1, 1e3, 1e6, 1e9, 1e12, 1e-3, 1e-6, 1e-9, 1e-12)
TAG_AFTER = re.compile(r"[^\[\n]{0,25}\[(S\d+|M|C\d*)\]")
MARKET_LABEL = {"price": "Price", "pe_trailing": "Trailing P/E", "pe_forward": "Forward P/E", "week52_low": "52-week low",
                "week52_high": "52-week high", "volume": "Volume", "avg_volume": "Average volume", "market_cap": "Market cap"}


def _to_float(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _snippet(text: str, start: int, end: int, pad: int = 80) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - pad): end + pad]).strip()


def build_evidence(state: AgentState) -> list[dict]:
    """Every number in the sources, with where it lives. Order = match priority (calc, market, filings)."""
    ev: list[dict] = []
    for i, c in enumerate(state.get("calcs") or [], 1):
        label = c["tool"].replace("_", " ")
        ev.append({"value": abs(float(c["result"])), "kind": "calc", "tag": f"C{i}", "field": f"{label} (result)"})
        for k, v in c["inputs"].items():
            ev.append({"value": abs(float(v)), "kind": "calc", "tag": f"C{i}", "field": f"{label}: {k.replace('_', ' ')}"})
    for k, v in (state.get("market") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            ev.append({"value": float(v), "kind": "market", "tag": "M", "field": MARKET_LABEL.get(k, k), "source_text": f"{v:,}"})
    for c in state.get("chunks") or []:
        m = c.get("metadata") or {}
        for nm in NUM_RE.finditer(c["text"]):
            val = _to_float(nm.group(1))
            if val is not None:
                ev.append({"value": val, "kind": "filing", "tag": c.get("tag", "S?"), "field": m.get("section", ""),
                           "period_end": m.get("period_end"), "source_text": nm.group(1),
                           "snippet": _snippet(c["text"], nm.start(1), nm.end(1))})
    return ev


def _matches(k: float, s: float, val: float, decimals: int) -> bool:
    tol = 0.5 * 10 ** -decimals + 1e-9
    return abs(k * s - val) <= max(tol, abs(val) * 0.006)


def verifier_node(state: AgentState) -> dict:
    """Deterministic fact-grounding: every figure in the memo must trace to a source, market value or calc.

    Also records WHERE each figure was found (source tag, filing period/section, the surrounding text)."""
    memo = state.get("memo", "")
    blank = lambda m: " " * len(m.group(0))  # noqa: E731  (keeps character offsets stable)
    scan = re.sub(r"\b(19|20)\d{2}(-\d{2}-\d{2})?\b", blank, memo)  # years / ISO dates are not claims
    scan = re.sub(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b", blank, scan)  # "September 30"
    evidence = build_evidence(state)

    grounding: list[dict] = []
    unverified: list[str] = []
    seen: set[str] = set()
    checked = 0
    for m in NUM_RE.finditer(scan):
        raw = m.group(1).rstrip(",")
        val = _to_float(raw)
        if val is None:
            continue
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if decimals == 0 and val < 10:
            continue  # counts like "three drivers"
        figure = m.group(0).rstrip(",")
        checked += 1
        tag_m = TAG_AFTER.match(scan, m.end())
        cited_tag = tag_m.group(1) if tag_m else None
        found = None
        # Prefer the source the memo cites right after the number, then any source; exact matches
        # (scale 1) win over unit-converted ones (e.g. 4,975,383,019,520 shown as $4.98 trillion).
        pools = ([[e for e in evidence if e["tag"] == cited_tag]] if cited_tag else []) + [evidence]
        for pool in pools:
            for s in SCALES:
                hit = next((e for e in pool if _matches(e["value"], s, val, decimals)), None)
                if hit:
                    found = {**hit, "scaled": s != 1}
                    break
            if found:
                break
        if not found:
            unverified.append(figure)
        elif figure not in seen:
            seen.add(figure)
            grounding.append({"figure": figure, **{k: v for k, v in found.items() if k != "value"}, "source_value": found["value"]})
    ratio = None if checked == 0 else round((checked - len(unverified)) / checked, 3)
    ver = {"numbers_checked": checked, "unverified": unverified, "grounded_ratio": ratio, "grounding": grounding}
    return {"verification": ver,
            "trace": [_step("verifier", f"{checked - len(unverified)}/{checked} numbers grounded")]}
