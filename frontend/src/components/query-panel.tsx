"use client";

import { CornerDownLeft, Loader2, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const SEED_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"];

const EXAMPLES: { label: string; q: string; ticker?: string }[] = [
  { label: "NVDA export controls", q: "What did NVIDIA say about the impact of export controls in its latest 10-Q?" },
  { label: "MSFT net margin", q: "What was Microsoft's net margin in its latest quarter?" },
  { label: "AAPL price & P/E", q: "What is Apple's current price, P/E ratio and 52-week range?" },
  { label: "META revenue growth", q: "What was Meta's year-over-year revenue growth in its latest quarter?" },
];

interface Props {
  running: boolean;
  onRun: (query: string, ticker: string | null) => void;
  onCancel: () => void;
}

export function QueryPanel({ running, onRun, onCancel }: Props) {
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const queryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        queryRef.current?.focus();
        queryRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submit = (q = query, t = ticker) => {
    if (q.trim().length < 3 || running) return;
    onRun(q.trim(), t.trim() || null);
  };

  return (
    <section aria-label="Ask a research question" className="rounded-xl border bg-card p-3 shadow-sm sm:p-4">
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="sm:w-32">
          <label htmlFor="ticker" className="sr-only">
            Ticker (optional)
          </label>
          <Input
            id="ticker"
            list="seed-tickers"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase().replace(/[^A-Z0-9.\-]/g, ""))}
            placeholder="Ticker"
            maxLength={10}
            autoComplete="off"
            spellCheck={false}
            className="num h-10 uppercase"
          />
          <datalist id="seed-tickers">
            {SEED_TICKERS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </div>
        <div className="relative min-w-0 flex-1">
          <label htmlFor="query" className="sr-only">
            Research question
          </label>
          <Input
            id="query"
            ref={queryRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about a US company's filings, ratios or live market data…"
            autoComplete="off"
            className="h-10 pr-14 text-[15px]"
          />
          <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
            ⌘K
          </kbd>
        </div>
        {running ? (
          <Button type="button" variant="outline" size="lg" className="h-10 px-4" onClick={onCancel}>
            <Square className="size-3.5 fill-current" /> Cancel
          </Button>
        ) : (
          <Button type="submit" size="lg" className="h-10 px-4" disabled={query.trim().length < 3}>
            Run research <CornerDownLeft className="size-3.5 opacity-70" />
          </Button>
        )}
      </form>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="eyebrow mr-1">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            disabled={running}
            onClick={() => {
              setQuery(ex.q);
              setTicker(ex.ticker ?? "");
              submit(ex.q, ex.ticker ?? "");
            }}
            className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-signal hover:text-foreground disabled:opacity-50"
          >
            {ex.label}
          </button>
        ))}
        {running && <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden />}
      </div>
    </section>
  );
}
