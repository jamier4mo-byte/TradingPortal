import { daypart, greeting, sessionStatus, ukClockSeconds, ukDateOrdinal } from "../../lib/time.ts";
import { useNow } from "../../lib/useNow.ts";

/** "GMT" or "BST": the UK zone in force at `d`. */
function ukZone(d: Date): string {
  const part = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", timeZoneName: "short" }).formatToParts(d).find((p) => p.type === "timeZoneName");
  return part?.value === "GMT+1" ? "BST" : (part?.value ?? "GMT");
}

/** Hero greeting (1.1): the only atmospheric card. The whole greeting is the heading, in large type:
 * "Good evening, Jamie. / Today is Saturday 7th November. / Markets closed – weekend (opens Sunday 22:00)."
 * The live clock and the zone sit apart in a small box (amends, Nov 2026). The ambience follows the UK time
 * of day and the open session through data attributes that `.hero-atmosphere` reads. The clock ticks every
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
      <div className="relative flex flex-col gap-5 tablet:flex-row tablet:items-start tablet:justify-between">
        <h1 className="min-w-0 text-heading font-semibold tablet:text-hero">
          <span className="block">
            {welcomeBack ? "Welcome back" : greeting(now)}, {firstName}.
          </span>
          <span className="mt-2 block text-title font-medium text-text tablet:mt-3 tablet:text-heading">
            {welcomeBack ? `${greeting(now)}. ` : ""}Today is {ukDateOrdinal(now)}.
          </span>
          <span className="num mt-1 flex items-center gap-2 text-title font-medium text-muted tablet:text-heading">
            <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${status.open ? "bg-live" : "bg-stale"}`} />
            <span>{status.text}.</span>
          </span>
        </h1>
        <div className="shrink-0 self-start rounded-panel border border-border-strong bg-surface-2 px-3 py-2">
          <time className="num block font-mono text-title font-semibold text-text" dateTime={now.toISOString()}>
            <span className="sr-only">UK time </span>
            UK {ukClockSeconds(now)}
          </time>
          <p className="text-label text-muted">London · {ukZone(now)}</p>
        </div>
      </div>
    </section>
  );
}
