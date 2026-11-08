export const fmtCompact = (n: number | null | undefined, prefix = "") => {
  if (n == null) return "—";
  const abs = Math.abs(n);
  const [d, s] = abs >= 1e12 ? [1e12, "T"] : abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : abs >= 1e3 ? [1e3, "K"] : [1, ""];
  return `${prefix}${(n / d).toFixed(d === 1 ? 0 : 2)}${s}`;
};

export const fmtPrice = (n: number | null | undefined, currency = "USD") =>
  n == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(n);

export const fmtX = (n: number | null | undefined) => (n == null ? "—" : `${n.toFixed(1)}×`);

export const fmtSeconds = (ms: number) => {
  const s = Math.floor(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
};

export const fmtDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
