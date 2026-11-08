"""Langfuse tracing. Everything here is fail-safe: if keys are missing or Langfuse is unreachable,
the app runs exactly as before, just untraced. Secrets are never logged."""

import logging
import uuid

from app.config import settings

log = logging.getLogger("observability")

_client = None
ENABLED = False

if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url or None,
            environment="development",
        )
        ENABLED = True
    except Exception as e:  # never let tracing setup break the app
        log.warning("Langfuse disabled: %s", type(e).__name__)


def traced(name: str):
    """Decorator that records a function as a timed span inside the current trace (no-op when disabled)."""

    def deco(fn):
        if not ENABLED:
            return fn
        from langfuse import observe

        return observe(name=name, capture_input=False, capture_output=False)(fn)

    return deco


def start(query: str, ticker: str | None, tags: list[str] | None = None) -> tuple[str | None, dict]:
    """Create a trace id up front and the LangChain config that sends this run to it."""
    if not ENABLED:
        return None, {}
    try:
        from langfuse.langchain import CallbackHandler

        trace_id = _client.create_trace_id()
        handler = CallbackHandler(public_key=settings.langfuse_public_key, trace_context={"trace_id": trace_id})
        config = {
            "callbacks": [handler],
            "run_name": "finsentinel-research",
            "metadata": {
                "langfuse_tags": ["finsentinel", *(tags or [])],
                "langfuse_session_id": f"session-{uuid.uuid4().hex[:12]}",
                **({"ticker": ticker} if ticker else {}),
            },
        }
        return trace_id, config
    except Exception as e:
        log.warning("Tracing skipped for this run: %s", type(e).__name__)
        return None, {}


def trace_url(trace_id: str | None) -> str | None:
    if not (ENABLED and trace_id):
        return None
    try:
        return _client.get_trace_url(trace_id=trace_id)
    except Exception:
        return None


def score(trace_id: str | None, name: str, value: float | None, comment: str | None = None) -> None:
    if not (ENABLED and trace_id) or value is None:
        return
    try:
        _client.create_score(trace_id=trace_id, name=name, value=float(value), data_type="NUMERIC", comment=comment)
    except Exception as e:
        log.warning("Score %s not recorded: %s", name, type(e).__name__)


def finish(trace_id: str | None, state: dict) -> None:
    """Attach quality scores from the run to its trace."""
    ver = state.get("verification") or {}
    score(trace_id, "figure_grounding", ver.get("grounded_ratio"),
          comment=f"{ver.get('numbers_checked', 0)} figures checked; unverified: {ver.get('unverified') or 'none'}")


def check() -> bool:
    """True if the configured keys authenticate against Langfuse."""
    try:
        return bool(ENABLED and _client.auth_check())
    except Exception:
        return False


def flush() -> None:
    if ENABLED:
        try:
            _client.flush()
        except Exception:
            pass
