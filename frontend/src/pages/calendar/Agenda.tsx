import { Check, Repeat, Undo2 } from "lucide-react";
import { type PointerEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { type DrawerOrigin, EmptyState, originOf, OwnerDot } from "../../components/ui/index.ts";
import { CATEGORIES, datesBetween, groupByDay, type Occurrence, ukClockOf, ukDateOf } from "../../lib/calendar.ts";
import { dayLabel, type NewsEvent } from "../../lib/news.ts";

const REVEAL = 96; // px the row slides before a swipe counts as "done"

export function categoryShort(c: Occurrence["category"]): string {
  return CATEGORIES.find((x) => x.value === c)?.short ?? "Oth";
}

/** One task as an agenda row. On touch screens, swipe right to mark it done; the Done button is always
 * there too (gestures are shortcuts, never the only way). The row itself opens the task. */
export function AgendaRow({
  occ,
  onOpen,
  onToggleDone,
  online,
}: {
  occ: Occurrence;
  onOpen: (o: Occurrence, origin?: DrawerOrigin) => void;
  onToggleDone: (o: Occurrence, done: boolean) => void;
  online: boolean;
}) {
  const [dx, setDx] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ x: number; y: number; horizontal: boolean | null } | null>(null);
  const canToggle = occ.can_edit && online;

  const onDown = (e: PointerEvent) => {
    if (e.pointerType !== "touch" || !canToggle) return;
    start.current = { x: e.clientX, y: e.clientY, horizontal: null };
  };
  const onMove = (e: PointerEvent) => {
    const s = start.current;
    if (!s) return;
    const mx = e.clientX - s.x;
    const my = e.clientY - s.y;
    if (s.horizontal === null && Math.hypot(mx, my) > 8) s.horizontal = Math.abs(mx) > Math.abs(my);
    if (s.horizontal) {
      setDragging(true);
      setDx(Math.max(0, Math.min(REVEAL + 24, mx)));
    }
  };
  const onUp = () => {
    if (!start.current) return;
    const swiped = dx >= REVEAL;
    start.current = null;
    setDragging(false);
    setDx(0);
    if (swiped) onToggleDone(occ, !occ.done);
  };

  const time = occ.all_day ? "All day" : `${ukClockOf(occ.start_at)}${occ.end_at ? `–${ukClockOf(occ.end_at)}` : ""}`;
  const label = `${occ.title}, ${time}, ${occ.owner.display_name}${occ.done ? ", done" : ""}`;

  return (
    <li className="relative overflow-hidden rounded-panel border border-border bg-surface-2">
      <div className={`absolute inset-y-0 left-0 flex items-center pl-3 text-body text-text ${dx === 0 && !dragging ? "invisible" : ""}`} aria-hidden>
        <Check className="size-4" /> <span className="ml-1">{occ.done ? "Not done" : "Done"}</span>
      </div>
      <div
        className={`relative flex min-h-14 touch-pan-y items-center gap-2 bg-surface-2 pr-1 pl-3 ${dragging ? "" : "transition-transform duration-(--dur-standard) ease-(--ease-spring)"} ${occ.done ? "opacity-70" : ""}`}
        style={{ transform: `translateX(${dx}px)` }}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
      >
        <button type="button" className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-left" onClick={(e) => onOpen(occ, originOf(e.currentTarget))} aria-label={label}>
          <OwnerDot colourIndex={occ.owner.colour_index} className="size-2.5 shrink-0" />
          <span className="num w-[5.5rem] shrink-0 text-label text-muted">{time}</span>
          <span className="min-w-0 flex-1">
            <span className={`block truncate text-body ${occ.done ? "line-through" : ""}`}>{occ.title}</span>
            <span className="block truncate text-label text-muted">
              {occ.owner.display_name} · {categoryShort(occ.category)}
              {occ.recurring ? (
                <>
                  {" "}
                  · <Repeat aria-hidden className="inline size-3 align-[-1px]" /> <span className="sr-only">repeats</span>
                </>
              ) : null}
            </span>
          </span>
        </button>
        <button
          type="button"
          className={`btn btn-ghost size-11 shrink-0 px-0 ${occ.done ? "text-muted" : ""}`}
          aria-label={occ.done ? `Mark ${occ.title} not done` : `Mark ${occ.title} done`}
          aria-pressed={occ.done}
          onClick={() => onToggleDone(occ, !occ.done)}
          disabled={!canToggle}
          title={canToggle ? undefined : occ.can_edit ? "You're offline" : `Only ${occ.owner.display_name} or the admin can mark this done`}
        >
          {occ.done ? <Undo2 aria-hidden className="size-4" /> : <Check aria-hidden className="size-4" />}
        </button>
      </div>
    </li>
  );
}

/** More than two high-impact releases in a day collapse into one row that opens the News Room for that day. */
function NewsSummaryRow({ date, events }: { date: string; events: NewsEvent[] }) {
  const first = events[0];
  return (
    <li>
      <Link to={`/news?view=day&date=${date}`} className="flex min-h-11 items-center gap-3 rounded-panel border border-dashed border-border px-3 text-label text-muted hover:text-text">
        <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-impact-high" />
        <span className="num w-[5.5rem] shrink-0">from {first.all_day ? "all day" : first.uk_time}</span>
        <span className="min-w-0 flex-1 truncate">
          <span className="font-semibold text-text">H</span> <span className="sr-only">High impact</span> · <span className="num">{events.length}</span> high-impact releases · News Room
        </span>
      </Link>
    </li>
  );
}

/** A high-impact news event as a quiet row in the agenda: impact colour plus the "High" label, never colour alone. */
function NewsRow({ ev }: { ev: NewsEvent }) {
  return (
    <li className="flex min-h-11 items-center gap-3 rounded-panel border border-dashed border-border px-3 text-label text-muted">
      <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-impact-high" />
      <span className="num w-[5.5rem] shrink-0">{ev.all_day ? "All day" : ev.uk_time}</span>
      <span className="min-w-0 flex-1 truncate">
        <span className="font-semibold text-text">H</span> <span className="sr-only">High impact</span> · <span className="font-mono">{ev.currency}</span> {ev.name}
      </span>
    </li>
  );
}

/** Phone agenda: today (or the chosen day) and the following days as a list. */
export function Agenda({
  from,
  to,
  occurrences,
  news,
  today,
  onOpen,
  onToggleDone,
  onNew,
  online,
}: {
  from: string;
  to: string;
  occurrences: Occurrence[];
  news: NewsEvent[];
  today: string;
  onOpen: (o: Occurrence, origin?: DrawerOrigin) => void;
  onToggleDone: (o: Occurrence, done: boolean) => void;
  onNew: (date: string) => void;
  online: boolean;
}) {
  const days = groupByDay(occurrences, datesBetween(from, to));
  const newsByDay = new Map<string, NewsEvent[]>();
  for (const ev of news) {
    const d = ukDateOf(ev.at);
    newsByDay.set(d, [...(newsByDay.get(d) ?? []), ev]);
  }
  if (occurrences.length === 0 && news.length === 0) {
    return (
      <EmptyState
        illustration={<CalendarEmpty />}
        title={from === to ? "Nothing planned" : "Nothing planned these days"}
        text="Add a backtest session, a review or an admin task."
        action={
          <button type="button" className="btn btn-primary" onClick={() => onNew(from)}>
            + New task
          </button>
        }
      />
    );
  }
  return (
    <div className="flex flex-col gap-5">
      {days.map(({ date, items }) => (
        <section key={date} aria-label={dayLabel(date)}>
          <h2 className="mb-2 flex items-baseline gap-2 text-body font-medium">
            <span className={date === today ? "border-l-2 border-accent pl-2" : ""}>{date === today ? "Today" : dayLabel(date)}</span>
            {date === today ? <span className="num text-label text-muted">{dayLabel(date, "short")}</span> : null}
            <span className="num ml-auto text-label text-muted">{items.length ? `${items.length} ${items.length === 1 ? "task" : "tasks"}` : ""}</span>
          </h2>
          <ul className="flex flex-col gap-2">
            {(newsByDay.get(date) ?? []).length > 2 ? (
              <NewsSummaryRow date={date} events={newsByDay.get(date) ?? []} />
            ) : (
              (newsByDay.get(date) ?? []).map((ev) => <NewsRow key={`news-${ev.id}`} ev={ev} />)
            )}
            {items.map((o) => (
              <AgendaRow key={o.id} occ={o} onOpen={onOpen} onToggleDone={onToggleDone} online={online} />
            ))}
            {items.length === 0 ? (
              <li>
                <button type="button" className="flex min-h-11 w-full items-center rounded-panel border border-dashed border-border px-3 text-left text-body text-muted hover:text-text" onClick={() => onNew(date)}>
                  Nothing planned · add a task
                </button>
              </li>
            ) : null}
          </ul>
        </section>
      ))}
    </div>
  );
}
