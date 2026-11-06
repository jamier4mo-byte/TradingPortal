import { Check } from "lucide-react";
import { type ReactNode, useId } from "react";

/** Toggle chip for multi-select filters: aria-pressed, a ✓ when on (never colour alone), 44px tall. */
export function ToggleChip({ pressed, onClick, children, label }: { pressed: boolean; onClick: () => void; children: ReactNode; label?: string }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onClick}
      className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-pill border px-3 text-body transition-colors duration-(--dur-quick) ${
        pressed ? "border-accent bg-accent-soft text-text" : "border-border-strong bg-surface-2 text-muted hover:text-text"
      }`}
    >
      {pressed ? <Check aria-hidden className="size-3.5" strokeWidth={2.5} /> : null}
      {children}
    </button>
  );
}

/** On/off switch (role="switch"). The thumb slides with the spring token; the description is linked
 * with aria-describedby rather than folded into the name. */
export function Switch({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string }) {
  const descId = useId();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-describedby={description ? descId : undefined}
      onClick={() => onChange(!checked)}
      className="flex min-h-11 items-center gap-3 text-left"
    >
      <span aria-hidden className={`relative h-6 w-10 shrink-0 rounded-pill border transition-colors duration-(--dur-quick) ${checked ? "border-accent bg-accent" : "border-border-input bg-surface-2"}`}>
        <span
          className={`absolute top-0.5 left-0.5 size-[18px] rounded-full transition-transform duration-(--dur-standard) ease-(--ease-spring) ${
            checked ? "translate-x-4 bg-on-accent" : "bg-muted"
          }`}
        />
      </span>
      <span className="min-w-0" aria-hidden>
        <span className="block text-body">{label}</span>
        {description ? (
          <span id={descId} className="block text-label text-muted">
            {description}
          </span>
        ) : null}
      </span>
    </button>
  );
}

/** "Couldn't refresh": a background refetch failed but earlier data is still on screen, faded. */
export function RefreshFailed({ updatedAt, onRetry }: { updatedAt?: string | number | null; onRetry: () => void }) {
  const when =
    updatedAt === null || updatedAt === undefined
      ? null
      : new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" }).format(new Date(updatedAt));
  return (
    <p role="status" className="flex min-h-11 flex-wrap items-center gap-x-3 rounded-panel border border-border-strong bg-surface-2 px-3 text-body">
      <span>
        Couldn&rsquo;t refresh{when ? <span className="num text-muted"> · last updated {when}</span> : null}
      </span>
      <button type="button" className="btn btn-ghost ml-auto" onClick={onRetry}>
        Retry
      </button>
    </p>
  );
}
