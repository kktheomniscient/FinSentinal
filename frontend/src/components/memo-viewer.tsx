"use client";

import { AlertTriangle, Check, ChevronDown, Copy, ShieldCheck } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { Status } from "@/lib/use-research";
import type { Citation, Grounding, Verification } from "@/lib/types";
import { fmtDate, fmtSeconds } from "@/lib/format";

type Block =
  | { kind: "h"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "p"; text: string };

function parse(md: string): Block[] {
  const blocks: Block[] = [];
  let list: string[] | null = null;
  let para: string[] = [];
  const flushPara = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push({ kind: "ul", items: list });
    list = null;
  };
  for (const raw of md.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flushPara();
      flushList();
    } else if (/^#{1,4}\s/.test(line)) {
      flushPara();
      flushList();
      blocks.push({ kind: "h", text: line.replace(/^#{1,4}\s+/, "") });
    } else if (/^[*\-•]\s+/.test(line)) {
      flushPara();
      (list ??= []).push(line.replace(/^[*\-•]\s+/, ""));
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}

const TOKEN = /(\*\*[^*]+\*\*|\[(?:S\d+|M|C\d*)\])/g;
const NUMBER = /(\$?\d(?:[\d,]*\d)?(?:\.\d+)?)/g;
const CHIP =
  "num mx-0.5 inline-flex h-[19px] -translate-y-px items-center rounded border px-1.5 align-middle font-sans text-[11px] font-medium leading-none";

function TagChip({ tag, onCite }: { tag: string; onCite: (tag: string) => void }) {
  if (tag.startsWith("S")) {
    return (
      <button
        type="button"
        onClick={() => onCite(tag)}
        title={`Open source ${tag}`}
        className={`${CHIP} border-signal/40 bg-signal-soft text-signal transition-colors hover:border-signal`}
      >
        {tag}
      </button>
    );
  }
  return (
    <span title={tag === "M" ? "Live market data (yfinance)" : "Calculated in Python"} className={`${CHIP} bg-muted text-muted-foreground`}>
      {tag}
    </span>
  );
}

interface InlineProps {
  text: string;
  onCite: (tag: string) => void;
  figures: Map<string, number>;
  onFigure: (i: number) => void;
  grounding: Grounding[];
}

function Inline({ text, onCite, figures, onFigure, grounding }: InlineProps) {
  return (
    <>
      {text.split(TOKEN).map((part, i) => {
        if (!part) return null;
        if (part.startsWith("**")) return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        const m = /^\[(S\d+|M|C\d*)\]$/.exec(part);
        if (m) return <TagChip key={i} tag={m[1]} onCite={onCite} />;
        return (
          <Fragment key={i}>
            {part.split(NUMBER).map((seg, j) => {
              const idx = figures.get(seg);
              if (idx == null) return <Fragment key={j}>{seg}</Fragment>;
              const g = grounding[idx];
              return (
                <button
                  key={j}
                  type="button"
                  onClick={() => onFigure(idx)}
                  title={`Traced to ${g.tag} · ${g.field}. Click for the evidence.`}
                  className="cursor-pointer rounded-sm underline decoration-signal/70 decoration-dotted underline-offset-[5px] transition-colors hover:bg-signal-soft"
                >
                  {seg}
                </button>
              );
            })}
          </Fragment>
        );
      })}
    </>
  );
}

function Highlight({ text, needle }: { text: string; needle?: string | null }) {
  const i = needle ? text.indexOf(needle) : -1;
  if (i < 0 || !needle) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded-sm bg-signal/25 px-0.5 font-medium text-foreground">{needle}</mark>
      {text.slice(i + needle.length)}
    </>
  );
}

const KIND_LABEL = { filing: "SEC filing", market: "Live market data", calc: "Python calculation" } as const;

function GroundingPanel({
  v,
  citations,
  focus,
  onCite,
}: {
  v: Verification;
  citations: Citation[];
  focus: number | null;
  onCite: (tag: string) => void;
}) {
  return (
    <div className="rise border-t bg-surface/40 px-5 py-4 sm:px-7" id="grounding-panel">
      <p className="eyebrow">Where each figure comes from</p>
      {v.unverified.length > 0 && (
        <div role="alert" className="mt-3 flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-xs">
          <AlertTriangle className="mt-px size-4 shrink-0 text-warning" aria-hidden />
          <p>
            <span className="font-medium">No matching source found for </span>
            <span className="num">{v.unverified.join(", ")}</span>
            <span className="text-muted-foreground">. Treat these as unconfirmed.</span>
          </p>
        </div>
      )}
      <ul className="mt-3 divide-y rounded-lg border bg-card">
        {v.grounding.map((g, i) => {
          const cite = g.kind === "filing" ? citations.find((c) => c.tag === g.tag) : undefined;
          return (
            <li
              key={g.figure}
              id={`ground-${i}`}
              className={`scroll-mt-24 px-4 py-3 ${focus === i ? "bg-signal-soft/60" : ""}`}
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span className="num min-w-20 text-sm font-medium">{g.figure}</span>
                <span className="text-muted-foreground" aria-hidden>→</span>
                <TagChip tag={g.tag} onCite={onCite} />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{KIND_LABEL[g.kind]}</span>
                {g.scaled && <span className="rounded border px-1.5 py-px text-[10px] text-muted-foreground">units converted</span>}
              </div>
              <p className="mt-1.5 text-[12.5px] text-muted-foreground">
                {g.kind === "filing" ? (
                  <>
                    <span className="num">
                      {cite?.ticker ?? ""} 10-Q{g.period_end ? ` · period ended ${fmtDate(g.period_end)}` : ""}
                    </span>
                    <span> · {g.field}</span>
                  </>
                ) : g.kind === "market" ? (
                  <>
                    {g.field}: <span className="num">{g.source_text ?? g.source_value}</span>
                  </>
                ) : (
                  <>
                    {g.field} = <span className="num">{g.source_value}</span>
                  </>
                )}
              </p>
              {g.snippet && (
                <p className="num mt-2 rounded-md border bg-background px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
                  …<Highlight text={g.snippet} needle={g.source_text} />…
                </p>
              )}
              {g.kind === "filing" && cite?.source_url && (
                <a href={cite.source_url} target="_blank" rel="noreferrer" className="num mt-1.5 inline-block text-[11px] text-signal hover:underline">
                  Open filing on SEC EDGAR ↗
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface Props {
  status: Status;
  memo: string | null;
  query: string;
  verification: Verification | null;
  citations: Citation[];
  traceUrl?: string | null;
  elapsed: number;
  onCite: (tag: string) => void;
}

export function MemoViewer({ status, memo, query, verification, citations, traceUrl, elapsed, onCite }: Props) {
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const grounding = useMemo(() => verification?.grounding ?? [], [verification]);
  const figures = useMemo(() => new Map(grounding.map((g, i) => [g.figure, i])), [grounding]);

  const copy = async () => {
    if (!memo) return;
    try {
      await navigator.clipboard.writeText(memo);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  const onFigure = (i: number) => {
    setOpen(true);
    setFocus(i);
    requestAnimationFrame(() => document.getElementById(`ground-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  };

  const v = verification;
  const ok = !!v && v.unverified.length === 0;
  const grounded = v ? v.numbers_checked - v.unverified.length : 0;

  return (
    <article aria-label="Research memo" className="overflow-hidden rounded-xl border bg-card shadow-sm" aria-busy={status === "running"}>
      <header className="flex items-start justify-between gap-4 border-b px-5 py-4 sm:px-7">
        <div className="min-w-0">
          <p className="eyebrow">Research memo</p>
          <h2 className="mt-1.5 text-[15px] font-medium leading-snug text-balance">{query}</h2>
        </div>
        {memo && (
          <button
            type="button"
            onClick={copy}
            className="flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            {copied ? <Check className="size-3.5 text-positive" /> : <Copy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </header>

      <div className="px-5 py-5 sm:px-7 sm:py-6">
        {memo ? (
          <div className="rise max-w-[68ch] font-serif text-[16.5px] leading-[1.7]">
            {parse(memo).map((b, i) =>
              b.kind === "h" ? (
                <h3 key={i} className="mb-2 mt-7 font-sans text-[11px] font-semibold uppercase tracking-[0.1em] text-signal first:mt-0">
                  {b.text}
                </h3>
              ) : b.kind === "ul" ? (
                <ul key={i} className="my-2 list-disc space-y-1.5 pl-5 marker:text-muted-foreground">
                  {b.items.map((it, j) => (
                    <li key={j}>
                      <Inline text={it} onCite={onCite} figures={figures} onFigure={onFigure} grounding={grounding} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p key={i} className="my-2">
                  <Inline text={b.text} onCite={onCite} figures={figures} onFigure={onFigure} grounding={grounding} />
                </p>
              ),
            )}
          </div>
        ) : (
          <div className="space-y-3" aria-hidden>
            <div className="sweep-bar relative h-0.5 w-full overflow-hidden rounded bg-muted" />
            <Skeleton className="mt-5 h-3 w-24" />
            <Skeleton className="h-4 w-full max-w-[68ch]" />
            <Skeleton className="h-4 w-[92%] max-w-[62ch]" />
            <Skeleton className="h-4 w-[70%] max-w-[48ch]" />
            <Skeleton className="mt-6 h-3 w-28" />
            <Skeleton className="h-4 w-[88%] max-w-[60ch]" />
            <Skeleton className="h-4 w-[60%] max-w-[42ch]" />
          </div>
        )}
      </div>

      {memo && v && open && <GroundingPanel v={v} citations={citations} focus={focus} onCite={onCite} />}

      {memo && (
        <footer className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t bg-surface/60 px-5 py-2.5 sm:px-7">
          {v && v.numbers_checked > 0 ? (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              aria-controls="grounding-panel"
              className={`-ml-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors hover:bg-accent ${ok ? "text-positive" : "text-warning"}`}
            >
              {ok ? <ShieldCheck className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
              <span className="num">
                {grounded}/{v.numbers_checked}
              </span>
              figures traced to sources
              <span className="text-muted-foreground">· {open ? "Hide" : "Show"} evidence</span>
              <ChevronDown className={`size-3.5 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="size-3.5" /> No figures to verify
            </span>
          )}
          <span className="num flex items-center gap-3 text-[11px] text-muted-foreground">
            {traceUrl && (
              <a href={traceUrl} target="_blank" rel="noreferrer" className="text-signal hover:underline" title="Open this run's trace in Langfuse">
                Trace ↗
              </a>
            )}
            Answered in {fmtSeconds(elapsed)}
          </span>
        </footer>
      )}
    </article>
  );
}
