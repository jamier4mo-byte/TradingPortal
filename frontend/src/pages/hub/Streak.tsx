import { Link } from "react-router-dom";

import { OfflineGlyph } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonText } from "../../components/ui/index.ts";
import { queryState, useHub } from "../../lib/hub.ts";
import { dayLabel } from "../../lib/news.ts";
import { StaleFigures } from "./StaleStamp.tsx";

/** Process streak ("Showing up"): days with a session logged, a note written or a trade reviewed. It
 * rewards showing up, never P&L. Lazy: lives below the fold. */
export default function Streak() {
  const hub = useHub();
  const state = queryState(hub);
  if (state === "pending") return <SkeletonText lines={3} />;
  if (state === "offline") return <EmptyState illustration={<OfflineGlyph className="size-8" />} title="You're offline" text="Your streak loads when you're back online." />;
  if (!hub.data) return <ErrorState title="The streak didn't load" text={hub.error?.message} onRetry={() => void hub.refetch()} />;
  const s = hub.data.streak;
  const first = s.days[0]?.date;
  const last = s.days[s.days.length - 1]?.date;

  if (s.best_days === 0) {
    return (
      <div className="flex flex-col gap-3">
        <Dots days={s.days} />
        <p className="text-body text-muted">Log a session or review a trade to start a streak.</p>
        <Link to="/journal" className="btn btn-ghost self-start">
          Open the journal
        </Link>
      </div>
    );
  }
  return (
    <StaleFigures paths={["/api/hub"]} dataUpdatedAt={hub.dataUpdatedAt} className="flex flex-col gap-3">
      <p className="text-title font-semibold">
        <span className="num">{s.current_days}</span>-day streak · best <span className="num">{s.best_days}</span>
      </p>
      <Dots days={s.days} />
      {first && last ? (
        <p className="num flex justify-between text-label text-muted" aria-hidden>
          <span>{dayLabel(first, "short")}</span>
          <span>{dayLabel(last, "short")}</span>
        </p>
      ) : null}
      <p className="text-body text-muted">
        {s.active_today ? "You showed up today." : s.current_days > 0 ? "Nothing yet today; a session or a review keeps it going." : "Start again today: a session logged or a trade reviewed."}{" "}
        Showing up counts, not the result.
      </p>
    </StaleFigures>
  );
}

function Dots({ days }: { days: { date: string; active: boolean }[] }) {
  return (
    <ol className="grid grid-cols-14 gap-1.5 tablet:grid-cols-28" aria-label="The last 28 days">
      {days.map((d) => (
        <li key={d.date} className="flex justify-center">
          <span aria-hidden className={`size-2.5 rounded-full ${d.active ? "bg-accent" : "border border-border-strong bg-surface-2"}`} />
          <span className="sr-only">
            {dayLabel(d.date, "short")}: {d.active ? "showed up" : "quiet"}
          </span>
        </li>
      ))}
    </ol>
  );
}
