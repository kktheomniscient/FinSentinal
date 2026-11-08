"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtDate } from "@/lib/format";
import type { Citation } from "@/lib/types";

interface Props {
  citations: Citation[];
  openTag: string | null;
  onToggle: (tag: string | null) => void;
}

export function CitationsTable({ citations, openTag, onToggle }: Props) {
  if (!citations.length) return null;
  const citedCount = citations.filter((c) => c.cited).length;
  return (
    <section aria-label="Sources" className="rise rounded-xl border bg-card shadow-sm">
      <div className="flex items-baseline justify-between border-b px-5 py-3.5">
        <h2 className="eyebrow">Sources</h2>
        <span className="text-xs text-muted-foreground">
          {citedCount} cited · {citations.length} retrieved
        </span>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16 pl-5">Tag</TableHead>
              <TableHead>Filing period</TableHead>
              <TableHead>Section</TableHead>
              <TableHead className="w-24" />
              <TableHead className="w-10 pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {citations.map((c) => {
              const open = openTag === c.tag;
              return (
                <FragmentRow key={c.tag} c={c} open={open} onToggle={() => onToggle(open ? null : c.tag)} />
              );
            })}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function FragmentRow({ c, open, onToggle }: { c: Citation; open: boolean; onToggle: () => void }) {
  return (
    <>
      <TableRow
        id={`cite-${c.tag}`}
        onClick={onToggle}
        className={`cursor-pointer scroll-mt-20 ${open ? "bg-signal-soft/50" : ""}`}
        aria-expanded={open}
      >
        <TableCell className="pl-5">
          <span className="num rounded border border-signal/40 bg-signal-soft px-1.5 py-0.5 text-[11px] font-medium text-signal">
            {c.tag}
          </span>
        </TableCell>
        <TableCell className="num whitespace-nowrap text-[13px]">
          {c.ticker} · 10-Q · {fmtDate(c.period_end)}
        </TableCell>
        <TableCell className="max-w-[28ch] truncate text-[13px] text-muted-foreground sm:max-w-[48ch]">{c.section}</TableCell>
        <TableCell>
          <Badge variant={c.cited ? "default" : "secondary"} className="h-5 text-[10px] font-normal">
            {c.cited ? "Cited" : "Retrieved"}
          </Badge>
        </TableCell>
        <TableCell className="pr-5">
          <ChevronDown className={`size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
        </TableCell>
      </TableRow>
      {open && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={5} className="whitespace-normal px-5 pb-4 pt-1">
            <p className="num rounded-md border bg-background p-3 text-[12px] leading-relaxed text-muted-foreground">
              “{c.excerpt}…”
            </p>
            <div className="num mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              {c.accession && <span>Accession {c.accession}</span>}
              {c.source_url && (
                <a
                  href={c.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-signal hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  Open on SEC EDGAR <ExternalLink className="size-3" />
                </a>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
