"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamResearch } from "./api";
import type { Plan, ResearchResult, Step } from "./types";

export type Status = "idle" | "running" | "done" | "error";

export function useResearch() {
  const [status, setStatus] = useState<Status>("idle");
  const [steps, setSteps] = useState<Step[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (status !== "running" || startedAt == null) return;
    const id = setInterval(() => setElapsed(Date.now() - startedAt), 250);
    return () => clearInterval(id);
  }, [status, startedAt]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
    setIngesting(null);
  }, []);

  const run = useCallback(async (q: string, ticker?: string | null) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const t0 = Date.now();
    setStatus("running");
    setSteps([]);
    setPlan(null);
    setIngesting(null);
    setResult(null);
    setError(null);
    setQuery(q);
    setStartedAt(t0);
    setElapsed(0);
    let gotResult = false;
    try {
      await streamResearch({ query: q, ticker: ticker || null }, (e) => {
        if (e.event === "step") {
          const { node, detail, plan: p } = e.data;
          if (p) setPlan(p);
          if (node === "retriever") setIngesting(null);
          setSteps((s) => [...s, { node, detail, at: Date.now() - t0 }]);
        } else if (e.event === "ingesting") {
          setIngesting(e.data.ticker);
        } else if (e.event === "result") {
          gotResult = true;
          setResult(e.data);
          setElapsed(Date.now() - t0);
          setStatus(e.data.error ? "error" : "done");
          if (e.data.error) setError(e.data.error);
        } else if (e.event === "error") {
          gotResult = true;
          setError(e.data.detail);
          setStatus("error");
        }
      }, ctrl.signal);
      if (!gotResult && !ctrl.signal.aborted) {
        setError("The connection closed before the answer arrived.");
        setStatus("error");
      }
    } catch (err) {
      if (ctrl.signal.aborted) return;
      const msg = err instanceof Error ? err.message : String(err);
      setError(
        msg === "Failed to fetch"
          ? "Can't reach the research API. Is the backend running on port 8000?"
          : msg,
      );
      setStatus("error");
    } finally {
      setIngesting(null);
    }
  }, []);

  return { status, steps, plan, ingesting, result, error, query, elapsed, run, cancel };
}
