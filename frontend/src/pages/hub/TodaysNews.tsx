import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CurrencyTag, Figures, ImpactChip, SurpriseBadge } from "../../components/news/NewsBits.tsx";
import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonText } from "../../components/ui/index.ts";
import { relativeTime } from "../../lib/format.ts";
import { type NewsEvent, ukISODate, useEvents, useToday } from "../../lib/news.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";
import { StaleFigures } from "./StaleStamp.tsx";

const TITLE = "Today's news";
const SUBTITLE = "Scheduled events for your instruments, UK time";

/** Today's news overview (1.2). The headline comes from /today, the rows from /events?mine=1. The card
 * follows the one card pattern; its "Open the News Room" control is stretched over the whole card so a tap
 * anywhere opens the News Room while the rows stay readable content (never nested links). The phone shows
 * the headline plus the top three events. */
export function TodaysNews({ className = "" }: { className?: string }) {
  const device = useDevice();
  const iso = ukISODate(new Date());
  const today = useToday();
  const events = useEvents({ from: iso, to: iso, currencies: [], impacts: [], mine: true });
  const compact = device !== "desktop";
  const limit = device === "phone" ? 3 : 6;
  const retry = () => void Promise.all([today.refetch(), events.refetch()]);
  const failed = (today.isError && !today.data) || (events.isError && !events.data);
  const offline = (today.fetchStatus === "paused" && !today.data) || (events.fetchStatus === "paused" && !events.data);
  const pending = !failed && !offline && (today.isPending || events.isPending);

  const list = events.data?.events ?? [];
  const shown = list.slice(0, limit);
  const more = list.length - shown.length;
  const updated = today.data?.last_updated_at ?? events.data?.last_updated_at ?? null;

  return (
    <Card
      title={TITLE}
      subtitle={SUBTITLE}
      className={`relative transition-[transform,border-color] duration-(--dur-quick) ease-(--ease-in-enter) has-[a:focus-visible]:border-border-strong hover:-translate-y-0.5 hover:border-border-strong active:scale-[0.99] ${className}`}
      controls={
        <Link to="/news" className={`btn btn-ghost ${failed ? "" : "after:absolute after:inset-0 after:rounded-card"}`}>
          Open the News Room
        </Link>
      }
    >
      {failed ? (
        <ErrorState title="Today's news didn't load" text={(today.error ?? events.error)?.message} onRetry={retry} />
      ) : offline ? (
        <EmptyState illustration={<CalendarEmpty />} title="You're offline" text="Today's events load when you're back online." />
      ) : pending ? (
        <SkeletonText lines={4} />
      ) : (
        <StaleFigures paths={["/api/news/today", "/api/news/events"]} dataUpdatedAt={Math.max(today.dataUpdatedAt, events.dataUpdatedAt)}>
          {today.data?.headline ? <p className="num text-body font-medium">{today.data.headline}</p> : null}
          {(today.isError || events.isError) && updated ? (
            <p role="status" className="num mt-2 text-label text-muted">
              Couldn&rsquo;t refresh · last updated {relativeTime(updated)}
            </p>
          ) : null}
          {list.length === 0 ? (
            <p className="mt-3 text-body text-muted">No high-impact news today.</p>
          ) : (
            <ul className="mt-3 flex flex-col divide-y divide-border" aria-label="Today's events">
              {shown.map((e) => (
                <EventLine key={e.id} event={e} compact={compact} />
              ))}
            </ul>
          )}
          <p className="mt-3 flex flex-wrap items-center gap-x-3 text-label text-muted">
            {more > 0 ? (
              <span>
                <span className="num">{more}</span> more in the News Room
              </span>
            ) : null}
            {updated ? <span className="num ml-auto">Updated {relativeTime(updated)}</span> : null}
          </p>
        </StaleFigures>
      )}
    </Card>
  );
}

/** One event: time · currency · name · impact chip, then forecast vs previous (and the actual once out). */
function EventLine({ event, compact }: { event: NewsEvent; compact: boolean }) {
  return (
    <li className="py-2">
      <div className={`grid items-center gap-2 ${compact ? "grid-cols-[3.25rem_minmax(0,1fr)_auto]" : "grid-cols-[3.5rem_3.25rem_minmax(0,1fr)_auto_minmax(13rem,17rem)]"}`}>
        <span className="num font-mono text-body">{event.all_day ? "All day" : event.uk_time}</span>
        {compact ? null : <CurrencyTag currency={event.currency} />}
        <span className="min-w-0">
          {compact ? <span className="num mr-1.5 font-mono text-label text-muted">{event.currency}</span> : null}
          <span className="text-body">{event.name}</span>
        </span>
        <ImpactChip impact={event.impact} compact />
        {compact ? null : <Figures event={event} />}
      </div>
      {compact ? (
        <p className="num mt-1 flex flex-wrap gap-x-3 pl-[3.75rem] text-label text-muted">
          <span>Fcst {event.forecast ?? "—"}</span>
          <span>Prev {event.previous ?? "—"}</span>
          {event.actual ? (
            <span className="text-text">
              Act {event.actual} {event.surprise ? <SurpriseBadge surprise={event.surprise} /> : null}
            </span>
          ) : null}
        </p>
      ) : null}
    </li>
  );
}
