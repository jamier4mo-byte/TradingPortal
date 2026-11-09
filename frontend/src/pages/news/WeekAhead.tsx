import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CurrencyTag, ImpactChip } from "../../components/news/NewsBits.tsx";
import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, OfflineState, RefreshFailed, SkeletonCard } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { displaySymbol } from "../../lib/markets.ts";
import { dayLabel, useWeekAhead } from "../../lib/news.ts";
import { vtName } from "../../lib/vt.ts";
import { BankHolidays } from "./parts.tsx";

/** Week ahead (3.4): the key high-impact events by day with the instruments they move. The default view
 * from Sunday 18:00 UK, and a planning aid (quieter days for backtesting). */
export function WeekAheadView() {
  const q = useWeekAhead();
  if (offlinePending(q)) return <OfflineState what="The week ahead" />;
  if (q.isPending) {
    return (
      <div className="grid gap-4 tablet:grid-cols-2 laptop:grid-cols-3 desktop:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} className="h-48" />
        ))}
      </div>
    );
  }
  if (!q.data) return <ErrorState title="The week ahead didn't load" text={q.error?.message} onRetry={() => q.refetch()} />;
  const days = q.data.days;
  const total = days.reduce((n, d) => n + d.events.length, 0);
  const through = q.data.schedule_through ?? null;
  const unpublished = through === null || through < q.data.start;
  if (total === 0 && unpublished) {
    const hols = days.flatMap((d) => d.holidays ?? []);
    return (
      <Card title="Week ahead" subtitle={`${dayLabel(q.data.start)} – ${dayLabel(q.data.end)}`}>
        <div className="flex flex-col gap-3">
          <EmptyState
            illustration={<CalendarEmpty />}
            title="Next week's schedule isn't published yet"
            text="It appears here as soon as Forex Factory publishes it, usually over the weekend."
          />
          <BankHolidays holidays={hols} showDates />
        </div>
      </Card>
    );
  }
  const quietest = [...days].sort((a, b) => a.events.length - b.events.length)[0];
  return (
    <section aria-label="Week ahead" className="flex flex-col gap-3">
      {q.isError ? <RefreshFailed updatedAt={q.dataUpdatedAt} onRetry={() => q.refetch()} /> : null}
      <p className="text-body text-muted">
        <span className="num">{total}</span> high-impact {total === 1 ? "event" : "events"} from {dayLabel(q.data.start)} to {dayLabel(q.data.end)}.{" "}
        {quietest ? <>Quietest day: {dayLabel(quietest.date)}, good for backtesting or reviews.</> : null}
        {through && through < q.data.end ? <> Published up to {dayLabel(through)}.</> : null}
      </p>
      <div className="grid gap-4 tablet:grid-cols-2 laptop:grid-cols-3 desktop:grid-cols-5">
        {days.map((d) => (
          <Card key={d.date} title={d.label} subtitle={d.events.length ? `${d.events.length} high impact` : "Quiet"}>
            {(d.holidays ?? []).length ? (
              <ul className="mb-2 flex flex-col gap-1.5" aria-label={`Bank holidays on ${d.label}`}>
                {d.holidays.map((h) => (
                  <li key={`${h.currency}-${h.name}`} className="flex flex-wrap items-center gap-2 text-label text-muted">
                    <CurrencyTag currency={h.currency} />
                    <span>Bank holiday · {h.name}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {d.events.length === 0 ? (
              <p className="text-body text-muted">No high-impact events.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {d.events.map((e) => (
                  <li key={e.id}>
                    <Link to={`/news/events/${e.id}`} className="block rounded-panel border border-border bg-surface-2 p-3 transition-colors duration-(--dur-quick) hover:border-border-strong">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
                        <span className="num font-mono text-body">{e.all_day ? "All day" : e.uk_time}</span>
                        <CurrencyTag currency={e.currency} />
                        <ImpactChip impact={e.impact} compact />
                      </div>
                      <p className="mt-1.5 text-body font-medium" style={{ viewTransitionName: vtName("event", e.id) }}>
                        {e.name}
                      </p>
                      {e.instruments.length ? (
                        <p className="mt-1 text-label text-muted">
                          Moves {e.instruments.map((i) => displaySymbol(i, i)).join(", ")}
                        </p>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}
