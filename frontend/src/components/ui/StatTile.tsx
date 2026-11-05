import type { ReactNode } from "react";

/** Headline number with a small sentence-case label. Sign or icon always accompanies colour. */
export function StatTile({
  label,
  value,
  unit,
  tone = "neutral",
  hint,
  className = "",
}: {
  label: string;
  value: string | number;
  unit?: string;
  tone?: "neutral" | "win" | "loss" | "breakeven";
  hint?: ReactNode;
  className?: string;
}) {
  const toneClass = tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : tone === "breakeven" ? "text-breakeven" : "";
  return (
    <div className={`rounded-panel border border-border bg-surface-2 p-3 ${className}`}>
      <p className="text-label text-muted">{label}</p>
      <p className={`num mt-1 text-heading font-semibold leading-none ${toneClass}`}>
        {value}
        {unit ? <span className="ml-1 text-body font-normal text-muted">{unit}</span> : null}
      </p>
      {hint ? <p className="mt-1 text-label text-muted">{hint}</p> : null}
    </div>
  );
}
