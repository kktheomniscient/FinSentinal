from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore")

    # Any OpenAI-compatible endpoint. Default: local llama.cpp server running a Qwen model.
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "erp-brain"
    openai_api_key: str = "not-needed"
    llm_timeout: float = 900.0

    # Langfuse tracing (keys from the root .env: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL).
    # Empty keys => tracing is simply off.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""

    # Final memo only: OpenRouter (fast, free model). Empty key => memo also uses the local model.
    # Key is read from OPENROUTER_KEY in the project-root .env; never logged.
    openrouter_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    memo_model: str = "nvidia/nemotron-3.5-super-vl:free"
    memo_timeout: float = 120.0
    # Qwen "thinking" mode: slow but more accurate. Off for short structured calls, on for the memo.
    synth_thinking: bool = True
    synth_max_tokens: int = 6000
    judge_thinking: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    # Calculation extraction only needs the statement tables; sending fewer excerpts cuts prompt-reading time
    calc_statement_chunks_only: bool = False
    retrieval_k: int = 3
    retrieval_k_calc: int = 7

    # SEC requires a descriptive User-Agent with contact info: "Name email@example.com".
    # Built from EMAIL in the project-root .env; SEC_USER_AGENT overrides it. No hardcoded default.
    email: str = ""
    sec_user_agent: str = ""
    sec_max_rps: float = 5.0  # SEC limit is 10 req/s; stay well under

    raw_filings_dir: Path = BACKEND_DIR / "data" / "raw_filings"
    chroma_dir: Path = BACKEND_DIR / "data" / "chroma_db"
    chroma_collection: str = "filings"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    state_file: Path = BACKEND_DIR / "data" / "ingestion_state.json"
    filings_per_ticker: int = 4
    refresh_after_hours: float = 24.0
    # Large, frequently queried companies pre-loaded so common queries need no EDGAR calls
    seed_tickers: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"]

    chunk_size: int = 900
    chunk_overlap: int = 120

    @model_validator(mode="after")
    def _default_sec_user_agent(self):
        if not self.sec_user_agent:
            if not self.email:
                raise ValueError("Set EMAIL (or SEC_USER_AGENT) in .env: SEC EDGAR requires contact info in the User-Agent")
            self.sec_user_agent = f"FinSentinel {self.email}"
        return self


settings = Settings()
