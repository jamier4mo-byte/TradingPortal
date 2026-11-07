import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { CountdownRing } from "../../components/news/CountdownRing.tsx";
import { CurrencyTag, Figures, ImpactChip } from "../../components/news/NewsBits.tsx";
import { OfflineState, Skeleton } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { dayLabel, type NewsEvent, useEventDetail, useNextEvent } from "../../lib/news.ts";
import { useNow } from "../../lib/useNow.ts";

const KEEP_RELEASED_MS = 30 * 60_000; // keep showing a just-released event for 30 minutes

/** The next high-impact event, pinned at the top of the News Room. The ring depletes; in the last 15
 * minutes it turns orange, then red, with a gentle pulse. Once the time passes the card stays on that
 * event for half an hour so the actual can flip in when it arrives. */
export function NextUp({ compact = false }: { compact?: boolean }) {
  const next = useNextEvent(true);
  const [held, setHeld] = useState<NewsEvent | null>(null);
  const lastSeen = useRef<NewsEvent | null>(null);
  const skew = useRef(0);

  useEffect(() => {
    const data = next.data;
    if (!data) return;
    skew.current = new Date(data.server_now).getTime() - Date.now();
    const prev = lastSeen.current;
    if (prev && data.event?.id !== prev.id && Date.now() + skew.current - new Date(prev.at).getTime() < KEEP_RELEASED_MS) {
      setHeld(prev);
    }
    lastSeen.current = data.event;
  }, [next.data]);

  const left = (iso: string, nowMs: number) => (new Date(iso).getTime() - (nowMs + skew.current)) / 1000;
  const secondsTo = next.data?.event ? left(next.data.event.at, Date.now()) : Infinity;
  const now = useNow(secondsTo < 3600 ? 1000 : 15_000);
  const nowMs = now.getTime();

  // When the shown event's time passes, hold it for a while (and refetch to move on to the next one).
  useEffect(() => {
    const e = next.data?.event;
    if (e && left(e.at, nowMs) <= 0 && held?.id !== e.id) {
      setHeld(e);
      void next.refetch();
    }
    if (held && -left(held.at, nowMs) * 1000 > KEEP_RELEASED_MS) setHeld(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nowMs]);

  const releasedDetail = useEventDetail(held?.id ?? 0);
  const shown = held ? (releasedDetail.data?.event ?? held) : next.data?.event ?? null;

  if (offlinePending(next)) {
    return (
      <section aria-label="Next high-impact event" className="card p-4 tablet:p-5">
        <OfflineState what="The countdown" className="py-2" />
      </section>
    );
  }
  if (next.isPending) {
    return (
      <section aria-label="Next high-impact event" className="card flex items-center gap-4 p-4 tablet:p-5">
        <Skeleton className="size-24 rounded-full" />
        <div className="flex-1">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="mt-2 h-4 w-32" />
        </div>
      </section>
    );
  }
  if (next.isError && !next.data) {
    return (
      <section aria-label="Next high-impact event" className="card p-4 tablet:p-5">
        <p className="text-body">The countdown didn&rsquo;t load.</p>
        <button type="button" className="btn btn-secondary mt-3" onClick={() => next.refetch()}>
          Try again
        </button>
      </section>
    );
  }
  if (!shown) {
    return (
      <section aria-label="Next high-impact event" className="card p-4 tablet:p-5">
        <p className="text-title font-semibold">No high-impact news ahead</p>
        <p className="mt-1 text-body text-muted">Nothing high impact is scheduled for your instruments in the loaded week.</p>
      </section>
    );
  }
  const secs = left(shown.at, nowMs);
  const refreshFailed = next.isError && !!next.data;
  const released = secs <= 0;
  return (
    <section aria-label="Next high-impact event" className={`card relative flex items-center gap-4 overflow-hidden p-4 tablet:gap-6 tablet:p-5`}>
      <CountdownRing secondsLeft={secs} size={compact ? 76 : 112} label={`${shown.currency} ${shown.name}`} />
      <div className="min-w-0 flex-1">
        <p className="text-label text-muted">
          {released ? "Just released" : "Next high impact"} · <span className="num">{dayLabel(shown.uk_date, "short")} {shown.uk_time} UK</span>
        </p>
        <Link to={`/news/events/${shown.id}`} className="mt-1 flex min-h-11 items-center gap-2 hover:underline hover:decoration-border-strong hover:underline-offset-4">
          <CurrencyTag currency={shown.currency} />
          <span className="line-clamp-2 min-w-0 text-title font-semibold">
            {shown.name}
          </span>
          <ImpactChip impact={shown.impact} compact className="hidden tablet:inline-flex" />
        </Link>
        {compact ? (
          shown.actual ? (
            <p className="num text-body">
              Actual <span className="flip-in inline-block font-semibold">{shown.actual}</span>
              {shown.forecast ? <span className="text-muted"> · forecast {shown.forecast}</span> : null}
            </p>
          ) : shown.forecast ? (
            <p className="num text-label text-muted">Forecast {shown.forecast} · previous {shown.previous ?? "—"}</p>
          ) : null
        ) : (
          <Figures event={{ ...shown, released: released || shown.released }} flip={!!held} className="mt-2 max-w-md" />
        )}
        {refreshFailed ? (
          <p className="mt-1 text-label text-muted">
            Couldn&rsquo;t refresh.{" "}
            <button type="button" className="inline-flex min-h-11 items-center underline underline-offset-4" onClick={() => next.refetch()}>
              Retry
            </button>
          </p>
        ) : null}
        <p className="mt-1 text-label text-muted" aria-live="polite">
          {released && !shown.actual ? "Actual pending: it appears here when the actuals feed next updates." : ""}
        </p>
      </div>
    </section>
  );
}
