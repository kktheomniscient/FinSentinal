import { fmtCompact, fmtPrice, fmtX } from "@/lib/format";
import type { Calc, MarketData } from "@/lib/types";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border bg-card p-3.5">
      <p className="eyebrow">{label}</p>
      <p className="num mt-1.5 text-xl font-medium leading-none">{value}</p>
      {sub && <p className="num mt-1.5 text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

function RangeBar({ low, high, price, currency }: { low: number; high: number; price: number | null; currency: string }) {
  const pct = price == null ? null : Math.max(0, Math.min(100, ((price - low) / (high - low)) * 100));
  return (
    <div className="col-span-2 rounded-lg border bg-card p-3.5 sm:col-span-3 lg:col-span-4">
      <div className="flex items-baseline justify-between">
        <p className="eyebrow">52-week range</p>
        {pct != null && <p className="num text-[11px] text-muted-foreground">{pct.toFixed(0)}% of range</p>}
      </div>
      <div className="relative mt-5 h-1.5 rounded-full bg-muted" role="img" aria-label={`Price at ${pct?.toFixed(0)} percent of 52-week range`}>
        {pct != null && (
          <>
            <div className="absolute inset-y-0 left-0 rounded-full bg-signal/35" style={{ width: `${pct}%` }} />
            <div
              className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-signal shadow"
              style={{ left: `${pct}%` }}
            />
          </>
        )}
      </div>
      <div className="num mt-2.5 flex justify-between text-xs text-muted-foreground">
        <span>{fmtPrice(low, currency)}</span>
        <span>{fmtPrice(high, currency)}</span>
      </div>
    </div>
  );
}

export function MarketGrid({ m }: { m: MarketData }) {
  const cur = m.currency ?? "USD";
  const volRatio = m.volume != null && m.avg_volume ? m.volume / m.avg_volume : null;
  return (
    <section aria-label="Live market data" className="rise">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="eyebrow">Live market</h2>
        <span className="num text-xs text-muted-foreground">
          {m.symbol}
          {m.name ? ` · ${m.name}` : ""}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Price" value={fmtPrice(m.price, cur)} />
        <Stat label="P/E trailing" value={fmtX(m.pe_trailing)} sub={m.pe_forward != null ? `Forward ${fmtX(m.pe_forward)}` : undefined} />
        <Stat label="Market cap" value={fmtCompact(m.market_cap, "$")} />
        <Stat
          label="Volume"
          value={fmtCompact(m.volume)}
          sub={volRatio != null ? `${volRatio.toFixed(2)}× avg volume` : undefined}
        />
        {m.week52_low != null && m.week52_high != null && (
          <RangeBar low={m.week52_low} high={m.week52_high} price={m.price} currency={cur} />
        )}
      </div>
    </section>
  );
}

const CALC: Record<string, { name: string; unit: string; formula: string }> = {
  net_margin: { name: "Net margin", unit: "%", formula: "net income ÷ revenue" },
  debt_to_equity: { name: "Debt / equity", unit: "×", formula: "total debt ÷ total equity" },
  yoy_growth: { name: "Year-over-year growth", unit: "%", formula: "(current − previous) ÷ |previous|" },
  yoy_net_margin_growth: { name: "Net margin change", unit: "", formula: "margin now vs. margin a year ago" },
};

export function CalcCard({ c }: { c: Calc }) {
  const meta = CALC[c.tool] ?? { name: c.tool, unit: "", formula: "" };
  const value = typeof c.result === "number" ? `${c.result}${meta.unit}` : null;
  return (
    <section aria-label="Calculation" className="rise rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="eyebrow">Calculated in Python, not by the model</h2>
          <p className="mt-2 text-sm font-medium">{meta.name}</p>
          {meta.formula && <p className="num mt-0.5 text-xs text-muted-foreground">{meta.formula}</p>}
        </div>
        {value && <p className="num text-3xl font-medium leading-none text-signal">{value}</p>}
      </div>
      <dl className="num mt-3 grid grid-cols-2 gap-x-6 gap-y-1 border-t pt-3 text-xs sm:grid-cols-4">
        {Object.entries(c.inputs).map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="truncate text-muted-foreground">{k.replace(/_/g, " ")}</dt>
            <dd>{v.toLocaleString("en-US")}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-muted-foreground">Inputs were checked to appear verbatim in the filing before the calculation ran.</p>
    </section>
  );
}
