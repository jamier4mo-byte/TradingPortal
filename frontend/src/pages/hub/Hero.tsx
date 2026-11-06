import { daypart, greeting, sessionStatus, ukClockSeconds, ukDateOrdinal } from "../../lib/time.ts";
import { useNow } from "../../lib/useNow.ts";

/** Hero greeting (1.1): the only atmospheric card. The ambience follows the UK time of day and the open
 * session through data attributes that `.hero-atmosphere` reads (Engaging touches). The clock ticks every
 * second here only. */
export function Hero({ firstName, welcomeBack, className = "" }: { firstName: string; welcomeBack: boolean; className?: string }) {
  const now = useNow(1000);
  const status = sessionStatus(now);
  return (
    <section
      aria-label="Greeting"
      data-daypart={daypart(now)}
      data-session={status.session}
      className={`relative overflow-hidden rounded-card border border-border bg-surface-1 p-5 tablet:p-8 ${className}`}
    >
      <div aria-hidden className="hero-atmosphere pointer-events-none absolute inset-0" />
      <div className="relative">
        <h1 className="text-heading font-semibold tablet:text-hero">
          {welcomeBack ? "Welcome back" : greeting(now)}, {firstName}
        </h1>
        <p className="mt-2 text-body text-muted">
          {welcomeBack ? `${greeting(now)}. ` : ""}Today is {ukDateOrdinal(now)}
        </p>
        <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-body text-muted">
          <span className="num inline-flex items-center gap-2">
            <span aria-hidden className={`size-2 rounded-full ${status.open ? "bg-live" : "bg-stale"}`} />
            {status.text}
          </span>
          <time className="num font-mono text-text" dateTime={now.toISOString()}>
            <span className="sr-only">UK time </span>
            UK {ukClockSeconds(now)}
          </time>
        </p>
      </div>
    </section>
  );
}
