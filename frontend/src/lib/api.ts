import type { NodeName, Plan, ResearchResult } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type StreamEvent =
  | { event: "step"; data: { node: NodeName; detail: string; plan?: Plan | null } }
  | { event: "ingesting"; data: { ticker: string } }
  | { event: "warning"; data: { detail: string } }
  | { event: "result"; data: ResearchResult }
  | { event: "error"; data: { detail: string } };

/** POST + SSE (EventSource can't POST). Resolves when the stream closes. */
export async function streamResearch(
  body: { query: string; ticker?: string | null },
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) detail = j.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {}
    throw new Error(detail);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) onEvent({ event, data: JSON.parse(data) } as StreamEvent);
    }
  }
}

export async function fetchHealth(): Promise<{ status: string; llm_model: string } | null> {
  try {
    const r = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}
