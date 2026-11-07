import { AlertTriangle, Eye, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { ChartEmpty, OfflineGlyph } from "./Illustrations.tsx";

/** Small line illustration plus one clear next step. */
export function EmptyState({
  title,
  text,
  action,
  illustration,
  className = "",
}: {
  title: string;
  text?: string;
  action?: ReactNode;
  illustration?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center px-4 py-8 text-center ${className}`}>
      <div className="mb-4 w-[120px] text-muted">{illustration ?? <ChartEmpty />}</div>
      <p className="text-body font-medium">{title}</p>
      {text ? <p className="mt-1 max-w-sm text-body text-muted">{text}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** Explains what went wrong, in plain words, with a retry. */
export function ErrorState({
  title = "That didn't load",
  text,
  onRetry,
  className = "",
}: {
  title?: string;
  text?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div role="alert" className={`flex flex-col items-center px-4 py-8 text-center ${className}`}>
      <AlertTriangle aria-hidden className="mb-3 size-6 text-loss" strokeWidth={1.75} />
      <p className="text-body font-medium">{title}</p>
      {text ? <p className="mt-1 max-w-sm text-body text-muted">{text}</p> : null}
      {onRetry ? (
        <button type="button" onClick={onRetry} className="btn btn-secondary mt-4">
          <RefreshCw aria-hidden className="size-4" />
          Try again
        </button>
      ) : null}
    </div>
  );
}

/** "Viewing Sam's strategy · read-only". Shown when the record belongs to someone else. */
export function ReadOnlyBanner({ owner, what = "work", className = "" }: { owner: string; what?: string; className?: string }) {
  return (
    <div
      role="status"
      className={`flex min-h-11 items-center gap-2 rounded-panel border border-border bg-surface-2 px-3 text-body text-muted ${className}`}
    >
      <Eye aria-hidden className="size-4 shrink-0" strokeWidth={1.75} />
      <span>
        Viewing {owner}&rsquo;s {what}. <span className="text-text">Read-only</span>
      </span>
    </div>
  );
}

/** Cold load with no connection and nothing cached (TanStack `fetchStatus === "paused"`, see `offlinePending`
 * in lib/offline.ts): one clear line instead of a skeleton that never resolves. `what` names the thing. */
export function OfflineState({ what = "This", text, className = "" }: { what?: string; text?: string; className?: string }) {
  return (
    <EmptyState
      illustration={<OfflineGlyph className="size-8" />}
      title="You're offline"
      text={text ?? `${what} loads when you're back online.`}
      className={className}
    />
  );
}

/** Slides in when the browser goes offline. Last-loaded data stays visible. */
export function OfflineBanner({ className = "" }: { className?: string }) {
  return (
    <div
      role="status"
      className={`flex min-h-11 items-center gap-2 rounded-panel border border-border-strong bg-surface-2 px-3 text-body ${className}`}
    >
      <OfflineGlyph className="size-4 shrink-0 text-stale" />
      <span>
        You&rsquo;re offline. <span className="text-muted">Showing the last data loaded; changes will wait.</span>
      </span>
    </div>
  );
}
