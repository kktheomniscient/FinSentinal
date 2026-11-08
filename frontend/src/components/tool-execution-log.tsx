"use client";

import { Check, CircleDashed, Loader2, MinusCircle, XCircle } from "lucide-react";
import type { Status } from "@/lib/use-research";
import { fmtSeconds } from "@/lib/format";
import type { NodeName, Plan, Step } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

const LABEL: Record<NodeName, string> = {
  router: "Route question",
  retriever: "Retrieve filings",
  market: "Market data",
  calc: "Calculate",
  synthesizer: "Write memo",
  verifier: "Verify figures",
};
const TOOL: Record<NodeName, string> = {
  router: "router",
  retriever: "chromadb",
  market: "yfinance",
  calc: "math",
  synthesizer: "llm",
  verifier: "check",
};

function pipeline(plan: Plan | null): NodeName[] {
  if (!plan) return ["router"];
  return [
    "router",
    ...(plan.needs_docs ? (["retriever"] as NodeName[]) : []),
    ...(plan.needs_market ? (["market"] as NodeName[]) : []),
    ...(plan.calculations?.length && plan.needs_docs ? (["calc"] as NodeName[]) : []),
    "synthesizer",
    "verifier",
  ];
}

interface Props {
  status: Status;
  steps: Step[];
  plan: Plan | null;
  ingesting: string | null;
  elapsed: number;
}

export function ToolExecutionLog({ status, steps, plan, ingesting, elapsed }: Props) {
  const nodes = pipeline(plan);
  const done = new Map(steps.map((s) => [s.node, s]));
  const activeIdx = status === "running" ? nodes.findIndex((n) => !done.has(n)) : -1;

  return (
    <section aria-label="Agent execution log" className="rounded-xl border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="eyebrow">Execution trace</h2>
        <span className="num text-xs text-muted-foreground" aria-live="off">
          {status === "idle" && steps.length === 0 ? "—" : fmtSeconds(elapsed)}
        </span>
      </div>
      {status === "idle" && steps.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">
          Each step the agent takes appears here as it runs: routing, retrieval from SEC filings, live market calls,
          deterministic math, and fact verification.
        </p>
      ) : (
        <ol className="divide-y">
          {nodes.map((n, i) => {
            const s = done.get(n);
            const active = i === activeIdx;
            const skipped = !s && status !== "running";
            const failed = s && /failed|skipped/i.test(s.detail);
            return (
              <li key={n} className={`rise flex gap-3 px-4 py-3 ${skipped ? "opacity-45" : ""}`}>
                <span className="mt-0.5 shrink-0">
                  {s ? (
                    failed ? (
                      <XCircle className="size-4 text-warning" aria-label="Skipped" />
                    ) : (
                      <Check className="size-4 text-positive" aria-label="Done" />
                    )
                  ) : active ? (
                    <Loader2 className="size-4 animate-spin text-signal" aria-label="Running" />
                  ) : skipped ? (
                    <MinusCircle className="size-4 text-muted-foreground" aria-label="Not run" />
                  ) : (
                    <CircleDashed className="size-4 text-muted-foreground" aria-label="Pending" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-medium ${!s && !active ? "text-muted-foreground" : ""}`}>{LABEL[n]}</span>
                    <Badge variant="secondary" className="num h-5 px-1.5 text-[10px] font-normal">
                      {TOOL[n]}
                    </Badge>
                  </div>
                  {s ? (
                    <p className="num mt-1 break-words text-[11.5px] leading-relaxed text-muted-foreground">{s.detail}</p>
                  ) : active ? (
                    <p className="mt-1 text-[11.5px] text-muted-foreground">
                      {n === "retriever" && ingesting
                        ? `Fetching ${ingesting} 10-Qs from SEC EDGAR (first time only)…`
                        : n === "synthesizer"
                          ? "Writing the memo from the sources. Usually under 30 seconds; a few minutes if it falls back to the local model."
                          : "Working…"}
                    </p>
                  ) : skipped ? (
                    <p className="mt-1 text-[11.5px] text-muted-foreground">
                      {n === "calc" ? "Skipped: no filing data to calculate from" : "Not needed for this question"}
                    </p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
