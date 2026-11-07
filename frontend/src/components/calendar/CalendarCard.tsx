/** Team calendar card contents for the Hub (1.4 on the Hub, 1.6 layout order).
 *
 * Contract (shared between the Hub and the calendar build): a self-contained component that fetches
 * its own data and renders the card *contents* only; the Hub supplies the `Card` wrapper, title and
 * the "Open calendar" control. `variant="week"` is the desktop week strip; `variant="agenda"` is the
 * phone's day / 3-day agenda list. It carries its own loading, empty, error and offline states.
 *
 * Deliberately light: no FullCalendar here (that lives in the lazy /calendar page), just lib/calendar.ts. */
import { Check, Undo2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api.ts";
import { datesBetween, groupByDay, type Occurrence, ukClockOf, useCompleteTask, useOccurrences } from "../../lib/calendar.ts";
import { addDays, dayLabel, mondayOf, ukISODate } from "../../lib/news.ts";
import { useStaleness } from "../../lib/offline.ts";
import { useOnline } from "../../lib/useMediaQuery.ts";
import { StaleStamp } from "../../pages/hub/StaleStamp.tsx";
import { useNow } from "../../lib/useNow.ts";
import { CalendarEmpty } from "../ui/Illustrations.tsx";
import { EmptyState, ErrorState, OwnerDot, Skeleton, useToast } from "../ui/index.ts";

const MAX_PER_DAY = 3;

export default function CalendarCard({ variant }: { variant: "week" | "agenda" }) {
  const now = useNow(60_000);
  const online = useOnline();
  const today = ukISODate(now);
  const from = variant === "week" ? mondayOf(today) : today;
  const to = variant === "week" ? addDays(from, 6) : addDays(today, 2);
  const q = useOccurrences(from, to);
  // Offline, or served from the service worker's cache: dim the figures and stamp "Last updated HH:MM".
  const stale = useStaleness(["/api/calendar/occurrences"], q.dataUpdatedAt);

  if (q.isPending && q.fetchStatus === "paused") {
    return <EmptyState illustration={<CalendarEmpty />} title="You're offline" text="Your tasks show when you're back online." />;
  }
  if (q.isPending) {
    return variant === "week" ? (
      <div className="grid grid-cols-7 gap-1.5" role="status" aria-label="Loading">
        {Array.from({ length: 7 }, (_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    ) : (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
    );
  }
  if (!q.data) return <ErrorState text={q.error instanceof Error ? q.error.message : undefined} onRetry={() => q.refetch()} />;

  const items = q.data.occurrences;
  if (items.length === 0) {
    return (
      <EmptyState
        illustration={<CalendarEmpty />}
        className="py-5"
        title={variant === "week" ? "Nothing planned this week" : "Nothing planned for the next three days"}
        text="Plan a backtest session, a review or an admin task."
        action={
          <Link to="/calendar?new=1" className="btn btn-secondary">
            + New task
          </Link>
        }
      />
    );
  }
  const days = groupByDay(items, datesBetween(from, to));
  return (
    <div className={`flex flex-col gap-2 ${stale.stale ? "[&_.num]:opacity-70" : ""}`} data-stale={stale.stale || undefined}>
      <StaleStamp s={stale} className="-mt-3" />
      {variant === "week" ? <WeekStrip days={days} today={today} /> : <AgendaList days={days} today={today} online={online} />}
    </div>
  );
}

/** Mon–Sun strip of this week: today highlighted, tasks as small rows with owner dots, done struck. */
function WeekStrip({ days, today }: { days: { date: string; items: Occurrence[] }[]; today: string }) {
  return (
    <ol className="grid grid-cols-7 gap-1.5" aria-label="This week">
      {days.map(({ date, items }) => {
        const isToday = date === today;
        const [, , d] = date.split("-");
        return (
          <li key={date} className="min-w-0">
            <Link
              to={`/calendar?view=day&date=${date}`}
              aria-label={`${dayLabel(date)}${items.length ? `, ${items.length} ${items.length === 1 ? "task" : "tasks"}` : ", nothing planned"}`}
              className={`flex min-h-24 flex-col gap-1 rounded-panel border p-1.5 transition-colors duration-(--dur-quick) hover:border-border-strong ${
                isToday ? "border-accent bg-accent-soft" : "border-border bg-surface-2"
              }`}
            >
              <span className="flex items-baseline justify-between gap-1 px-0.5">
                <span className="text-label text-muted">{dayLabel(date, "short").slice(0, 3)}</span>
                <span className={`num text-body ${isToday ? "font-semibold" : "font-medium"}`}>{Number(d)}</span>
              </span>
              {items.slice(0, MAX_PER_DAY).map((o) => (
                <span key={o.id} className={`flex items-center gap-1 truncate text-label ${o.done ? "text-muted line-through" : ""}`} title={`${o.title} · ${o.owner.display_name}`}>
                  <OwnerDot colourIndex={o.owner.colour_index} className="size-1.5 shrink-0" />
                  <span className="truncate">{o.title}</span>
                </span>
              ))}
              {items.length > MAX_PER_DAY ? <span className="num px-0.5 text-label text-muted">+{items.length - MAX_PER_DAY} more</span> : null}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

/** Today and the next two days as a list with a Done button per task. */
function AgendaList({ days, today, online }: { days: { date: string; items: Occurrence[] }[]; today: string; online: boolean }) {
  const complete = useCompleteTask();
  const { toast } = useToast();
  const toggle = (o: Occurrence, done: boolean) => {
    const vars = { task_id: o.task_id, occurrence_date: o.occurrence_date };
    complete.mutate(
      { ...vars, done },
      { onError: (err) => toast({ title: "Couldn't save that", text: err instanceof ApiError ? err.message : "The change was rolled back.", tone: "loss" }) },
    );
    toast({ title: done ? "Marked done" : "Marked not done", text: o.title, undo: () => complete.mutate({ ...vars, done: !done }) });
  };
  return (
    <div className="flex flex-col gap-3">
      {days.map(({ date, items }) => (
        <section key={date} aria-label={date === today ? "Today" : dayLabel(date)}>
          <h3 className="mb-1.5 text-label font-medium text-muted">{date === today ? "Today" : dayLabel(date)}</h3>
          {items.length === 0 ? (
            <p className="text-label text-muted">Nothing planned</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {items.map((o) => {
                const time = o.all_day ? "All day" : ukClockOf(o.start_at);
                const can = o.can_edit && online;
                return (
                  <li key={o.id} className={`flex items-center gap-2 rounded-panel border border-border bg-surface-2 pl-3`}>
                    <Link to={`/calendar?view=day&date=${date}`} className="flex min-h-11 min-w-0 flex-1 items-center gap-3" aria-label={`${o.title}, ${time}, ${o.owner.display_name}${o.done ? ", done" : ""}`}>
                      <OwnerDot colourIndex={o.owner.colour_index} className="shrink-0" />
                      <span className="num w-14 shrink-0 text-label text-muted">{time}</span>
                      <span className={`truncate text-body ${o.done ? "line-through text-muted" : ""}`}>{o.title}</span>
                    </Link>
                    <button
                      type="button"
                      className="btn btn-ghost size-11 shrink-0 px-0"
                      aria-label={o.done ? `Mark ${o.title} not done` : `Mark ${o.title} done`}
                      aria-pressed={o.done}
                      onClick={() => toggle(o, !o.done)}
                      disabled={!can}
                      title={can ? undefined : o.can_edit ? "You're offline" : `Only ${o.owner.display_name} or the admin can mark this done`}
                    >
                      {o.done ? <Undo2 aria-hidden className="size-4" /> : <Check aria-hidden className="size-4" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
