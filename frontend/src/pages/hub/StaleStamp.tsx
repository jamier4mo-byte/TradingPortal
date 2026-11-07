import type { ReactNode } from "react";

import { type Staleness, useStaleness } from "../../lib/offline.ts";

/** Stale figures (Foundations: Stale and paused data). Offline, or data the service worker served from
 * its cache: a `--color-stale` dot and "Last updated HH:MM" (UK) sit under the card title, and every
 * `.num` inside fades to 70%. Fresh data renders the children untouched. */
export function StaleFigures({ paths, dataUpdatedAt, children, className = "" }: { paths: string[]; dataUpdatedAt?: number | null; children: ReactNode; className?: string }) {
  const s = useStaleness(paths, dataUpdatedAt);
  return (
    <>
      <StaleStamp s={s} />
      <div className={`${s.stale ? "[&_.num]:opacity-70" : ""} transition-opacity duration-(--dur-standard) ${className}`} data-stale={s.stale || undefined}>
        {children}
      </div>
    </>
  );
}

/** The stamp alone, for cards that place it themselves. */
export function StaleStamp({ s, className = "-mt-3 mb-3" }: { s: Staleness; className?: string }) {
  if (!s.stale) return null;
  return (
    <p role="status" className={`num flex items-center gap-1.5 text-label text-muted ${className}`}>
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-stale" />
      {s.label ?? "Offline · showing the last data loaded"}
    </p>
  );
}
