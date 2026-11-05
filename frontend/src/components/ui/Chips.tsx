import type { ReactNode } from "react";

import { initials } from "../../lib/format.ts";

/** Tailwind needs the class names written out to keep them. One per owner token. */
export const OWNER_BG = [
  "bg-owner-0",
  "bg-owner-1",
  "bg-owner-2",
  "bg-owner-3",
  "bg-owner-4",
  "bg-owner-5",
  "bg-owner-6",
  "bg-owner-7",
];
export const OWNER_TEXT = [
  "text-owner-0",
  "text-owner-1",
  "text-owner-2",
  "text-owner-3",
  "text-owner-4",
  "text-owner-5",
  "text-owner-6",
  "text-owner-7",
];

export function ownerBg(index: number): string {
  return OWNER_BG[((index % 8) + 8) % 8];
}

/** Chip with a coloured dot: news impact, owners, tags, sessions. Colour is never the only signal. */
export function Chip({
  children,
  dot,
  dotClass = "bg-muted",
  className = "",
  onRemove,
}: {
  children: ReactNode;
  dot?: boolean;
  dotClass?: string;
  className?: string;
  onRemove?: () => void;
}) {
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-pill border border-border bg-surface-2 px-2.5 text-label text-text ${className}`}
    >
      {dot ? <span aria-hidden className={`size-1.5 rounded-full ${dotClass}`} /> : null}
      {children}
      {onRemove ? (
        <button type="button" onClick={onRemove} aria-label="Remove" className="-my-2 -mr-3 grid size-11 place-items-center rounded-pill text-muted hover:text-text">
          ×
        </button>
      ) : null}
    </span>
  );
}

/** Who logged it. Deactivated users keep their colour and get the "(deactivated)" label. */
export function OwnerChip({
  name,
  colourIndex,
  deactivated = false,
  compact = false,
}: {
  name: string;
  colourIndex: number;
  deactivated?: boolean;
  compact?: boolean;
}) {
  const label = deactivated ? `${name} (deactivated)` : name;
  return (
    <span className="inline-flex items-center gap-2 text-label text-muted" title={label}>
      <span
        aria-hidden
        className={`grid size-6 shrink-0 place-items-center rounded-full text-[10px] font-semibold text-bg ${ownerBg(colourIndex)} ${
          deactivated ? "opacity-60" : ""
        }`}
      >
        {initials(name)}
      </span>
      {compact ? <span className="sr-only">{label}</span> : <span>{label}</span>}
    </span>
  );
}

export function OwnerDot({ colourIndex, className = "" }: { colourIndex: number; className?: string }) {
  return <span aria-hidden className={`inline-block size-2 rounded-full ${ownerBg(colourIndex)} ${className}`} />;
}
