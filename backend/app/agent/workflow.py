"""LangGraph StateGraph: router -> [retriever] -> [market] -> [calc] -> synthesizer -> verifier."""

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (calc_node, market_node, retriever_node, router_node,
                             synthesizer_node, verifier_node)
from app import observability as obs
from app.agent.state import AgentState


def _after_router(state: AgentState) -> str:
    if state.get("error"):
        return END
    return "retriever" if state["plan"]["needs_docs"] else ("market" if state["plan"]["needs_market"] else "synthesizer")


def _after_retriever(state: AgentState) -> str:
    if state.get("error"):
        return END
    return "market" if state["plan"]["needs_market"] else _after_market(state)


def _after_market(state: AgentState) -> str:
    return "calc" if state["plan"].get("calculations") and state.get("chunks") else "synthesizer"


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [("router", router_node), ("retriever", retriever_node), ("market", market_node),
                     ("calc", calc_node), ("synthesizer", synthesizer_node), ("verifier", verifier_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", _after_router, ["retriever", "market", "synthesizer", END])
    g.add_conditional_edges("retriever", _after_retriever, ["market", "calc", "synthesizer", END])
    g.add_conditional_edges("market", _after_market, ["calc", "synthesizer"])
    g.add_edge("calc", "synthesizer")
    g.add_edge("synthesizer", "verifier")
    g.add_edge("verifier", END)
    return g.compile()


graph = build_graph()


def run_research(query: str, ticker: str | None = None, tags: list[str] | None = None) -> AgentState:
    trace_id, config = obs.start(query, ticker, tags)
    state = graph.invoke({"query": query, "ticker": ticker, "trace": []}, config=config)
    obs.finish(trace_id, state)
    state["trace_id"] = trace_id
    return state


def stream_research(query: str, ticker: str | None = None, tags: list[str] | None = None):
    """Yield (mode, payload): first ('meta', {trace_id, trace_url}), then ('updates'|'custom', ...) for live display."""
    trace_id, config = obs.start(query, ticker, tags)
    yield "meta", {"trace_id": trace_id, "trace_url": obs.trace_url(trace_id)}
    yield from graph.stream({"query": query, "ticker": ticker, "trace": []}, config=config, stream_mode=["updates", "custom"])


finish_trace = obs.finish
