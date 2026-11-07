import type { DatesSetArg, EventClickArg, EventContentArg, EventDropArg, EventInput } from "@fullcalendar/core";
import enGb from "@fullcalendar/core/locales/en-gb";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { type DateClickArg } from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { ChevronLeft, ChevronRight, Plus, Repeat } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { ConfirmDialog, type DrawerOrigin, EmptyState, ErrorState, originOf, OwnerDot, PillToggle, RefreshFailed, Skeleton, Stagger, ToggleChip, useToast } from "../../components/ui/index.ts";
import { ApiError, type PublicUser } from "../../lib/api.ts";
import { useAuth } from "../../lib/auth.tsx";
import { dur } from "../../lib/motion.ts";
import {
  type CalendarView,
  type Mode,
  type Occurrence,
  rangeLabel,
  stepDate,
  ukClockOf,
  ukWall,
  ukWallToUtc,
  useCompleteTask,
  useHiddenOwners,
  useMoveTask,
  useOccurrences,
  useShowNews,
  useTask,
  viewRange,
} from "../../lib/calendar.ts";
import { dayLabel, type NewsEvent, ukISODate, useEvents } from "../../lib/news.ts";
import { useDevice, useOnline } from "../../lib/useMediaQuery.ts";
import { useNow } from "../../lib/useNow.ts";
import { Agenda, categoryShort } from "./Agenda.tsx";
import { type Prefill, TaskDrawer } from "./TaskDrawer.tsx";

const DESKTOP_VIEWS: { value: CalendarView; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
];
const PHONE_VIEWS: { value: CalendarView; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "3day", label: "3 days" },
];
const FC_VIEW: Record<CalendarView, string> = { day: "timeGridDay", "3day": "timeGridDay", week: "timeGridWeek", month: "dayGridMonth" };
const SCOPES: { value: Mode; label: string }[] = [
  { value: "occurrence", label: "This occurrence" },
  { value: "series", label: "Whole series" },
];

function readView(raw: string | null, phone: boolean): CalendarView {
  const v = (raw ?? "") as CalendarView;
  if (phone) return v === "day" ? "day" : "3day";
  if (v === "day" || v === "month" || v === "week") return v;
  return "week";
}

/** Date as FullCalendar hands it back (the calendar runs in UTC fed with UK wall clocks): "YYYY-MM-DDTHH:mm:ss". */
function wallOf(d: Date): string {
  return d.toISOString().slice(0, 19);
}

interface DrawerState {
  open: boolean;
  occurrence: Occurrence | null;
  /** Where the tapped row sits, so the drawer grows out of it. */
  origin?: DrawerOrigin;
  prefill: Prefill | null;
}

interface PendingDrop {
  occ: Occurrence;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  revert: () => void;
}

/** /calendar: the team calendar (1.4). Week grid on desktop and tablet, a day / 3-day agenda on the phone.
 * Everyone sees everyone's tasks; you drag and edit your own (the admin anyone's). */
export default function CalendarPage() {
  const device = useDevice();
  const phone = device === "phone";
  const online = useOnline();
  const now = useNow(60_000);
  const { user } = useAuth();
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const today = ukISODate(now);
  const view = readView(params.get("view"), phone);
  const date = params.get("date") ?? today;
  const range = useMemo(() => viewRange(view, date), [view, date]);

  const set = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(params);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === "") next.delete(k);
        else next.set(k, v);
      }
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const [hidden, setHidden] = useHiddenOwners();
  const [showNews, setShowNews] = useShowNews();
  const ownersRef = useRef<PublicUser[]>([]);
  const q = useOccurrences(range.from, range.to, undefined);
  if (q.data) ownersRef.current = q.data.owners;
  const owners = q.data?.owners ?? ownersRef.current;
  const occurrences = useMemo(() => (q.data?.occurrences ?? []).filter((o) => !hidden.includes(o.owner.id)), [q.data, hidden]);
  const newsQ = useEvents({ from: range.from, to: range.to, currencies: [], impacts: ["high"], mine: false });
  const news = showNews ? (newsQ.data?.events ?? []) : [];

  const [drawer, setDrawer] = useState<DrawerState>({ open: false, occurrence: null, prefill: null });
  const seriesQ = useTask(drawer.occurrence?.recurring ? drawer.occurrence.task_id : null);
  const complete = useCompleteTask();
  const move = useMoveTask();
  const [pending, setPending] = useState<PendingDrop | null>(null);
  const [dropScope, setDropScope] = useState<Mode>("occurrence");
  const [settling, setSettling] = useState<string | null>(null);

  // ?new=1 (command palette, Hub) opens the new-task drawer.
  useEffect(() => {
    if (params.get("new") === "1") {
      setDrawer({ open: true, occurrence: null, prefill: { date: date, time: "09:00" } });
      set({ new: null });
    }
  }, [params, date, set]);

  // Keep the drawer's occurrence fresh after a save (the list refetches).
  useEffect(() => {
    if (!drawer.open || !drawer.occurrence || !q.data) return;
    const fresh = q.data.occurrences.find((o) => o.id === drawer.occurrence!.id);
    if (fresh && fresh !== drawer.occurrence) setDrawer((d) => ({ ...d, occurrence: fresh }));
  }, [q.data, drawer.open, drawer.occurrence]);

  const openNew = (prefill: Prefill) => setDrawer({ open: true, occurrence: null, prefill });
  const openOcc = (occ: Occurrence, origin?: DrawerOrigin) => setDrawer({ open: true, occurrence: occ, prefill: null, origin });

  const toggleDone = (occ: Occurrence, done: boolean) => {
    const vars = { task_id: occ.task_id, occurrence_date: occ.occurrence_date };
    complete.mutate(
      { ...vars, done },
      { onError: (err) => toast({ title: "Couldn't save that", text: err instanceof ApiError ? err.message : "The change was rolled back.", tone: "loss" }) },
    );
    toast({ title: done ? "Marked done" : "Marked not done", text: occ.title, undo: () => complete.mutate({ ...vars, done: !done }) });
  };

  const doMove = (occ: Occurrence, start_at: string, end_at: string | null, all_day: boolean, mode: Mode) => {
    const previous = { start_at: occ.start_at, end_at: occ.end_at };
    move.mutate(
      { task_id: occ.task_id, occurrence_date: occ.occurrence_date, start_at, end_at: end_at ?? undefined, mode, ...(all_day !== occ.all_day ? { all_day } : {}) },
      {
        onSuccess: () => {
          setSettling(occ.id);
          window.setTimeout(() => setSettling(null), dur.standard() * 1000);
        },
        onError: (err) => toast({ title: "Couldn't move that", text: err instanceof ApiError ? err.message : "It's back where it was.", tone: "loss" }),
      },
    );
    const when = all_day ? dayLabel(ukWall(start_at).slice(0, 10), "short") : `${dayLabel(ukWall(start_at).slice(0, 10), "short")} ${ukClockOf(start_at)}`;
    toast({
      title: mode === "series" ? "Series moved" : "Moved",
      text: `${occ.title} · ${when}`,
      undo:
        mode === "series"
          ? undefined
          : () => move.mutate({ task_id: occ.task_id, occurrence_date: occ.occurrence_date, start_at: previous.start_at, end_at: previous.end_at, mode: "occurrence" }),
    });
  };

  // ---- FullCalendar wiring (desktop and tablet) ----
  const calRef = useRef<FullCalendar>(null);
  useEffect(() => {
    const api = calRef.current?.getApi();
    if (!api || phone) return;
    const wanted = FC_VIEW[view];
    if (api.view.type !== wanted) api.changeView(wanted, date);
    else if (api.getDate().toISOString().slice(0, 10) !== date) api.gotoDate(date);
  }, [view, date, phone]);

  const fixA11y = useCallback(() => {
    // FullCalendar marks its layout tables as ARIA grids whose rows live in nested tables, which breaks the
    // grid pattern (aria-required-children/parent). They are layout, not data: make them presentational.
    // The events themselves stay focusable links with their own text.
    for (const el of document.querySelectorAll<HTMLElement>('.fc [role="grid"], .fc [role="rowgroup"], .fc [role="row"], .fc [role="gridcell"], .fc [role="columnheader"], .fc [role="presentation"] table')) {
      el.setAttribute("role", "presentation");
    }
    // FullCalendar's inner scroll regions need keyboard access (WCAG 2.1.1); it doesn't add tabindex itself.
    for (const el of document.querySelectorAll<HTMLElement>(".fc .fc-scroller")) {
      if (el.scrollHeight > el.clientHeight + 1 && el.tabIndex < 0) {
        el.tabIndex = 0;
        el.setAttribute("role", "region");
        el.setAttribute("aria-label", "Timetable");
      }
    }
  }, []);

  const events = useMemo<EventInput[]>(() => {
    const tasks: EventInput[] = occurrences.map((o) => ({
      id: o.id,
      title: o.title,
      start: ukWall(o.start_at),
      end: o.end_at ? ukWall(o.end_at) : undefined,
      allDay: o.all_day,
      editable: o.can_edit && online,
      durationEditable: false,
      classNames: ["tp-ev", `tp-owner-${((o.owner.colour_index % 8) + 8) % 8}`, o.done ? "tp-done" : "", settling === o.id ? "tp-settle" : "", o.can_edit ? "" : "tp-readonly"].filter(Boolean),
      extendedProps: { occ: o },
    }));
    // Releases often share a minute (NFP, unemployment, earnings at 13:30): one marker per minute.
    const byMinute = new Map<string, NewsEvent[]>();
    for (const ev of news) {
      const key = ev.all_day ? `${ev.uk_date}:all` : ukWall(ev.at).slice(0, 16);
      byMinute.set(key, [...(byMinute.get(key) ?? []), ev]);
    }
    const markers: EventInput[] = [...byMinute.values()].map((group) => {
      const ev = group[0];
      const currencies = [...new Set(group.map((g) => g.currency))].join(", ");
      return {
        id: `news-${ev.id}`,
        title: `High impact · ${group.map((g) => `${g.currency} ${g.name}`).join(", ")}`,
        start: ukWall(ev.at),
        end: ev.all_day ? undefined : ukWall(new Date(new Date(ev.at).getTime() + 15 * 60_000)),
        allDay: ev.all_day,
        display: "background",
        classNames: ["tp-news"],
        extendedProps: { news: ev, newsCount: group.length, newsCurrencies: currencies },
      };
    });
    return [...tasks, ...markers];
  }, [occurrences, news, online, settling]);

  const onDateClick = (info: DateClickArg) => {
    openNew({ date: info.dateStr.slice(0, 10), time: info.allDay ? undefined : info.dateStr.slice(11, 16), allDay: info.allDay });
  };
  const onEventClick = (info: EventClickArg) => {
    const occ = info.event.extendedProps.occ as Occurrence | undefined;
    if (occ) openOcc(occ, originOf(info.el));
  };
  const onEventDrop = (info: EventDropArg) => {
    const occ = info.event.extendedProps.occ as Occurrence | undefined;
    if (!occ || !info.event.start) return info.revert();
    const all_day = info.event.allDay;
    const start_at = ukWallToUtc(wallOf(info.event.start));
    const end_at = info.event.end && !all_day ? ukWallToUtc(wallOf(info.event.end)) : null;
    if (occ.recurring) {
      setDropScope("occurrence");
      setPending({ occ, start_at, end_at, all_day, revert: info.revert });
      return;
    }
    doMove(occ, start_at, end_at, all_day, "series");
  };
  const onDatesSet = (_arg: DatesSetArg) => fixA11y();

  const renderEvent = (arg: EventContentArg) => {
    const ev = arg.event.extendedProps.news as NewsEvent | undefined;
    if (ev) {
      const count = arg.event.extendedProps.newsCount as number;
      const currencies = arg.event.extendedProps.newsCurrencies as string;
      return (
        <span className="tp-news-label" title={arg.event.title}>
          <span className="tp-news-h">H</span>
          <span className="sr-only">High impact news</span> <span className="num">{ev.uk_time}</span> {currencies}
          {count > 1 ? <span className="num text-muted">×{count}</span> : null}
        </span>
      );
    }
    const occ = arg.event.extendedProps.occ as Occurrence;
    const month = arg.view.type === "dayGridMonth";
    return (
      <div className={`tp-ev-body ${month ? "tp-ev-row" : ""}`} title={`${occ.title} · ${occ.owner.display_name} · ${occ.category_label}${occ.done ? " · done" : ""}`}>
        <span className="tp-ev-head">
          <OwnerDot colourIndex={occ.owner.colour_index} className="shrink-0" />
          {arg.timeText ? <span className="num tp-ev-time">{arg.timeText}</span> : null}
          {occ.recurring ? <Repeat aria-hidden className="size-3 shrink-0 text-muted" /> : null}
          {occ.done ? <span className="sr-only">done</span> : null}
        </span>
        <span className={`tp-ev-title ${occ.done ? "line-through" : ""}`}>{occ.title}</span>
        {month ? null : (
          <span className="tp-ev-meta">
            {occ.owner.display_name} · {categoryShort(occ.category)}
          </span>
        )}
      </div>
    );
  };

  // ---- states ----
  const loading = q.isPending && q.fetchStatus !== "paused";
  const offlineNoData = q.isPending && q.fetchStatus === "paused";
  const failed = !q.data && q.isError;
  const isAdmin = user?.role === "admin";
  const otherOwners = owners.some((o) => o.id !== user?.id);
  const me: PublicUser | null = user ? { id: user.id, display_name: user.display_name, label: user.label, status: user.status, colour_index: user.colour_index } : null;

  return (
    <Stagger screenKey="calendar" className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-heading font-semibold">Calendar</h1>
          <p className="num text-label text-muted">{rangeLabel(view, date)} · UK time</p>
        </div>
        <button type="button" className="btn btn-primary ml-auto" onClick={() => openNew({ date: date >= today ? date : today, time: "09:00" })} disabled={!online}>
          <Plus aria-hidden className="size-4" />
          New task
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Previous ${view === "3day" ? "3 days" : view}`} onClick={() => set({ date: stepDate(view, date, -1) })}>
            <ChevronLeft aria-hidden className="size-5" />
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => set({ date: null })} disabled={range.from <= today && today <= range.to}>
            Today
          </button>
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Next ${view === "3day" ? "3 days" : view}`} onClick={() => set({ date: stepDate(view, date, 1) })}>
            <ChevronRight aria-hidden className="size-5" />
          </button>
        </div>
        <PillToggle<CalendarView> value={view} onChange={(v) => set({ view: v })} options={phone ? PHONE_VIEWS : DESKTOP_VIEWS} label="Calendar view" />
        <ToggleChip pressed={showNews} onClick={() => setShowNews(!showNews)} label="Show high-impact news">
          <span aria-hidden className="size-2 rounded-full bg-impact-high" />
          News <span className="text-label">High</span>
        </ToggleChip>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Owners">
        <span className="mr-1 text-label text-muted">Owners</span>
        {owners.map((o) => {
          const on = !hidden.includes(o.id);
          return (
            <ToggleChip key={o.id} pressed={on} onClick={() => setHidden(on ? [...hidden, o.id] : hidden.filter((id) => id !== o.id))} label={o.label}>
              <OwnerDot colourIndex={o.colour_index} />
              {o.display_name}
            </ToggleChip>
          );
        })}
        {!isAdmin && otherOwners ? <span className="ml-auto text-label text-muted">Drag or edit your own tasks; other people&rsquo;s are view-only.</span> : null}
      </div>

      <section className="card p-3 tablet:p-4" aria-label="Team calendar">
        {q.data && q.isError ? <RefreshFailed updatedAt={q.dataUpdatedAt} onRetry={() => q.refetch()} /> : null}
        {!online && q.data ? (
          <p role="status" className="mb-3 text-label text-muted">
            Offline · showing the last tasks loaded; drag and edit are paused.
          </p>
        ) : null}
        {offlineNoData ? (
          <EmptyState illustration={<CalendarEmpty />} title="You're offline" text="The calendar appears when you're back online." />
        ) : loading ? (
          <div className="flex flex-col gap-3" role="status" aria-label="Loading">
            <div className="grid grid-cols-7 gap-2">
              {Array.from({ length: 7 }, (_, i) => (
                <Skeleton key={i} className="h-6" />
              ))}
            </div>
            <Skeleton className="h-[52dvh]" />
          </div>
        ) : failed ? (
          <ErrorState text={q.error instanceof Error ? q.error.message : undefined} onRetry={() => q.refetch()} />
        ) : phone ? (
          <Agenda from={range.from} to={range.to} occurrences={occurrences} news={news} today={today} onOpen={openOcc} onToggleDone={toggleDone} onNew={(d) => openNew({ date: d, time: "09:00" })} online={online} />
        ) : (
          <>
            {occurrences.length === 0 ? (
              <EmptyState
                illustration={<CalendarEmpty />}
                className="py-4"
                title={view === "day" ? "Nothing planned this day" : view === "week" ? "Nothing planned this week" : "Nothing planned this month"}
                text={hidden.length ? "Some owners are hidden by the chips above." : "Tap a slot or add a task."}
                action={
                  <button type="button" className="btn btn-secondary" onClick={() => openNew({ date: date >= today ? date : today, time: "09:00" })} disabled={!online}>
                    + New task
                  </button>
                }
              />
            ) : null}
            <div className="tp-calendar" data-view={view}>
              <FullCalendar
                ref={calRef}
                plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                locale={enGb}
                timeZone="UTC"
                initialView={FC_VIEW[view]}
                initialDate={date}
                headerToolbar={false}
                firstDay={1}
                now={ukWall(now)}
                nowIndicator
                height={view === "month" ? "auto" : device === "tablet" ? 620 : 700}
                expandRows
                slotDuration="00:30:00"
                slotLabelInterval="01:00"
                scrollTime="06:00:00"
                slotLabelFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
                eventTimeFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
                dayHeaderFormat={view === "month" ? { weekday: "short" } : { weekday: "short", day: "numeric" }}
                allDayText="All day"
                fixedWeekCount={false}
                dayMaxEvents={3}
                moreLinkClick="popover"
                navLinks={false}
                editable={online}
                eventStartEditable={online}
                eventDurationEditable={false}
                longPressDelay={350}
                eventLongPressDelay={350}
                selectLongPressDelay={350}
                eventOrder="start,-duration,title"
                events={events}
                eventContent={renderEvent}
                eventClick={onEventClick}
                dateClick={onDateClick}
                eventDrop={onEventDrop}
                datesSet={onDatesSet}
                eventsSet={fixA11y}
              />
            </div>
          </>
        )}
      </section>

      <TaskDrawer
        open={drawer.open}
        onOpenChange={(open) => setDrawer((d) => ({ ...d, open }))}
        occurrence={drawer.occurrence}
        prefill={drawer.prefill}
        origin={drawer.origin}
        seriesRule={seriesQ.data?.rrule ?? null}
        me={me}
        online={online}
      />

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open && pending) {
            pending.revert();
            setPending(null);
          }
        }}
        title="Move a repeating task"
        text={pending ? `Move “${pending.occ.title}” for this occurrence only, or shift the whole series?` : undefined}
        confirmLabel="Move"
        onConfirm={() => {
          if (!pending) return;
          const p = pending;
          setPending(null);
          doMove(p.occ, p.start_at, p.end_at, p.all_day, dropScope);
        }}
      >
        <div className="mt-4">
          <PillToggle<Mode> value={dropScope} onChange={setDropScope} options={SCOPES} label="Apply the move to" size="sm" />
        </div>
      </ConfirmDialog>
    </Stagger>
  );
}
