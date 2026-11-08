import json

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.agent.workflow import finish_trace, run_research, stream_research
from app import observability as obs
from app.api.v1.schemas import ResearchRequest, ResearchResponse
from app.config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "llm_model": settings.llm_model, "llm_base_url": settings.llm_base_url,
            "memo_model": settings.memo_model if settings.openrouter_key else settings.llm_model,
            "tracing": obs.ENABLED}


def _public(state: dict, query: str, trace_url: str | None = None) -> dict:
    return {
        "trace_url": trace_url,
        "query": query,
        "ticker": state.get("ticker"),
        "memo": state.get("memo"),
        "error": state.get("error"),
        "citations": state.get("citations") or [],
        "market": state.get("market"),
        "calcs": state.get("calcs") or [],
        "notes": state.get("notes") or [],
        "verification": state.get("verification"),
        "trace": [{"node": t["node"], "detail": t["detail"]} for t in state.get("trace") or []],
    }


@router.post("/research", response_model=ResearchResponse)
async def research(req: ResearchRequest):
    """Run the agent to completion and return the full result as JSON."""
    state = await run_in_threadpool(run_research, req.query, req.ticker)
    return _public(state, req.query, obs.trace_url(state.get("trace_id")))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/research/stream")
def research_stream(req: ResearchRequest):
    """Server-sent events: `step` per graph node, `ingesting`/`warning` live events, then one `result`."""

    def gen():
        state: dict = {"trace": []}
        trace_id = trace_url = None
        try:
            for mode, payload in stream_research(req.query, req.ticker):
                if mode == "meta":
                    trace_id, trace_url = payload["trace_id"], payload["trace_url"]
                    continue
                if mode == "custom":
                    yield _sse(payload.get("event", "info"), payload)
                    continue
                for node, update in payload.items():
                    update = update or {}
                    for k, v in update.items():
                        if k == "trace":
                            state["trace"] += v
                        else:
                            state[k] = v
                    for step in update.get("trace", []):
                        yield _sse("step", {"node": node, "detail": step["detail"], "plan": update.get("plan")})
            finish_trace(trace_id, state)
            yield _sse("result", _public(state, req.query, trace_url))
        except Exception as e:  # surface failures to the client instead of dropping the stream
            yield _sse("error", {"detail": f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
