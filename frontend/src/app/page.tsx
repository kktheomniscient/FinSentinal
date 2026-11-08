"use client";

import { AlertCircle, Info } from "lucide-react";
import { useCallback, useState } from "react";
import { CitationsTable } from "@/components/citations-table";
import { Header } from "@/components/header";
import { CalcCard, MarketGrid } from "@/components/metrics-grid";
import { MemoViewer } from "@/components/memo-viewer";
import { QueryPanel, SEED_TICKERS } from "@/components/query-panel";
import { ToolExecutionLog } from "@/components/tool-execution-log";
import { useResearch } from "@/lib/use-research";

function Notes({ notes }: { notes: string[] }) {
  return (
    <aside role="note" className="rise flex gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4">
      <Info className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
      <div className="min-w-0">
        <p className="text-sm font-medium">Limits of this answer</p>
        <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export default function Page() {
  const r = useResearch();
  const [openTag, setOpenTag] = useState<string | null>(null);
  const running = r.status === "running";
  const started = r.status !== "idle" || r.steps.length > 0;
  const result = r.result;

  const run = useCallback(
    (q: string, t: string | null) => {
      setOpenTag(null);
      r.run(q, t);
    },
    [r.run], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const onCite = useCallback((tag: string) => {
    setOpenTag(tag);
    requestAnimationFrame(() => document.getElementById(`cite-${tag}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }, []);

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:px-6 sm:py-6">
        <QueryPanel running={running} onRun={run} onCancel={r.cancel} />

        {!started ? (
          <div className="rise mt-10 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
            <div className="max-w-xl">
              <h2 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
                Ask about any US-listed company. Get a memo that cites its filings.
              </h2>
              <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
                The agent reads SEC 10-Q filings, pulls live prices, and does ratio math in code so figures are never
                guessed. Every number in the answer is checked against its source.
              </p>
            </div>
            <div className="rounded-xl border bg-card p-4">
              <p className="eyebrow">Ready instantly</p>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {SEED_TICKERS.map((t) => (
                  <span key={t} className="num rounded-md border bg-background px-2 py-1 text-xs">
                    {t}
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                Any other US ticker works too. Its latest four 10-Qs are fetched from SEC EDGAR the first time you ask,
                which adds about 15 seconds once.
              </p>
            </div>
          </div>
        ) : (
          <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="flex min-w-0 flex-col gap-5">
              {r.status === "error" && !result?.memo ? (
                <div role="alert" className="rise flex gap-3 rounded-xl border border-destructive/40 bg-destructive/5 p-4">
                  <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" />
                  <div>
                    <p className="text-sm font-medium">This question couldn&apos;t be answered</p>
                    <p className="mt-1 text-sm text-muted-foreground">{r.error}</p>
                  </div>
                </div>
              ) : (
                <>
                  {result?.market && <MarketGrid m={result.market} />}
                  {!!result?.notes?.length && <Notes notes={result.notes} />}
                  {result?.calcs?.map((c) => <CalcCard key={c.tool} c={c} />)}
                  <MemoViewer
                    status={r.status}
                    memo={result?.memo ?? null}
                    query={r.query}
                    verification={result?.verification ?? null}
                    elapsed={r.elapsed}
                    citations={result?.citations ?? []}
                    traceUrl={result?.trace_url}
                    onCite={onCite}
                  />
                  {result && <CitationsTable citations={result.citations} openTag={openTag} onToggle={setOpenTag} />}
                </>
              )}
            </div>
            <aside className={`lg:sticky lg:top-[72px] lg:order-none ${running ? "order-first" : ""}`}>
              <ToolExecutionLog status={r.status} steps={r.steps} plan={r.plan} ingesting={r.ingesting} elapsed={r.elapsed} />
            </aside>
          </div>
        )}
      </main>
      <footer className="mx-auto w-full max-w-[1400px] px-4 pb-6 pt-2 text-[11px] text-muted-foreground sm:px-6">
        Research aid only, not investment advice. Filings from SEC EDGAR; quotes from Yahoo Finance via yfinance.
      </footer>
    </>
  );
}
