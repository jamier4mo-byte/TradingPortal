import { Drawer, SkeletonText } from "../../../components/ui/index.ts";
import { type BriefNews, fmtDuration, fmtMonth, fmtR, type Strategy, useBrief } from "../../../lib/journal.ts";
import { dayLabel } from "../../../lib/news.ts";

/** Pre-session brief (U7): profile, rule checklist, the last two "one thing to improve", next month to replay. */
export function BriefDrawer({ open, onClose, strategy }: { open: boolean; onClose: () => void; strategy: Strategy }) {
  const brief = useBrief(strategy.id, open);
  const b = brief.data;
  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()} title="Before you start" description={strategy.name}>
      {brief.isPending ? (
        <SkeletonText lines={8} />
      ) : brief.isError ? (
        <p role="alert" className="text-body text-loss">{brief.error.message}</p>
      ) : b ? (
        <div className="flex flex-col gap-5">
          <section>
            <h3 className="text-body font-medium">Replay next</h3>
            <p className="mt-1 text-body text-muted">
              {b.next_uncovered ? (
                <>
                  <span className="text-text">{fmtMonth(b.next_uncovered)}</span> is the next month without an ideal trade.
                </>
              ) : (
                "Coverage is complete. Pick any month for the backtest."
              )}
            </p>
          </section>
          <section>
            <h3 className="text-body font-medium">Rules</h3>
            <ol className="mt-2 flex flex-col gap-1.5">
              {b.rules.map((r, i) => (
                <li key={r.key} className="flex gap-2 text-body">
                  <span className="num w-5 shrink-0 text-muted">{i + 1}.</span>
                  {r.text}
                </li>
              ))}
            </ol>
          </section>
          <section>
            <h3 className="text-body font-medium">Profile</h3>
            {b.profile ? (
              <dl className="mt-2 grid grid-cols-2 gap-2 text-body">
                <div className="rounded-panel border border-border bg-surface-2 px-3 py-2"><dt className="text-label text-muted">Average stop</dt><dd className="num">{b.profile.avg_sl_distance ?? "—"}</dd></div>
                <div className="rounded-panel border border-border bg-surface-2 px-3 py-2"><dt className="text-label text-muted">Average target</dt><dd className="num">{b.profile.avg_tp_distance ?? "—"} {b.profile.avg_tp_r ? `(${b.profile.avg_tp_r.toFixed(1)}R)` : ""}</dd></div>
                <div className="rounded-panel border border-border bg-surface-2 px-3 py-2"><dt className="text-label text-muted">Average R</dt><dd className="num">{fmtR(b.profile.avg_r)}</dd></div>
                <div className="rounded-panel border border-border bg-surface-2 px-3 py-2"><dt className="text-label text-muted">Typical hold</dt><dd className="num">{fmtDuration(b.profile.typical_duration_seconds)}</dd></div>
                <div className="col-span-2 rounded-panel border border-border bg-surface-2 px-3 py-2"><dt className="text-label text-muted">Entry times</dt><dd>{b.profile.entry_hours.map((h) => h.label).join(", ") || "—"}</dd></div>
              </dl>
            ) : (
              <p className="mt-1 text-body text-muted">The profile appears once six months of ideal trades are in, or when you open the backtest early.</p>
            )}
          </section>
          <section>
            <h3 className="text-body font-medium">From your last sessions</h3>
            {b.recent_improve_notes.length ? (
              <ul className="mt-2 flex flex-col gap-2">
                {b.recent_improve_notes.map((n) => (
                  <li key={n.session_id} className="rounded-panel border border-border bg-surface-2 px-3 py-2 text-body">
                    {n.note}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-body text-muted">No notes yet. Each recap asks for one thing to improve.</p>
            )}
          </section>
          <BriefNewsSection news={b.news} />
        </div>
      ) : null}
    </Drawer>
  );
}

function BriefNewsSection({ news }: { news: BriefNews | null }) {
  return (
    <section>
      <h3 className="text-body font-medium">High-impact news{news?.month ? ` in ${fmtMonth(news.month)}` : ""}</h3>
      {!news || news.status === "no_data" ? (
        <p className="mt-1 text-body text-muted">{news?.note ?? "No news data for that month: it's outside the stored news history."}</p>
      ) : news.events.length === 0 ? (
        <p className="mt-1 text-body text-muted">No high-impact events stored for your instruments that month.</p>
      ) : (
        <>
          <p className="num mt-1 text-label text-muted">
            {news.high_count} high-impact {news.high_count === 1 ? "event" : "events"}
            {news.status === "partial" ? " · part of the month has no news data" : ""}
          </p>
          <ul className="mt-2 flex max-h-64 flex-col divide-y divide-border overflow-y-auto">
            {news.events.map((e) => (
              <li key={e.id} className="flex min-h-11 items-center gap-2 py-1.5 text-body">
                <span className="num w-28 shrink-0 text-label text-muted">
                  {dayLabel(e.uk_date, "short")} {e.uk_time}
                </span>
                <span className="font-mono text-label">{e.currency}</span>
                <span className="min-w-0 flex-1 truncate">{e.name}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
