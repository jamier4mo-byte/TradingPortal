import { Minus, Plus, TrendingDown, TrendingUp } from "lucide-react";

import type { Outcome } from "../../../lib/journal.ts";

/** Win / loss / breakeven with an icon and a label: colour is never the only signal. */
export function OutcomeChip({ outcome, compact = false }: { outcome: Outcome | null | undefined; compact?: boolean }) {
  if (!outcome) return <span className="text-label text-muted">—</span>;
  const map = {
    win: { label: "Win", icon: TrendingUp, cls: "text-win border-win/40" },
    loss: { label: "Loss", icon: TrendingDown, cls: "text-loss border-loss/40" },
    breakeven: { label: "Breakeven", icon: Minus, cls: "text-breakeven border-breakeven/40" },
  }[outcome];
  const Icon = map.icon;
  return (
    <span className={`inline-flex min-h-7 items-center gap-1 rounded-pill border bg-surface-2 px-2 text-label ${map.cls}`}>
      <Icon aria-hidden className="size-3.5" strokeWidth={2} />
      {compact ? <span className="sr-only">{map.label}</span> : map.label}
    </span>
  );
}

export function SideChip({ side }: { side: "buy" | "sell" }) {
  const Icon = side === "buy" ? Plus : Minus;
  return (
    <span className="inline-flex min-h-7 items-center gap-1 rounded-pill border border-border bg-surface-2 px-2 text-label">
      <Icon aria-hidden className="size-3" strokeWidth={2.5} />
      {side === "buy" ? "Long" : "Short"}
    </span>
  );
}
