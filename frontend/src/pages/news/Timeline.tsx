import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { SkeletonCard } from "../../components/ui/index.ts";
import { ErrorState } from "../../components/ui/States.tsx";
import { type Timeline as TimelineData, useTimeline } from "../../lib/news.ts";
import { ukParts } from "../../lib/time.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";
import { useNow } from "../../lib/useNow.ts";
import { ImpactDot } from "../../components/news/NewsBits.tsx";

const DAY = 24 * 60;

/** Minutes after UK midnight for an ISO time, clamped to the day of `date` (UK). */
function ukMinute(iso: string, date: string): number {
  const d = new Date(iso);
  const ukDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  if (ukDate < date) return 0;
  if (ukDate > date) return DAY;
  const { hour, minute } = ukParts(d);
  return hour * 60 + minute;
}

const pct = (m: number) => `${(m / DAY) * 100}%`;

/** Trading-day timeline (3.2): Asia, London and New York bands, high-impact windows shaded, event markers,
 * a moving "now" line and the current session softly highlighted. On the phone it scrolls sideways with
 * "now" centred. */
export function TradingDayTimeline({ date, isToday }: { date: string; isToday: boolean }) {
  const q = useTimeline(date);
  if (q.isPending) return <SkeletonCard className="h-40" />;
  if (q.isError) return <ErrorState title="The timeline didn't load" text={q.error.message} onRetry={() => q.refetch()} />;
  return <TimelineBody data={q.data} isToday={isToday} />;
}

function TimelineBody({ data, isToday }: { data: TimelineData; isToday: boolean }) {
  const now = useNow(30_000);
  const phone = useDevice() === "phone";
  const scroller = useRef<HTMLDivElement>(null);
  const nowMin = isToday ? ukParts(now).hour * 60 + ukParts(now).minute : null;
  const activeSession = nowMin === null ? null : data.sessions.filter((s) => ukMinute(s.start, data.date) <= nowMin && nowMin < ukMinute(s.end, data.date)).map((s) => s.name);

  useEffect(() => {
    const el = scroller.current;
    if (!el || !phone) return;
    const target = nowMin ?? 8 * 60; // centre "now", or the London open on other days
    el.scrollLeft = (target / DAY) * el.scrollWidth - el.clientWidth / 2;
    // only on mount / day change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.date, phone]);

  const high = data.events.filter((e) => e.impact === "high");
  const others = data.events.filter((e) => e.impact !== "high" && !e.all_day);
  const summary = `${data.sessions.map((s) => s.name).join(", ")} sessions; ${high.length} high-impact ${high.length === 1 ? "event" : "events"} with ${data.window_minutes}-minute news windows${
    nowMin !== null ? `; now ${String(Math.floor(nowMin / 60)).padStart(2, "0")}:${String(nowMin % 60).padStart(2, "0")} UK` : ""
  }.`;

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div ref={scroller} className="overflow-x-auto pb-2 [scrollbar-width:thin]" tabIndex={phone ? 0 : undefined} aria-label={phone ? "Trading-day timeline, scrolls sideways" : undefined}>
        <div className={`relative ${phone ? "w-[1100px]" : "w-full"}`}>
          {/* hour ticks */}
          <div className="relative h-5 text-label text-muted" aria-hidden>
            {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
              <span key={h} className="num absolute -translate-x-1/2 first:translate-x-0" style={{ left: pct(h * 60) }}>
                {String(h).padStart(2, "0")}:00
              </span>
            ))}
          </div>
          <div className="relative mt-1 rounded-panel border border-border bg-surface-2" style={{ height: 120 }}>
            {/* news windows */}
            {data.windows.map((w) => {
              const a = ukMinute(w.start, data.date);
              const b = ukMinute(w.end, data.date);
              return (
                <div
                  key={`w-${w.event_id}`}
                  aria-hidden
                  className="absolute inset-y-0 border-x border-impact-high/40 bg-impact-high/10"
                  style={{ left: pct(a), width: pct(Math.max(2, b - a)) }}
                />
              );
            })}
            {/* session bands */}
            {data.sessions.map((s, i) => {
              const a = ukMinute(s.start, data.date);
              const b = ukMinute(s.end, data.date);
              const active = activeSession?.includes(s.name);
              return (
                <div
                  key={s.name}
                  className={`absolute flex h-6 items-center overflow-hidden rounded-pill border px-2 text-label ${
                    active ? "border-accent bg-accent-soft text-text" : "border-border-strong bg-surface-1 text-muted"
                  }`}
                  style={{ left: pct(a), width: pct(b - a), top: 8 + i * 30 }}
                >
                  <span className="truncate">
                    {s.name}
                    {active ? <span className="sr-only"> (now)</span> : null}
                  </span>
                </div>
              );
            })}
            {/* event markers */}
            {[...others, ...high].map((e) => {
              const m = ukMinute(e.at, data.date);
              return (
                <Link
                  key={e.id}
                  to={`/news/events/${e.id}`}
                  className="group absolute bottom-0 grid h-11 w-11 -translate-x-1/2 place-items-center"
                  style={{ left: pct(m) }}
                  aria-label={`${e.uk_time} ${e.currency} ${e.name}, ${e.impact_label} impact`}
                  title={`${e.uk_time} ${e.currency} ${e.name}`}
                >
                  <ImpactDot impact={e.impact} className={e.impact === "high" ? "size-3 ring-2 ring-surface-2" : "size-2 opacity-80"} />
                </Link>
              );
            })}
            {/* now line */}
            {nowMin !== null ? (
              <div aria-hidden className="absolute inset-y-0 w-px bg-text transition-[left] duration-(--dur-emphasis)" style={{ left: pct(nowMin) }}>
                <span className="num absolute -top-5 left-1/2 -translate-x-1/2 rounded-pill bg-text px-1.5 text-label text-bg">Now</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-label text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-4 rounded-sm border border-impact-high/40 bg-impact-high/10" />
          News window ±{data.window_minutes} min around high impact
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-4 rounded-sm border border-accent bg-accent-soft" />
          Current session
        </span>
        <Link to="/settings#news" className="underline decoration-border-strong underline-offset-4 hover:text-text">
          Change window
        </Link>
      </p>
    </figure>
  );
}
