/** Inline-SVG line illustrations in the portal's style: 1.5px strokes in the accent and muted ink. */
import type { SVGProps } from "react";

const base: SVGProps<SVGSVGElement> = {
  viewBox: "0 0 120 72",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export function ChartEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <path d="M8 60h104" className="text-border-strong" />
      <path d="M8 60V12" className="text-border-strong" />
      <path d="M16 50l18-12 16 8 18-20 16 10 20-16" className="text-accent" />
      <circle cx="104" cy="20" r="2.5" className="text-accent" fill="currentColor" stroke="none" />
      <path d="M24 24h12M24 30h8" className="text-muted" strokeDasharray="2 3" />
    </svg>
  );
}

export function ListEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <rect x="14" y="12" width="92" height="14" rx="4" className="text-border-strong" />
      <rect x="14" y="30" width="92" height="14" rx="4" className="text-border-strong" />
      <rect x="14" y="48" width="60" height="14" rx="4" className="text-accent" />
      <path d="M22 19h10M22 37h18" className="text-muted" />
      <path d="M86 55h12M92 49v12" className="text-accent" />
    </svg>
  );
}

export function PeopleEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <circle cx="44" cy="26" r="9" className="text-muted" />
      <path d="M26 58c2-10 9-15 18-15s16 5 18 15" className="text-muted" />
      <circle cx="78" cy="30" r="7" className="text-accent" />
      <path d="M66 58c1-8 6-12 12-12s11 4 12 12" className="text-accent" />
      <path d="M94 20h10M99 15v10" className="text-accent" />
    </svg>
  );
}

export function KeyEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <circle cx="40" cy="36" r="12" className="text-accent" />
      <circle cx="40" cy="36" r="4" className="text-accent" />
      <path d="M52 36h40M80 36v8M90 36v10" className="text-muted" />
      <rect x="20" y="16" width="40" height="40" rx="8" className="text-border-strong" strokeDasharray="3 4" />
    </svg>
  );
}

export function OfflineGlyph({ className = "" }: { className?: string }) {
  return (
    <svg {...base} viewBox="0 0 24 24" className={className} strokeWidth={1.75}>
      <path d="M5 12.5a9 9 0 0 1 14 0M8.5 16a4.5 4.5 0 0 1 7 0" />
      <circle cx="12" cy="19.5" r="0.75" fill="currentColor" />
      <path d="M4 4l16 16" />
    </svg>
  );
}

export function CalendarEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <rect x="22" y="12" width="76" height="52" rx="6" className="text-border-strong" />
      <path d="M22 26h76M40 6v12M80 6v12" className="text-border-strong" />
      <path d="M34 38h8M52 38h8M70 38h8M34 50h8M52 50h8" className="text-muted" strokeDasharray="2 3" />
      <circle cx="74" cy="50" r="4" className="text-accent" />
    </svg>
  );
}

export function PulseEmpty({ className = "" }: { className?: string }) {
  return (
    <svg {...base} className={className}>
      <path d="M8 40h26l6-14 8 28 8-20 6 6h50" className="text-accent" />
      <path d="M8 60h104" className="text-border-strong" />
      <path d="M20 20h14M20 14h8" className="text-muted" strokeDasharray="2 3" />
    </svg>
  );
}
