"""Run the golden benchmark through the agent and score it with Ragas.

Metrics: Faithfulness, Answer Relevancy, Context Precision (with reference), plus a deterministic
key-fact hit rate. Judge = the same local OpenAI-compatible model (thinking off by default).

Usage:  python -m app.evaluation.run_ragas_eval [--limit N] [--ids 1,9,14] [--out results.json]
"""

import argparse
import asyncio
import json
import sys
import types
from pathlib import Path

# ragas 0.4.x imports a module removed from newer langchain-community; stub it (we never use Vertex).
_m = types.ModuleType("langchain_community.chat_models.vertexai")
_m.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules.setdefault(_m.__name__, _m)

from openai import AsyncOpenAI  # noqa: E402
from ragas.embeddings.base import BaseRagasEmbedding  # noqa: E402
from ragas.llms.base import llm_factory  # noqa: E402
from ragas.metrics.collections import AnswerRelevancy, ContextPrecisionWithReference, Faithfulness  # noqa: E402

from app import observability as obs  # noqa: E402
from app.agent.workflow import run_research  # noqa: E402
from app.config import settings  # noqa: E402

BENCH = Path(__file__).with_name("benchmark_data.json")


class STEmbeddings(BaseRagasEmbedding):
    """sentence-transformers embeddings (same model as the vector store) for Answer Relevancy."""

    def __init__(self, model_name: str = settings.embedding_model):
        super().__init__()
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_text(self, text, **kw):
        return self.model.encode(text).tolist()

    async def aembed_text(self, text, **kw):
        return await asyncio.to_thread(self.embed_text, text)


def build_judges():
    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.openai_api_key, timeout=settings.llm_timeout)
    llm = llm_factory(
        settings.llm_model, client=client, temperature=0, max_tokens=2000,
        extra_body={"chat_template_kwargs": {"enable_thinking": settings.judge_thinking}},
    )
    return (
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=STEmbeddings()),
        ContextPrecisionWithReference(llm=llm),
    )


def contexts_of(state: dict) -> list[str]:
    ctx = [c["text"] for c in state.get("chunks") or []]
    for c in state.get("calcs") or []:
        ctx.append(f"Deterministic calculation {c['tool']} with inputs {c['inputs']} = {c['result']}")
    return ctx


def key_fact_hit(answer: str, keys: list[str]) -> bool:
    a = answer.lower().replace(",", "")
    return any(k.lower().replace(",", "") in a for k in keys)


async def score(item, state, judges):
    faith, rel, prec = judges
    answer, ctx = state.get("memo", ""), contexts_of(state)
    out = {"faithfulness": None, "answer_relevancy": None, "context_precision": None}
    if not answer or not ctx:
        return out
    for name, coro in [
        ("faithfulness", faith.ascore(user_input=item["question"], response=answer, retrieved_contexts=ctx)),
        ("answer_relevancy", rel.ascore(user_input=item["question"], response=answer)),
        ("context_precision", prec.ascore(user_input=item["question"], reference=item["ground_truth"], retrieved_contexts=ctx)),
    ]:
        try:
            out[name] = float((await coro).value)
        except Exception as e:  # a judge failure must not sink the whole run
            out[name] = None
            out[f"{name}_error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


async def main(args):
    items = json.loads(BENCH.read_text())
    if args.ids:
        wanted = {int(i) for i in args.ids.split(",")}
        items = [i for i in items if i["id"] in wanted]
    if args.limit:
        items = items[: args.limit]
    judges = build_judges()
    rows = []
    for item in items:
        state = await asyncio.to_thread(run_research, item["question"], None, ["eval"])  # ticker=None exercises the router
        scores = await score(item, state, judges)
        row = {
            "id": item["id"], "category": item["category"], "question": item["question"],
            "routed_ticker": state.get("ticker"), "expected_ticker": item["ticker"],
            "answer": state.get("memo") or state.get("error"),
            "key_fact_hit": key_fact_hit(state.get("memo", ""), item["key_facts"]),
            "verifier_grounded_ratio": (state.get("verification") or {}).get("grounded_ratio"),
            **scores,
        }
        tid = state.get("trace_id")  # attach the Ragas scores to the Langfuse trace of this answer
        for k in ("faithfulness", "answer_relevancy", "context_precision"):
            obs.score(tid, f"ragas_{k}", row[k])
        obs.score(tid, "key_fact_hit", float(row["key_fact_hit"]))
        rows.append(row)
        print(f"[{row['id']:>2}] {row['category']:<11} ticker={row['routed_ticker']:<5} fact={row['key_fact_hit']!s:<5} "
              f"faith={row['faithfulness']} rel={row['answer_relevancy']} prec={row['context_precision']}", flush=True)
        Path(args.out).write_text(json.dumps(rows, indent=2))  # incremental save

    summary = {
        "n": len(rows),
        "faithfulness": mean(r["faithfulness"] for r in rows),
        "answer_relevancy": mean(r["answer_relevancy"] for r in rows),
        "context_precision": mean(r["context_precision"] for r in rows),
        "key_fact_hit_rate": round(sum(r["key_fact_hit"] for r in rows) / max(len(rows), 1), 3),
        "router_ticker_accuracy": round(sum(r["routed_ticker"] == r["expected_ticker"] for r in rows) / max(len(rows), 1), 3),
        "faithfulness_target_0.85_met": (mean(r["faithfulness"] for r in rows) or 0) >= 0.85,
    }
    Path(args.out).write_text(json.dumps({"summary": summary, "results": rows}, indent=2))
    obs.flush()
    print("\nSUMMARY", json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids")
    ap.add_argument("--out", default=str(Path(__file__).with_name("results.json")))
    asyncio.run(main(ap.parse_args()))
