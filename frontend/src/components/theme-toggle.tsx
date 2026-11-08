"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

type Choice = "system" | "light" | "dark";

// The saved choice lives in localStorage; useSyncExternalStore keeps SSR ("system") and hydration consistent.
const listeners = new Set<() => void>();
const read = (): Choice => {
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
};
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => void listeners.delete(cb);
};

function apply(c: Choice) {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  if (c !== "system") root.classList.add(c);
  try {
    if (c === "system") localStorage.removeItem("theme");
    else localStorage.setItem("theme", c);
  } catch {}
  listeners.forEach((l) => l());
}

export function ThemeToggle() {
  const choice = useSyncExternalStore(subscribe, read, () => "system" as Choice);
  const next: Choice = choice === "system" ? "light" : choice === "light" ? "dark" : "system";
  const Icon = choice === "light" ? Sun : choice === "dark" ? Moon : Monitor;
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`Theme: ${choice}. Switch to ${next}.`}
      title={`Theme: ${choice}`}
      onClick={() => apply(next)}
    >
      <Icon className="size-4" />
    </Button>
  );
}
