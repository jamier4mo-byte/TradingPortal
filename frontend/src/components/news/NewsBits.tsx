import type { Impact, NewsEvent, Surprise } from "../../lib/news.ts";

const IMPACT_DOT: Record<Impact, string> = {
  high: "bg-impact-high",
  medium: "bg-impact-medium",
  low: "bg-impact-low",
  holiday: "bg-stale",
  none: "bg-stale",
};
const IMPACT_LABEL: Record<Impact, string> = { high: "High", medium: "Med", low: "Low", holiday: "Holiday", none: "None" };

/** Impact uses the reserved red/orange/yellow and always carries its High/Med/Low label. */
export function ImpactChip({ impact, compact = false, className = "" }: { impact: Impact; compact?: boolean; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-pill border border-border bg-surface-2 text-label text-text ${
        compact ? "min-h-6 px-2" : "min-h-7 px-2.5"
      } ${className}`}
    >
      <span aria-hidden className={`size-2 rounded-full ${IMPACT_DOT[impact]}`} />
      <span>
        {IMPACT_LABEL[impact]}
        <span className="sr-only"> impact</span>
      </span>
    </span>
  );
}

export function ImpactDot({ impact, className = "" }: { impact: Impact; className?: string }) {
  return <span aria-hidden className={`inline-block size-2 rounded-full ${IMPACT_DOT[impact]} ${className}`} />;
}

/** Actual vs forecast. Surprise colours are their own tokens (never win/loss), always with ▲/▼ and the
 * difference; the words come from the event type ("Better than forecast"). */
export function SurpriseBadge({ surprise, withWords = false }: { surprise: Surprise; withWords?: boolean }) {
  const up = surprise.direction === "up";
  const down = surprise.direction === "down";
  const tone = up ? "text-surprise-up" : down ? "text-surprise-down" : "text-muted";
  const arrow = up ? "▲" : down ? "▼" : "＝";
  return (
    <span className={`num inline-flex items-center gap-1 text-label ${tone}`}>
      <span aria-hidden>{arrow}</span>
      <span>{surprise.direction === "inline" ? "in line" : surprise.diff_text}</span>
      <span className={withWords ? "text-muted" : "sr-only"}>
        {withWords ? " · " : ", "}
        {surprise.wording}
      </span>
    </span>
  );
}

/** Actual · Forecast · Previous, in a fixed grid so columns line up in a list. */
export function Figures({ event, flip = false, className = "" }: { event: NewsEvent; flip?: boolean; className?: string }) {
  return (
    <dl className={`grid grid-cols-3 gap-x-3 text-label ${className}`}>
      <div className="min-w-0">
        <dt className="text-muted">Actual</dt>
        <dd className="num text-body text-text">
          {event.actual ? (
            <span key={event.actual} className={`inline-block ${flip ? "flip-in" : ""}`}>
              {event.actual}
            </span>
          ) : (
            <span className="text-muted">{event.released ? "pending" : "—"}</span>
          )}
          {event.surprise ? (
            <span className="block">
              <SurpriseBadge surprise={event.surprise} />
            </span>
          ) : null}
        </dd>
      </div>
      <div className="min-w-0">
        <dt className="text-muted">Forecast</dt>
        <dd className="num text-body">{event.forecast ?? <span className="text-muted">—</span>}</dd>
      </div>
      <div className="min-w-0">
        <dt className="text-muted">Previous</dt>
        <dd className="num text-body">
          {event.previous ?? <span className="text-muted">—</span>}
          {event.revised ? <span className="block text-muted">rev. {event.revised}</span> : null}
        </dd>
      </div>
    </dl>
  );
}

export function CurrencyTag({ currency }: { currency: string }) {
  return <span className="num inline-flex min-w-10 justify-center rounded-panel border border-border px-1.5 font-mono text-label text-text">{currency}</span>;
}
