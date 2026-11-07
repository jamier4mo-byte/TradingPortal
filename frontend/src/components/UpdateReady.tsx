import { RefreshCw } from "lucide-react";

import { applyUpdate, useUpdateReady } from "../lib/offline.ts";

/** "A new version is ready · Reload": shown by the shell once a new service worker has installed and is
 * waiting. Reload hands control to it and the page reloads (main.tsx). Same quiet look as OfflineBanner. */
export function UpdateReady({ className = "" }: { className?: string }) {
  const ready = useUpdateReady();
  if (!ready) return null;
  return (
    <div role="status" className={`flex min-h-11 items-center gap-2 rounded-panel border border-border-strong bg-surface-2 pl-3 pr-1 text-body ${className}`}>
      <RefreshCw aria-hidden className="size-4 shrink-0 text-accent" strokeWidth={1.75} />
      <span>
        A new version is ready. <span className="text-muted">Reload to use it.</span>
      </span>
      <button type="button" className="btn btn-ghost ml-auto text-accent" onClick={applyUpdate}>
        Reload
      </button>
    </div>
  );
}
