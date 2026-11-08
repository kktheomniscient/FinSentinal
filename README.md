# FinSentinel

**An autonomous equity-research agent that answers questions about US-listed companies from their SEC 10-Q filings, and shows its work.**

Ask something like *"What was Apple's net margin last quarter, and how does it compare to a year ago?"* FinSentinel works out which company you mean, pulls the relevant 10-Q passages from SEC EDGAR, has a calculator (not the LLM) do the arithmetic, optionally fetches live market data, and writes a short, cited due-diligence memo. A verifier then checks every number in the memo against its sources.

> **What's included:** a FastAPI + LangGraph backend, an on-demand SEC EDGAR ingestion pipeline, deterministic financial tools, a Ragas evaluation suite (faithfulness 0.978), Langfuse tracing, and a streaming Next.js research terminal.

---

## Table of contents

1. [Key features](#key-features)
2. [How it works](#how-it-works)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Getting started](#getting-started)
6. [Configuration](#configuration)
7. [API reference](#api-reference)
8. [The agent in detail](#the-agent-in-detail)
9. [Data ingestion](#data-ingestion)
10. [Evaluation](#evaluation)
11. [Observability](#observability)
12. [Frontend](#frontend)
13. [Testing](#testing)
14. [Design decisions](#design-decisions)
15. [Limitations](#limitations)
16. [Future enhancements](#future-enhancements)
17. [License](#license)

---

## Key features

- **Grounded answers.** The memo may only use facts from retrieved sources. Each claim carries a tag: `[S1]` filing passage, `[M]` live market data, `[C1]` computed figure.
- **Zero-LLM arithmetic.** Debt/Equity, net margin, YoY growth and YoY net-margin change run in plain Python with `Decimal`. The LLM only *extracts* input numbers, and each extracted number must appear verbatim in the retrieved excerpts, or the calculation is rejected and retried.
- **Deterministic fact verification.** After the memo is written, a verifier node checks every figure against filing text, market data and calculation results. It reports a `grounded_ratio` and lists any unverified figures.
- **On-demand ingestion.** Any ticker in SEC EDGAR is fetched, parsed, chunked and indexed the first time someone asks about it. Seed tickers are preloaded for instant answers.
- **Section-aware citations.** Chunks carry ticker, period end, Part/Item section, accession number and source URL.
- **Live streaming UI.** Server-Sent Events show each agent step as it happens (ingesting, retrieving, calculating, writing, verifying).
- **Resilient by design.** If the router LLM fails, heuristics take over. If OpenRouter fails, the memo falls back to the local model. If Langfuse is unreachable, the app runs untraced. If a ticker has no 10-Qs, the agent says so and still answers what it can.
- **Measured quality.** A 15-question Ragas benchmark is included, with results checked into the repo.

---

## How it works

```
 Next.js terminal (shadcn/ui)
        │  POST /api/v1/research/stream   (SSE)
        ▼
 FastAPI  ──►  LangGraph state machine
                 │
                 ▼
              router ──► retriever ──► market ──► calc ──► synthesizer ──► verifier
              (LLM +     (EDGAR →      (yfinance) (LLM      (OpenRouter    (deterministic
              heuristics) Chroma)                  extracts   or local LLM)  number check)
                                                   inputs,
                                                   Python
                                                   computes)
```

Each stage is optional where it makes sense. A pure price question skips the filings, and a pure narrative question skips the calculator:

| Router decision | Path taken |
|---|---|
| needs filings only | router → retriever → synthesizer → verifier |
| filings + live data | router → retriever → market → synthesizer → verifier |
| filings + ratios | router → retriever → (market) → calc → synthesizer → verifier |
| live data only | router → market → synthesizer → verifier |
| no identifiable company / ingestion error | router (or retriever) → END with an `error` |

(Defined in [backend/app/agent/workflow.py](backend/app/agent/workflow.py).)

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn/ui (Base UI), Lucide icons |
| API | FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Orchestration | LangGraph (`StateGraph`), LangChain (`langchain-openai`) |
| LLMs | Any OpenAI-compatible endpoint. Default: a local llama.cpp-style server on `localhost:1234` (Qwen). Optional OpenRouter for the final memo. |
| Vector store | ChromaDB (persistent) with `sentence-transformers/all-MiniLM-L6-v2` embeddings |
| Filings | SEC EDGAR (`data.sec.gov` submissions API + `sec.gov/Archives`) via `httpx`; parsed with BeautifulSoup + lxml; `pypdf` as a fallback |
| Market data | `yfinance` |
| Evaluation | Ragas + `datasets` |
| Tracing | Langfuse (optional) |
| Tests | pytest |

---

## Project structure

```
finsentinel/
├── .env                          # secrets & overrides (not committed; see Configuration)
├── init.md                       # original design and implementation notes
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, startup warm-up of embeddings + Chroma
│   │   ├── config.py             # all settings (pydantic-settings, reads .env)
│   │   ├── observability.py      # fail-safe Langfuse tracing + scoring
│   │   ├── api/v1/
│   │   │   ├── endpoints.py      # /health, /research, /research/stream
│   │   │   └── schemas.py        # request/response models (Citation, Verification, ...)
│   │   ├── agent/
│   │   │   ├── state.py          # AgentState TypedDict
│   │   │   ├── workflow.py       # LangGraph graph, run_research(), stream_research()
│   │   │   ├── nodes.py          # router, retriever, market, calc, synthesizer, verifier
│   │   │   ├── prompts.py        # router / calc-extraction / memo system prompts
│   │   │   └── llm.py            # local + OpenRouter chat model factories
│   │   ├── tools/
│   │   │   ├── financial_math_tool.py  # Decimal-based ratio math
│   │   │   └── stock_data_tool.py      # yfinance snapshot
│   │   ├── ingestion/
│   │   │   ├── sec_edgar_client.py     # ticker→CIK, list/download 10-Qs, rate limited
│   │   │   ├── filing_loader.py        # HTML→text, Part/Item sections, chunking
│   │   │   ├── vector_indexer.py       # Chroma upsert/search/metadata helpers
│   │   │   ├── ingestion_service.py    # ensure_ticker_indexed() with locks + freshness
│   │   │   └── seed_universe.py        # CLI to pre-seed tickers
│   │   └── evaluation/
│   │       ├── benchmark_data.json     # 15 golden Q&A items
│   │       ├── run_ragas_eval.py       # benchmark runner
│   │       └── results.json            # latest scores + per-question output
│   ├── data/
│   │   ├── raw_filings/          # downloaded 10-Q .htm + .json sidecar metadata
│   │   ├── chroma_db/            # persisted vector index
│   │   └── ingestion_state.json  # per-ticker last-checked timestamps / seed flags
│   └── tests/                    # pytest unit tests
└── frontend/
    ├── package.json
    ├── components.json           # shadcn configuration
    └── src/
        ├── app/                  # layout.tsx, page.tsx, globals.css
        ├── components/           # header, query-panel, tool-execution-log,
        │                         # metrics-grid, memo-viewer, citations-table,
        │                         # theme-toggle, and ui/ (shadcn primitives)
        └── lib/                  # api.ts (SSE client), use-research.ts, types.ts, format.ts, utils.ts
```

---

## Getting started

### Prerequisites

- **Python 3.12+** (the checked-in virtualenv uses 3.14)
- **Node.js 20+** and npm
- An **OpenAI-compatible LLM server** reachable at `http://localhost:1234/v1` (for example llama.cpp or LM Studio serving a Qwen model), *or* change `LLM_BASE_URL`/`LLM_MODEL` to point elsewhere
- Internet access for SEC EDGAR and yfinance
- Optional: an [OpenRouter](https://openrouter.ai) key and a [Langfuse](https://langfuse.com) project

### 1. Configure environment

Copy `.env.example` to `.env` in the project root (the backend also reads `backend/.env`) and fill it in:

```bash
cp .env.example .env
```

It contains:

```env
# Optional: use OpenRouter for the final memo (otherwise the local model writes it)
OPENROUTER_KEY=sk-or-...

# Optional: Langfuse tracing (leave blank to disable)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Required: SEC requires a User-Agent with contact info; the EDGAR client builds it from this
EMAIL=your@email.com
# Optional full override: SEC_USER_AGENT="Your Name your@email.com"
```

> ⚠️ `.env` holds secrets. Keep it out of version control (add it to `.gitignore`).

### 2. Backend

```bash
cd backend
python -m venv ../venv && source ../venv/bin/activate   # or reuse the existing ../venv
pip install -r requirements.txt

# Optional: preload the default blue-chip tickers (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM)
python -m app.ingestion.seed_universe
# ...or specific ones:
python -m app.ingestion.seed_universe KO LLY

# Start the API on :8000
uvicorn app.main:app --reload --port 8000
```

On startup the app loads the embedding model and opens Chroma once, so the first query is not slow. Check it is up:

```bash
curl http://localhost:8000/api/v1/health
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

The frontend talks to `http://localhost:8000/api/v1` by default. Override with `NEXT_PUBLIC_API_URL`.

> The frontend's `AGENTS.md` notes that this Next.js version has breaking changes from older releases. Check `node_modules/next/dist/docs/` before changing framework-level code.

### 4. Try it

Open the UI and ask, for example:

- *What were Apple's total net sales for the quarter ended June 27, 2026?*
- *Compare NVIDIA's net margin this quarter vs a year ago.*
- *What is Tesla's debt-to-equity ratio, and what is it trading at now?*
- *What are the main risks Meta flagged in its latest 10-Q?*

Or call the API directly:

```bash
curl -s -X POST http://localhost:8000/api/v1/research \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is Microsoft'"'"'s net margin in the latest quarter?"}' | jq
```

---

## Configuration

All settings live in [backend/app/config.py](backend/app/config.py) and can be overridden by environment variables (or `.env`), using the upper-cased field name.

| Setting | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:1234/v1` | OpenAI-compatible endpoint for routing, calc extraction, and memo fallback |
| `LLM_MODEL` | `erp-brain` | Model name sent to that endpoint (set this to your served model's name) |
| `OPENAI_API_KEY` | `not-needed` | Key for the local endpoint |
| `LLM_TIMEOUT` | `900` s | Local LLM request timeout |
| `OPENROUTER_KEY` | *(empty)* | If set, the final memo is generated via OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `MEMO_MODEL` | `nvidia/nemotron-3.5-super-vl:free` | OpenRouter model for the memo |
| `MEMO_TIMEOUT` | `120` s | |
| `SYNTH_THINKING` | `true` | Qwen "thinking" mode for memo synthesis (slower, more accurate) |
| `SYNTH_MAX_TOKENS` | `6000` | Memo token budget |
| `JUDGE_THINKING` | `false` | Thinking mode for the Ragas judge |
| `RETRIEVAL_K` | `3` | Top-k semantic passages |
| `RETRIEVAL_K_CALC` | `7` | Total passages when ratios are requested (adds statement-table passages) |
| `CALC_STATEMENT_CHUNKS_ONLY` | `false` | Send only statement-table chunks to calc extraction (faster prompts) |
| `EMAIL` | *(required)* | Contact email; the EDGAR User-Agent becomes `FinSentinel <EMAIL>`. The backend refuses to start without it (or `SEC_USER_AGENT`) |
| `SEC_USER_AGENT` | *(derived from `EMAIL`)* | Optional full override of the User-Agent string |
| `SEC_MAX_RPS` | `5.0` | EDGAR request rate (SEC's limit is 10/s) |
| `FILINGS_PER_TICKER` | `4` | Latest N 10-Qs ingested per ticker |
| `REFRESH_AFTER_HOURS` | `24` | Minimum gap between EDGAR freshness checks per ticker |
| `SEED_TICKERS` | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM | Default list for `seed_universe` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `120` | Text splitter settings |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | |
| `CORS_ORIGINS` | `localhost:3000`, `127.0.0.1:3000` | Allowed frontend origins |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` | *(empty)* | Empty keys turn tracing off |

Storage paths (`RAW_FILINGS_DIR`, `CHROMA_DIR`, `STATE_FILE`) default to `backend/data/...`.

---

## API reference

Base path: `/api/v1`. Interactive docs are at `http://localhost:8000/docs`.

### `GET /health`

Returns service status and the active models.

```json
{ "status": "ok", "llm_model": "erp-brain", "llm_base_url": "http://localhost:1234/v1",
  "memo_model": "nvidia/nemotron-3.5-super-vl:free", "tracing": true }
```

### `POST /research`

Runs the agent to completion and returns the whole result.

**Request**

| Field | Type | Notes |
|---|---|---|
| `query` | string | 3–1000 characters, required |
| `ticker` | string \| null | Optional override, up to 10 characters (`A-Z a-z 0-9 . -`). If omitted, the router infers it from the query. |

**Response (`ResearchResponse`)**

| Field | Description |
|---|---|
| `memo` | Markdown memo (`## Executive Summary`, optionally `## Key Drivers` / `## Risks`) |
| `ticker` | Resolved ticker |
| `citations[]` | `{tag, cited, ticker, period_end, section, accession, source_url, excerpt}` |
| `market` | yfinance snapshot (price, P/E, 52-week range, volume, market cap), or `null` |
| `calcs[]` | `{tool, inputs, result}` for each deterministic calculation |
| `notes[]` | Limitations the memo had to state (for example missing data) |
| `verification` | `{numbers_checked, unverified[], grounded_ratio, grounding[]}`, where `grounding` records where each figure was found |
| `trace[]` | `{node, detail}` per executed step |
| `trace_url` | Langfuse trace link when tracing is enabled |
| `error` | Set when the run could not proceed (for example unknown ticker) |

### `POST /research/stream`

Same request body. Returns `text/event-stream` with these events:

| Event | Payload |
|---|---|
| `step` | `{node, detail, plan?}`, one per completed graph node |
| `ingesting` | `{ticker}`, emitted when the retriever starts ensuring filings are indexed |
| `warning` | `{detail}`, for example router LLM failure fell back to heuristics |
| `result` | The full `ResearchResponse` shape |
| `error` | `{detail}`, for an unexpected failure |

The frontend consumes this with `fetch` + a stream reader (see [frontend/src/lib/api.ts](frontend/src/lib/api.ts)), because `EventSource` cannot POST.

---

## The agent in detail

All nodes are in [backend/app/agent/nodes.py](backend/app/agent/nodes.py) and share an `AgentState` ([state.py](backend/app/agent/state.py)): `query`, `ticker`, `plan`, `chunks`, `market`, `calcs`, `notes`, `memo`, `citations`, `verification`, `error`, `trace`.

### 1. Router
A short, non-thinking LLM call returns JSON: `{ticker, needs_docs, needs_market, calculations[]}`. Heuristics reinforce it:
- Regexes detect market keywords (price, P/E, 52-week, volume, market cap) if the LLM omits `needs_market`.
- Keyword fallbacks add any calculation the user plainly named (net margin, YoY growth, debt-to-equity), capped at 3.
- Questions about revenue, income, debt, equity and similar always force `needs_docs`.
- If the LLM call fails entirely, a `warning` event is emitted and heuristics carry on.
- No identifiable ticker produces a clear error instead of a guess.

### 2. Retriever
1. Calls `ensure_ticker_indexed(ticker)`, which emits an `ingesting` event and fetches from EDGAR only if needed.
2. Picks the period to search: a date named in the query (for example "June 27, 2026") if indexed, otherwise the latest period when the query says *latest / most recent / current…*.
3. Runs a semantic search (`k=3`) filtered by ticker and period.
4. For ratio or financial questions, adds statement-shaped searches ("BALANCE SHEETS … Total stockholders' equity", "INCOME STATEMENTS … Net income") because semantic search alone often misses table chunks. Total passages go up to 7.
5. Tags passages `S1…Sn`.
6. If the ticker has no 10-Qs (for example foreign private issuers filing 20-F), this is *not* fatal: a note is recorded and the run continues.

### 3. Market
Fetches a `yfinance` snapshot (price, trailing/forward P/E, 52-week range, volume, average volume, market cap). Failure adds a note instead of aborting.

### 4. Calc
For each requested calculation, the LLM extracts exact input figures from the excerpts as JSON. Safeguards:
- Argument names must match the tool signature exactly.
- Every number must appear **verbatim** in the retrieved text (sign and thousands separators ignored). Otherwise the call is retried once with feedback, then skipped with a note.
- Prompts steer it to the correct column (latest three-month quarter vs year-to-date, or the prior-year comparison column).
- The computation itself is done by [financial_math_tool.py](backend/app/tools/financial_math_tool.py): `debt_to_equity`, `net_margin`, `yoy_growth`, `yoy_net_margin_growth`. These use `Decimal`, round explicitly, and raise on divide-by-zero.

### 5. Synthesizer
Writes the memo under strict rules ([prompts.py](backend/app/agent/prompts.py)): sources only, cite every claim, copy numbers exactly, name the filing period, never do arithmetic, answer every part of the question, state limitations plainly, under 300 words.

Model selection: OpenRouter (`MEMO_MODEL`) when `OPENROUTER_KEY` is set, falling back to the local model if it errors or returns nothing. The local model uses thinking mode when reasoning over filing text, with an automatic non-thinking retry if reasoning exhausts the token budget.

### 6. Verifier
A deterministic check (no LLM). It extracts every number in the memo, ignoring years, dates, small counts, and unit words like "52-week" or form names like "10-Q", and looks for a matching value in the evidence: calculation inputs and results, market data, and every number in the retrieved passages. It tolerates unit scaling (for example 4,975,383,019,520 shown as $4.98 trillion) and rounding, and prefers the source the memo cited. The output is `numbers_checked`, `unverified[]`, `grounded_ratio`, and a per-figure `grounding` record (source tag, period, section, surrounding snippet).

---

## Data ingestion

Implemented in [backend/app/ingestion/](backend/app/ingestion/).

1. **EDGAR client** resolves ticker → zero-padded CIK (`company_tickers.json`), lists filings from the submissions API, filters `form == "10-Q"`, and downloads the primary document into `backend/data/raw_filings/` as `{TICKER}_10-Q_{period_end}.htm` plus a `.json` metadata sidecar. It sends a descriptive `User-Agent` and rate limits requests (default 5 req/s).
2. **Filing loader** flattens HTML to text (one line per block, tables as ` | `-joined rows), detects `PART` / `ITEM` headings so each chunk knows its section, then splits with `RecursiveCharacterTextSplitter` (900 chars, 120 overlap).
3. **Chunk metadata:** ticker, form, period end, section, accession number, source URL.
4. **Vector indexer** upserts into a persistent Chroma collection (`filings`) with MiniLM embeddings. Chunk IDs derive from the filing, so re-indexing is idempotent.
5. **Ingestion service** (`ensure_ticker_indexed`):
   - Returns instantly from cache if the ticker is indexed and was checked within `REFRESH_AFTER_HOURS`.
   - Otherwise lists the latest N 10-Qs, downloads and indexes only the ones not yet indexed.
   - A per-ticker lock means concurrent queries for the same ticker ingest once.
   - Unknown tickers fail fast with a clear message. Tickers with no 10-Qs get an informative `NoQuarterlyFilings` error that says which forms they do file.
   - State (last-checked time, seed flag) lives in `backend/data/ingestion_state.json`.

Note that 10-Qs only cover Q1–Q3. Q4 is reported in the 10-K, which this system does not ingest.

Downloaded filings and the vector index are local data (git-ignored). Run the seed script, or just ask about a ticker, to build them.

---

## Evaluation

```bash
cd backend
python -m app.evaluation.run_ragas_eval                 # all 15 questions
python -m app.evaluation.run_ragas_eval --limit 5       # first 5
python -m app.evaluation.run_ragas_eval --ids 1,9,14    # specific questions
python -m app.evaluation.run_ragas_eval --out results.json
```

[benchmark_data.json](backend/app/evaluation/benchmark_data.json) has 15 golden questions (id, ticker, category, question, ground truth, key facts). The runner executes each through the real agent and scores it with Ragas, using the local LLM as judge, plus a deterministic key-fact check and router accuracy.

Latest recorded run ([results.json](backend/app/evaluation/results.json)), n = 15:

| Metric | Score |
|---|---|
| Faithfulness | **0.978** (target ≥ 0.85, met) |
| Answer relevancy | 0.83 |
| Context precision | 0.583 |
| Key-fact hit rate | 0.867 |
| Router ticker accuracy | 1.00 |

Context precision is the weakest metric, which fits the retrieval design: it deliberately pulls extra statement-table chunks that a judge may rate as less relevant.

---

## Observability

[observability.py](backend/app/observability.py) integrates **Langfuse** and is fail-safe: with no keys, or if Langfuse is unreachable, the app behaves normally without tracing. Secrets are never logged.

- Each run creates a trace tagged `finsentinel`, with session id and ticker metadata.
- LLM calls get readable run names (`router-llm`, `calc-extract:<tool>`, `memo-openrouter`, `memo-local`).
- Key functions (`yfinance.get_stock_data`, `ingestion.ensure_ticker_indexed`) are recorded as timed spans.
- A `figure_grounding` score (the verifier's `grounded_ratio`) is attached to every trace.
- The API returns `trace_url` so the UI can link to the trace. `/health` reports whether tracing is on.

---

## Frontend

A single-page "research terminal" built with Next.js App Router and shadcn/ui, with light and dark themes.

| Component | Role |
|---|---|
| `query-panel` | Ticker selector (seed tickers), natural-language prompt, run and cancel |
| `tool-execution-log` | Live badges and steps for each agent node, including ingestion progress |
| `memo-viewer` | Renders the Markdown memo; citation tags `[S1]` link to the sources |
| `citations-table` | Expandable sources: period, section, accession, EDGAR link, excerpt |
| `metrics-grid` | Market snapshot cards and calculation cards (`CalcCard`, `MarketGrid`) |
| `header`, `theme-toggle` | Navigation bar with backend status, theme switch |

State and streaming are handled by `useResearch` ([use-research.ts](frontend/src/lib/use-research.ts)), which reads the SSE stream from the API client. Warnings and limitations (`notes`) are shown in a "Limits of this answer" callout.

Scripts: `npm run dev`, `npm run build`, `npm start`, `npm run lint`.

---

## Testing

```bash
cd backend
pytest
```

| File | Covers |
|---|---|
| `test_financial_math.py` | Ratio and growth arithmetic |
| `test_filing_loader.py` | 10-Q parsing and chunk metadata |
| `test_ingestion_service.py` | Cache vs EDGAR paths, freshness, locking |
| `test_agent_units.py` | Router/calc/verifier helper logic |

Tests are unit-level and do not call the LLM. The Ragas benchmark is the end-to-end quality check. The frontend has no automated tests yet.

---

## Design decisions

- **LLM for language, Python for numbers.** Models are unreliable at arithmetic, so a calculator does the math and a verifier audits the result.
- **Hybrid retrieval.** Semantic search plus statement-shaped queries. Embeddings alone often miss financial tables.
- **Local first, hosted where it pays.** Routing and extraction (short, structured) run on a local model with thinking off, which is much faster. The slow, reasoning-heavy memo step can use a fast hosted model, with local fallback.
- **Lean index.** Only tickers that people ask about (plus seeds) are stored. Ingestion is idempotent and rate limited.
- **Fail soft.** Every external dependency (router LLM, OpenRouter, yfinance, Langfuse, EDGAR coverage) degrades gracefully and tells the user what was missing.

---

## Limitations

- Covers **10-Q filings only** (no 10-K, 8-K, earnings transcripts, or foreign private issuers that file 20-F / 6-K).
- Only the latest `FILINGS_PER_TICKER` (4) quarters per ticker are indexed.
- Calculations need the relevant statement values to be in the retrieved passages; otherwise they are skipped and noted.
- The verifier checks that figures *exist in sources*, not that they are used with the right meaning.
- Live market data comes from `yfinance` (unofficial, can be rate limited or incomplete).
- Output quality depends on the configured LLMs. Default model name `erp-brain` assumes a local server you must provide.
- Not investment advice. This is a research aid.

---

## Future enhancements

- 10-K and 8-K support, including Q4 coverage
- Higher context precision through reranking
- Frontend tests and CI

---

## License

Released under the [MIT License](LICENSE).

---

## Acknowledgements

Filing data from [SEC EDGAR](https://www.sec.gov/edgar). Market data from Yahoo Finance via `yfinance`.
