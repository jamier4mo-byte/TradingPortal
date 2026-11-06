import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CurrencyTag, ImpactChip } from "../../components/news/NewsBits.tsx";
import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, RefreshFailed, SkeletonCard } from "../../components/ui/index.ts";
import { displaySymbol } from "../../lib/markets.ts";
import { dayLabel, useWeekAhead } from "../../lib/news.ts";
import { vtName } from "../../lib/vt.ts";

/** Week ahead (3.4): the key high-impact events by day with the instruments they move. The default view
 * from Sunday 18:00 UK, and a planning aid for the team calendar (quieter days for backtesting). */
export function WeekAheadView() {
  const q = useWeekAhead();
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
  if (total === 0) {
    return (
      <Card title="Week ahead" subtitle={`${dayLabel(q.data.start)} – ${dayLabel(q.data.end)}`}>
        <EmptyState illustration={<CalendarEmpty />} title="No high-impact events scheduled" text="The schedule for next week appears once Forex Factory publishes it, usually by Sunday evening." />
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
      </p>
      <div className="grid gap-4 tablet:grid-cols-2 laptop:grid-cols-3 desktop:grid-cols-5">
        {days.map((d) => (
          <Card key={d.date} title={d.label} subtitle={d.events.length ? `${d.events.length} high impact` : "Quiet"}>
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
