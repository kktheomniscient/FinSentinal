# FinSentinel: Autonomous Financial Research & Equity Due-Diligence Agent

## 1. Project Overview & JD Alignment
* **Role Alignment:** Generative AI & Agentic AI Track (AI CoE).
* **Objective:** Build an autonomous equity research workstation that accepts complex investor queries, searches unstructured US company filings (SEC 10-Q quarterly reports pulled from SEC EDGAR), invokes deterministic financial calculation tools, pulls live ticker data, validates facts against hallucinations using Ragas, and presents findings on an institutional Next.js + shadcn/ui terminal.
* **Key JD Matches:**
  * LLMs, Generative AI, Prompt Engineering, Embeddings, and Vector Search.
  * Agentic AI, AI Agents, Tool Calling, and Multi-Step Orchestration.
  * AI evaluation across Accuracy, Relevance, Latency, and Safety.
  * Production frontend engineering with accessible component libraries and FastAPI microservices.

---

## 2. Technical Stack
| Layer | Technology | Purpose |
|---|---|---|
| **Frontend UI** | Next.js (App Router), React, TypeScript, **shadcn/ui**, Tailwind CSS, Lucide Icons | Institutional financial workstation interface |
| **Backend API** | FastAPI + Uvicorn + Pydantic v2 | High-performance async REST API with SSE streaming |
| **Agent Orchestration** | LangGraph / LangChain Core | State machine, tool calling loops, branching logic |
| **LLM Inference** | Local OpenAI-compatible server (Qwen, `localhost:1234`) for routing, calculation-input extraction and Ragas judging; OpenRouter (`nvidia/nemotron-3.5-super-vl:free`, key in root `.env` as `OPENROUTER_KEY`) for the final memo, with automatic fallback to the local model | Routing and tool-input extraction stay local; the slow, reasoning-heavy memo step runs on a fast hosted model |
| **Vector DB & Embeddings** | ChromaDB + `sentence-transformers/all-MiniLM-L6-v2` | Local semantic search with metadata filtering |
| **Market Data** | `yfinance` | Real-time prices, historical ranges, and trading multiples for US-listed tickers (NASDAQ/NYSE) |
| **Filings Source** | SEC EDGAR API (`data.sec.gov` submissions API + `www.sec.gov/Archives`), `httpx`, `beautifulsoup4` | Programmatic download of 10-Q quarterly reports (HTML) by ticker/CIK |
| **Document Processing** | `beautifulsoup4` / `lxml` (primary), `pypdf` (fallback) | Parsing EDGAR 10-Q HTML filings into section-aware text; PDF fallback for any manually added documents |
| **Evaluation Suite** | `ragas` + `datasets` | Measuring Faithfulness, Answer Relevance, and Context Precision |

---

## 3. System Architecture & Information Flow

```
   ┌─────────────────────────────────────────────────────────┐
   │        Next.js Research Terminal (shadcn/ui)             │
   │  - Ticker Selector & Search Bar (Input, Command)        │
   │  - Real-time Trace & Tool Execution Badges (Badge, Tabs)│
   │  - Structured Synthesis & Citations (Card, Table)       │
   └────────────────────────────┬────────────────────────────┘
                                │ HTTP / SSE
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │             FastAPI Microservice (Port 8000)             │
   │  - Endpoints: POST /api/v1/research, GET /health        │
   │  - Pydantic v2 Request/Response Validation              │
   └────────────────────────────┬────────────────────────────┘
                                │
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │                LangGraph Agent State Machine            │
   │   (State: query, ticker, docs, tool_results, summary)   │
   └───────────────┬─────────────────────────┬───────────────┘
                   │                         │
     [Qualitative Context Path]    [Quantitative Math Path]
                   │                         │
                   ▼                         ▼
   ┌───────────────────────────┐  ┌──────────────────────────┐
   │   ChromaDB Vector Store   │  │   Python Tool Layer      │
   │  - 10-Q Filing Chunks     │  │  - yfinance (Live quotes)│
   │  - Top-k Semantic Search  │  │  - Deterministic Math    │
   │  - On-demand EDGAR fetch  │  │                          │
   └───────────────┬───────────┘  └──────────┬───────────────┘
                   │                         │
                   └────────────┬────────────┘
                                │
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │             Fact Grounding & Verification Node          │
   │  - Validates numerical assertions against source chunks │
   │  - Formats structured investment thesis memo            │
   └────────────────────────────┬────────────────────────────┘
                                │
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │               Ragas Automated Evaluation                │
   │  - Golden Benchmark Test Set (15+ Q&A pairs)            │
   │  - Faithfulness, Answer Relevance, Context Precision    │
   └─────────────────────────────────────────────────────────┘
```

---

## 4. Repository & File Structure
```
finsentinel/
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                  # API keys, vector DB paths, LLM settings
│   │   ├── main.py                    # FastAPI instance & CORS middleware
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints.py       # POST /api/v1/research, GET /api/v1/health
│   │   │       └── schemas.py         # Pydantic request/response schemas
│   │   ├── agent/
│   │   │   ├── state.py               # TypedDict schema for LangGraph
│   │   │   ├── workflow.py            # LangGraph StateGraph compilation
│   │   │   ├── nodes.py               # Router, Retriever, ToolExecutor, Synthesizer
│   │   │   └── prompts.py             # System prompts with grounding constraints
│   │   ├── tools/
│   │   │   ├── stock_data_tool.py     # yfinance market data fetcher
│   │   │   └── financial_math_tool.py # Zero-hallucination math calculations
│   │   ├── ingestion/
│   │   │   ├── sec_edgar_client.py    # Ticker→CIK lookup, list & download 10-Q filings from SEC EDGAR
│   │   │   ├── filing_loader.py       # 10-Q HTML parsing (Item/section aware) & recursive chunking
│   │   │   ├── vector_indexer.py      # ChromaDB embeddings generation
│   │   │   ├── ingestion_service.py   # ensure_ticker_indexed(): on-demand fetch→parse→index, freshness checks
│   │   │   └── seed_universe.py       # CLI to pre-seed the blue-chip ticker list
│   │   └── evaluation/
│   │       ├── benchmark_data.json    # 15 golden questions with ground truth
│   │       └── run_ragas_eval.py      # Automated Ragas benchmarking script
│   └── data/
│       ├── raw_filings/               # 10-Q filings from SEC EDGAR (pre-seeded blue chips + on-demand cache)
│       └── chroma_db/                 # Persisted vector DB (pre-seeded + lazily ingested tickers)
└── frontend/
    ├── package.json
    ├── components.json                # shadcn configuration
    ├── tailwind.config.ts
    ├── tsconfig.json
    └── src/
        ├── app/
        │   ├── layout.tsx             # Root layout with Inter/Geist fonts
        │   └── page.tsx               # Main Financial Terminal dashboard
        ├── components/
        │   ├── ui/                    # shadcn components (button, card, badge, table, etc.)
        │   ├── header.tsx             # Terminal navigation bar with status indicator
        │   ├── query-panel.tsx        # Ticker select, search prompt, execution button
        │   ├── tool-execution-log.tsx # Visual execution badges showing agent step trace
        │   ├── metrics-grid.tsx       # Live market figures in clean card layouts
        │   └── memo-viewer.tsx        # Markdown memo renderer with citation accordions
        └── lib/
            ├── api.ts                 # Axios/Fetch client connecting to FastAPI
            └── utils.ts               # cn() helper for Tailwind classes
```

---

## 5. Step-by-Step Implementation

### Phase 1: Ingestion & Deterministic Tools (Backend)
1. Initialize virtual environment and install core backend dependencies:
   ```bash
   cd backend
   python -m venv venv && source venv/bin/activate
   pip install fastapi uvicorn pydantic langgraph langchain-openai chromadb sentence-transformers yfinance ragas pypdf httpx beautifulsoup4 lxml
   ```
2. Build `sec_edgar_client.py` (SEC EDGAR API):
   * Resolve ticker → zero-padded 10-digit CIK via `https://www.sec.gov/files/company_tickers.json`.
   * List filings via `https://data.sec.gov/submissions/CIK##########.json`; filter `form == "10-Q"` and keep the latest N (e.g. 4–8).
   * Download the primary document from `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primaryDocument}` into `data/raw_filings/` as `{TICKER}_10-Q_{period_end}.htm` (plus a `.json` metadata sidecar).
   * Compliance: SEC requires a descriptive `User-Agent` header (e.g. `"Your Name your@email.com"`, configured in `config.py`) and a rate limit of ≤10 requests/second; add a small delay/retry. No API key needed.
   * Note: 10-Qs cover Q1–Q3 only (Q4 is reported in the 10-K); this is expected.
3. Build `filing_loader.py`:
   * Parse 10-Q HTML (BeautifulSoup/lxml) into clean text, detecting `Part I/II – Item N` headings (e.g. Item 2 MD&A, Item 1A Risk Factors) so each chunk can cite its section.
   * Split into chunks using `RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)`.
   * Attach chunk metadata: `{"ticker": "AAPL", "form": "10-Q", "period_end": "2025-03-29", "section": "Part I Item 2", "accession": "0000320193-25-000057", "source_url": "..."}`. Filings have no fixed pages, so citations reference section + accession/source URL (PDF fallback keeps `page`).
4. Build `vector_indexer.py`:
   * Index chunks into a local persistent ChromaDB collection using `sentence-transformers/all-MiniLM-L6-v2`.
   * Upserts are idempotent (chunk IDs derive from the filing), and the indexer can report which accession numbers a ticker already has indexed.
5. Build `ingestion_service.py` (on-demand ingestion — the DB is **not** bulk-loaded):
   * `ensure_ticker_indexed(ticker)` is called by the agent whenever a query needs filings for a ticker. Flow: check Chroma for that ticker → if missing or stale, fetch the latest N (default 4) 10-Qs from EDGAR → parse → chunk → index → return.
   * Staleness check: compare the newest indexed accession/`filing_date` against EDGAR's submissions list (one cheap request); only download filings not already indexed. Re-check at most once per day per ticker.
   * Per-ticker lock so concurrent queries for the same ticker don't ingest twice; unknown tickers fail fast with a clear error (not in SEC `company_tickers.json`).
   * Keep the DB lean: only tickers users actually ask about are added. Optional cap/eviction of least-recently-queried non-seed tickers.
   * `seed_universe.py`: pre-seed a small configurable list of large, frequently queried companies (e.g. AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM) so the most common queries are instant. Seed tickers are never evicted.
6. Implement deterministic tools in `tools/`:
   * `stock_data_tool.py`: Pull live P/E, 52-week range, and volume via `yfinance` for US tickers (no exchange suffix; USD).
   * `financial_math_tool.py`: Perform exact ratio arithmetic (Debt/Equity, YoY Net Margin growth) in Python to eliminate LLM arithmetic hallucinations.

### Phase 2: LangGraph Orchestration & Ragas Evaluation
1. Build `agent/workflow.py`:
   * Define `AgentState` containing query, ticker, messages, retrieved chunks, and tool results.
   * Assemble nodes:
     * **Router Node:** Decides whether to query ChromaDB, call market tools, or synthesize directly.
     * **Retriever Node:** Calls `ensure_ticker_indexed(ticker)` first (instant for pre-seeded/already-ingested tickers; fetches from EDGAR on a first-time ticker), then extracts top-3 relevant context passages from ChromaDB. Emits an `ingesting <TICKER>` trace event so the UI can show progress.
     * **Tool Node:** Executes deterministic calculations.
     * **Synthesizer Node:** Generates structured research memos citing retrieved filing sections/accession numbers.
2. Build `evaluation/run_ragas_eval.py`:
   * Define 15 benchmark questions testing 10-Q earnings highlights and ratio comparisons.
   * Run evaluation against Faithfulness, Answer Relevance, and Context Precision.
   * Target: Faithfulness score $\ge 0.85$.

### Phase 3: Modern Frontend with shadcn/ui
1. Scaffold Next.js project with Tailwind CSS and TypeScript:
   ```bash
   npx create-next-app@latest frontend --typescript --tailwind --eslint --app
   cd frontend
   npx shadcn@latest init
   npx shadcn@latest add button card badge input tabs table skeleton separator scroll-area
   npm install lucide-react clsx tailwind-merge
   ```
2. Build UI views in `src/components/`:
   * `query-panel.tsx`: Ticker selection dropdown and input box for natural language research queries.
   * `tool-execution-log.tsx`: Dynamic badges (`Badge variant="secondary"`) displaying which tools the agent invoked in real time.
   * `memo-viewer.tsx`: Formatted memo displaying the Executive Summary, Key Drivers, Risks, and an expandable citation table referencing specific filing sections and EDGAR links.
3. Connect `src/lib/api.ts` to `POST http://localhost:8000/api/v1/research`.

---

## 6. Verification Checklist
- [ ] SEC EDGAR client downloads 10-Qs for target tickers with a compliant User-Agent and rate limiting.
- [x] Asking about a never-seen ticker triggers on-demand EDGAR ingestion and then answers; a repeat query skips ingestion; pre-seeded tickers answer without any EDGAR calls.
- [x] Agent routes to `yfinance` when market metrics are requested, bypassing document search when irrelevant.
- [x] Citations correctly map back to the exact 10-Q section and accession number/source URL in the parsed filings.
- [x] Ragas Faithfulness score is evaluated and documented at $\ge 0.85$. (Measured 0.978 on the 15-question benchmark with a local Qwen judge; answer relevancy 0.83, context precision 0.58 — see `backend/app/evaluation/results.json`.)
- [x] Frontend displays clean shadcn/ui cards, execution badges, and loading skeletons with zero UI glitches.
