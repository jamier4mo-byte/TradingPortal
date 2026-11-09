import { Bell, ChevronLeft, ChevronRight, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { Drawer, EmptyState, ErrorState, PillToggle, RefreshFailed, SkeletonText, Stagger } from "../../components/ui/index.ts";
import { relativeTime } from "../../lib/format.ts";
import { addDays, dayLabel, type Impact, mondayOf, ukISODate, useEvents, useNewsStatus } from "../../lib/news.ts";
import { ukParts } from "../../lib/time.ts";
import { useDevice, useMediaQuery } from "../../lib/useMediaQuery.ts";
import { useNow } from "../../lib/useNow.ts";
import { NextUp } from "./NextUp.tsx";
import { BankHolidays, EventGroups, extraHolidays, FilterControls, filterCount, type FilterState } from "./parts.tsx";
import { TradingDayTimeline } from "./Timeline.tsx";
import { WeekAheadView } from "./WeekAhead.tsx";

type View = "day" | "week" | "ahead";
const VIEWS = [
  { value: "day" as const, label: "Day" },
  { value: "week" as const, label: "Week" },
  { value: "ahead" as const, label: "Week ahead" },
];

/** From Sunday 18:00 UK the Week ahead is the default view (3.4). */
function defaultView(now: Date): View {
  const { weekday, hour } = ukParts(now);
  return weekday === "Sun" && hour >= 18 ? "ahead" : "day";
}

function readList(p: URLSearchParams, key: string): string[] {
  return (p.get(key) ?? "").split(",").filter(Boolean);
}

export default function NewsRoom({ initialView }: { initialView?: View }) {
  const now = useNow(60_000);
  const device = useDevice();
  const wideRows = useMediaQuery("(min-width: 1440px)");
  const compact = device !== "desktop";
  const [params, setParams] = useSearchParams();
  const today = ukISODate(now);
  const view = (params.get("view") as View | null) ?? initialView ?? defaultView(now);
  const date = params.get("date") ?? today;
  const filters: FilterState = {
    currencies: readList(params, "cur"),
    impacts: readList(params, "impact") as Impact[],
    mine: params.get("mine") === "1",
  };
  const [sheet, setSheet] = useState(false);

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    setParams(next, { replace: true });
  };
  const setFilters = (f: FilterState) => set({ cur: f.currencies.join(","), impact: f.impacts.join(","), mine: f.mine ? "1" : null });

  const range = useMemo(() => {
    if (view === "week") {
      const mon = mondayOf(date);
      return { from: mon, to: addDays(mon, 6) };
    }
    return { from: date, to: date };
  }, [view, date]);

  return (
    <Stagger screenKey="news" className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="m-0">
          <img src="/brand/newsroom-logo.png" alt="News Room" className="h-8 w-auto tablet:h-9" />
        </h1>
        <FeedStatus />
        <Link to="/settings/alerts" className="btn btn-secondary ml-auto">
          <Bell aria-hidden className="size-4" />
          <span>Alerts</span>
        </Link>
      </header>

      <NextUp compact={device === "phone"} />

      <div className="flex flex-wrap items-center gap-3">
        <PillToggle<View> value={view} onChange={(v) => set({ view: v })} options={VIEWS} label="Calendar view" />
        {view !== "ahead" ? (
          <DateNav view={view} date={date} today={today} onDate={(d) => set({ date: d === today ? null : d })} />
        ) : null}
        {view !== "ahead" && compact ? (
          <button type="button" className="btn btn-secondary ml-auto" onClick={() => setSheet(true)}>
            <SlidersHorizontal aria-hidden className="size-4" />
            Filters{filterCount(filters) ? <span className="num"> · {filterCount(filters)}</span> : null}
          </button>
        ) : null}
      </div>

      {view === "ahead" ? (
        <WeekAheadView />
      ) : (
        <div className="grid grid-cols-1 gap-4 laptop:grid-cols-12 laptop:gap-6">
          {view === "day" ? (
            <Card title="Trading day" subtitle={`${dayLabel(date)} · UK time`} className="laptop:col-span-12">
              <TradingDayTimeline date={date} isToday={date === today} />
            </Card>
          ) : null}
          {!compact ? (
            <Card title="Filters" className="laptop:col-span-4 desktop:col-span-3 laptop:self-start">
              <FilterControls value={filters} onChange={setFilters} />
            </Card>
          ) : null}
          <Card
            title={view === "day" ? (date === today ? "Today" : dayLabel(date)) : `Week of ${dayLabel(range.from)}`}
            subtitle="All times UK"
            className={compact ? "" : "laptop:col-span-8 desktop:col-span-9"}
          >
            <EventList from={range.from} to={range.to} today={today} filters={filters} compact={!wideRows} multiDay={view === "week"} onClear={() => setFilters({ currencies: [], impacts: [], mine: false })} />
          </Card>
        </div>
      )}

      <Drawer
        open={sheet}
        onOpenChange={setSheet}
        title="Filters"
        footer={
          <div className="flex gap-2">
            <button type="button" className="btn btn-ghost" onClick={() => setFilters({ currencies: [], impacts: [], mine: false })}>
              Clear all
            </button>
            <button type="button" className="btn btn-primary ml-auto" onClick={() => setSheet(false)}>
              Show events
            </button>
          </div>
        }
      >
        <FilterControls value={filters} onChange={setFilters} />
      </Drawer>
    </Stagger>
  );
}

/** ‹ [selected day or week] › and, away from today, a "Today" button back. The middle label always names the
 * day being shown (it used to read "Today" whichever day you had stepped to). */
function DateNav({ view, date, today, onDate }: { view: View; date: string; today: string; onDate: (d: string) => void }) {
  const step = view === "week" ? 7 : 1;
  const onToday = view === "day" ? date === today : mondayOf(date) === mondayOf(today);
  const label =
    view === "day"
      ? date === today
        ? `Today · ${dayLabel(date, "short")}`
        : date === addDays(today, 1)
          ? `Tomorrow · ${dayLabel(date, "short")}`
          : date === addDays(today, -1)
            ? `Yesterday · ${dayLabel(date, "short")}`
            : dayLabel(date, "short")
      : onToday
        ? `This week · from ${dayLabel(mondayOf(date), "short")}`
        : `Week of ${dayLabel(mondayOf(date), "short")}`;
  return (
    <div className="flex flex-wrap items-center gap-1">
      <button type="button" className="btn btn-ghost size-11 px-0" aria-label={view === "week" ? "Previous week" : "Previous day"} onClick={() => onDate(addDays(date, -step))}>
        <ChevronLeft aria-hidden className="size-5" />
      </button>
      <p className="num min-w-36 text-center text-body font-medium" aria-live="polite">
        {label}
      </p>
      <button type="button" className="btn btn-ghost size-11 px-0" aria-label={view === "week" ? "Next week" : "Next day"} onClick={() => onDate(addDays(date, step))}>
        <ChevronRight aria-hidden className="size-5" />
      </button>
      {onToday ? null : (
        <button type="button" className="btn btn-secondary ml-1" onClick={() => onDate(today)}>
          Today
        </button>
      )}
    </div>
  );
}

/** "Updated 12 min ago": fades when the feeds are more than 2 hours old. */
function FeedStatus() {
  const status = useNewsStatus();
  const at = status.data?.last_updated_at ?? null;
  const stale = !at || Date.now() - new Date(at).getTime() > 2 * 3600_000;
  const failing = status.data?.feeds.some((f) => f.last_status === "error");
  if (status.isPending) return null;
  return (
    <p className={`num inline-flex items-center gap-2 text-label text-muted ${stale ? "opacity-80" : ""}`}>
      <span aria-hidden className={`size-2 rounded-full ${stale ? "bg-stale" : "bg-live"}`} />
      {at ? `Updated ${relativeTime(at)}` : "Not updated yet"}
      {failing ? " · a feed is failing, the other keeps the schedule" : ""}
    </p>
  );
}

function EventList({
  from,
  to,
  today,
  filters,
  compact,
  multiDay,
  onClear,
}: {
  from: string;
  to: string;
  today: string;
  filters: FilterState;
  compact: boolean;
  multiDay: boolean;
  onClear: () => void;
}) {
  const q = useEvents({ from, to, ...filters });
  if (q.isPending && q.fetchStatus === "paused")
    return <EmptyState illustration={<CalendarEmpty />} title="You're offline" text="The calendar appears when you're back online." />;
  if (q.isPending) return <SkeletonText lines={8} />;
  if (!q.data) return <ErrorState text={q.error?.message} onRetry={() => q.refetch()} />;
  const events = q.data.events;
  const holidays = <BankHolidays holidays={extraHolidays(q.data.holidays ?? [], events)} showDates={multiDay} />;
  // Days after the published schedule are empty because Forex Factory hasn't released them yet.
  // No schedule loaded at all: anything after this week counts as not yet published.
  const through = q.data.schedule_through ?? (to > addDays(mondayOf(today), 6) ? addDays(mondayOf(today), 6) : null);
  const unpublished = through !== null && to > through;
  const notPublished = unpublished ? (
    <p role="note" className="rounded-panel border border-border p-3 text-body text-muted">
      {from > through ? (
        <>The news schedule for {multiDay ? "this week" : "this day"} isn&rsquo;t published yet.</>
      ) : (
        <>The news schedule is published up to {dayLabel(through)}; later days fill in once it&rsquo;s out.</>
      )}{" "}
      Forex Factory publishes the current week and the next one, so forecasts appear about a week ahead. Bank holidays are known in advance.
    </p>
  ) : null;
  if (events.length === 0) {
    const filtered = filterCount(filters) > 0;
    return (
      <div className="flex flex-col gap-3">
        {holidays}
        {unpublished && from > through && !filtered ? (
          notPublished
        ) : (
          <EmptyState
            illustration={<CalendarEmpty />}
            title={filtered ? "No events match these filters" : multiDay ? "No events this week yet" : "No events on this day"}
            text={filtered ? "Try fewer currencies or impact levels." : "The schedule loads from Forex Factory each hour."}
            action={
              filtered ? (
                <button type="button" className="btn btn-secondary" onClick={onClear}>
                  Clear filters
                </button>
              ) : undefined
            }
          />
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {q.isError ? <RefreshFailed updatedAt={q.dataUpdatedAt} onRetry={() => q.refetch()} /> : null}
      {holidays}
      <div className={q.isPlaceholderData || q.isError ? "opacity-60 transition-opacity duration-(--dur-standard)" : ""}>
        <EventGroups events={events} compact={compact} showDayHeadings={multiDay} />
      </div>
      {notPublished}
    </div>
  );
}
