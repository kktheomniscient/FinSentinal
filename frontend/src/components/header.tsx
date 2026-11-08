"use client";

import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";
import { ThemeToggle } from "./theme-toggle";

export function Header() {
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [model, setModel] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const ping = async () => {
      const h = await fetchHealth();
      if (!live) return;
      setHealth(h ? "online" : "offline");
      setModel(h?.llm_model ?? null);
    };
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden className="shrink-0">
            <rect width="26" height="26" rx="6" fill="var(--primary)" />
            <path d="M6 18.5 10.5 13l3.5 3L20 8" stroke="var(--primary-foreground)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            <circle cx="20" cy="8" r="2" fill="var(--signal)" />
          </svg>
          <div className="leading-tight">
            <h1 className="text-[15px] font-semibold tracking-tight">FinSentinel</h1>
            <p className="hidden text-[11px] text-muted-foreground sm:block">Due diligence grounded in SEC 10-Q filings</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="flex items-center gap-2 rounded-full border bg-card px-2.5 py-1 text-xs"
            role="status"
            aria-live="polite"
          >
            <span
              className={`size-1.5 rounded-full ${
                health === "online" ? "bg-positive" : health === "offline" ? "bg-negative" : "bg-muted-foreground animate-pulse"
              }`}
            />
            <span className="text-muted-foreground">
              {health === "online" ? (
                <>
                  API online{model && <span className="num hidden sm:inline"> · {model}</span>}
                </>
              ) : health === "offline" ? (
                "API offline"
              ) : (
                "Connecting"
              )}
            </span>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
