import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CurrencyTag, ImpactChip } from "../../components/news/NewsBits.tsx";
import { CalendarEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, OfflineState, SkeletonText, StatTile } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { queryState, useHub, type WeekRecap } from "../../lib/hub.ts";
import { fmtPnl } from "../../lib/journal.ts";
import { signed } from "../../lib/markets.ts";
import { dayLabel, useWeekAhead } from "../../lib/news.ts";
import { StaleFigures } from "./StaleStamp.tsx";

/** Week behind / week ahead (Engaging touches): from Sunday 18:00 UK until Monday night, a recap of the
 * user's own week sits beside the key events of the coming week. Lazy: only mounted inside that window. */
export default function WeekPair() {
  return (
    <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
      <WeekBehind />
      <WeekAheadCompact />
    </div>
  );
}

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

function WeekBehind() {
  const hub = useHub();
  const recap = hub.data?.week_recap;
  const subtitle = recap ? `${dayLabel(recap.week_start, "short")} – ${dayLabel(recap.week_end, "short")}` : undefined;
  return (
    <Card title="Week behind" subtitle={subtitle}>
      {queryState(hub) === "pending" ? (
        <SkeletonText lines={4} />
      ) : queryState(hub) === "offline" ? (
        <EmptyState illustration={<CalendarEmpty />} title="You're offline" text="The recap loads when you're back online." />
      ) : !recap ? (
        <ErrorState title="The recap didn't load" text={hub.error?.message} onRetry={() => void hub.refetch()} />
      ) : recap.trades === 0 && recap.sessions === 0 ? (
        <EmptyState illustration={<CalendarEmpty />} title="A quiet week" text="No sessions or trades logged last week. A fresh week starts now." />
      ) : (
        <StaleFigures paths={["/api/hub"]} dataUpdatedAt={hub.dataUpdatedAt}>
          <Recap recap={recap} />
        </StaleFigures>
      )}
    </Card>
  );
}

function Recap({ recap }: { recap: WeekRecap }) {
  const r = recap.total_r;
  const usd = recap.total_pnl ?? null;
  return (
    <div className="grid grid-cols-2 gap-3 tablet:grid-cols-3">
      <StatTile label="Sessions" value={recap.sessions} />
      <StatTile label="Trades" value={recap.trades} />
      {usd === null ? (
        <StatTile label="Total R" value={r === null ? "—" : signed(r, 1)} tone={r === null ? "neutral" : r > 0 ? "win" : r < 0 ? "loss" : "breakeven"} />
      ) : (
        <StatTile
          label="Net P&L"
          value={fmtPnl(usd)}
          hint={r === null ? undefined : <span className="num">{signed(r, 1)} R</span>}
          tone={usd > 0 ? "win" : usd < 0 ? "loss" : "breakeven"}
        />
      )}
      <StatTile label="Win rate" value={pct(recap.win_rate)} hint="Breakevens left out" />
      <StatTile label="Rules kept" value={pct(recap.rules_kept_rate)} hint="Trades with every rule followed" />
      <StatTile label="Best day" value={recap.best_day ?? "—"} hint={recap.best_day_r === null ? undefined : <span className="num">{signed(recap.best_day_r, 1)} R</span>} />
    </div>
  );
}

/** A compact week-ahead list: each day with its high-impact events; the full view is a link away. */
function WeekAheadCompact() {
  const q = useWeekAhead();
  const total = q.data?.days.reduce((n, d) => n + d.events.length, 0) ?? 0;
  return (
    <Card
      title="Week ahead"
      subtitle={q.data ? `${dayLabel(q.data.start, "short")} – ${dayLabel(q.data.end, "short")}` : undefined}
      controls={
        <Link to="/news/week" className="btn btn-ghost">
          Open the week ahead
        </Link>
      }
    >
      {offlinePending(q) ? (
        <OfflineState what="The week ahead" />
      ) : q.isPending ? (
        <SkeletonText lines={5} />
      ) : !q.data ? (
        <ErrorState title="The week ahead didn't load" text={q.error?.message} onRetry={() => void q.refetch()} />
      ) : total === 0 ? (
        <EmptyState illustration={<CalendarEmpty />} title="No high-impact events scheduled" text="The schedule appears once Forex Factory publishes it, usually by Sunday evening." />
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {q.data.days.map((d) => (
            <li key={d.date} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 py-2">
              <span className="text-body font-medium">{d.label}</span>
              {d.events.length === 0 ? (
                <span className="text-body text-muted">Quiet</span>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {d.events.slice(0, 3).map((e) => (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body">
                      <span className="num font-mono">{e.all_day ? "All day" : e.uk_time}</span>
                      <CurrencyTag currency={e.currency} />
                      <span className="min-w-0 flex-1">{e.name}</span>
                      <ImpactChip impact={e.impact} compact />
                    </li>
                  ))}
                  {d.events.length > 3 ? (
                    <li className="text-label text-muted">
                      <span className="num">{d.events.length - 3}</span> more
                    </li>
                  ) : null}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
