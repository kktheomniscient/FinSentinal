export type NodeName = "router" | "retriever" | "market" | "calc" | "synthesizer" | "verifier";

export interface Plan {
  ticker: string | null;
  needs_docs: boolean;
  needs_market: boolean;
  calculations: string[];
}

export interface Step {
  node: NodeName;
  detail: string;
  at: number; // ms since the run started (client clock)
}

export interface Citation {
  tag: string;
  cited: boolean;
  ticker: string;
  period_end: string;
  section: string;
  accession: string | null;
  source_url: string | null;
  excerpt: string;
}

export interface MarketData {
  symbol: string;
  name: string | null;
  currency: string | null;
  price: number | null;
  pe_trailing: number | null;
  pe_forward: number | null;
  week52_low: number | null;
  week52_high: number | null;
  volume: number | null;
  avg_volume: number | null;
  market_cap: number | null;
}

export interface Calc {
  tool: string;
  inputs: Record<string, number>;
  result: number | Record<string, number>;
}

/** Where one figure in the memo was found. */
export interface Grounding {
  figure: string;
  kind: "filing" | "market" | "calc";
  tag: string; // S1.. | M | C1..
  field: string; // filing section, market field, or calculation input
  source_value: number;
  source_text?: string | null; // the number exactly as printed in the source
  snippet?: string | null; // surrounding text from the filing
  period_end?: string | null;
  scaled: boolean; // memo shows it in different units (e.g. $4.98 trillion for 4,975,383,019,520)
}

export interface Verification {
  numbers_checked: number;
  unverified: string[];
  grounded_ratio: number | null;
  grounding: Grounding[];
}

export interface ResearchResult {
  trace_url?: string | null;
  query: string;
  ticker: string | null;
  memo: string | null;
  error: string | null;
  citations: Citation[];
  market: MarketData | null;
  calcs: Calc[];
  notes: string[];
  verification: Verification | null;
  trace: { node: NodeName; detail: string }[];
}
