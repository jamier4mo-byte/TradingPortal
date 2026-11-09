import { Lightbulb, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

import Card from "../../../components/Card.tsx";
import { Chip, SkeletonText, StatTile, useToast } from "../../../components/ui/index.ts";
import { useSessionInsights } from "../../../lib/analytics.ts";
import { api } from "../../../lib/api.ts";
import { fmtPct, fmtPnl, fmtR, fmtRange, type JournalSession, type Trade, useInvalidateJournal, useSessionTrades } from "../../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../../lib/motion.ts";

/** Session recap: trades, win rate, total R, rules followed, the best trade's screenshot, one thing to improve. */
export function RecapCard({ session, onClose, className = "" }: { session: JournalSession; onClose: () => void; className?: string }) {
  const level = motionLevel();
  const trades = useSessionTrades(session.id);
  const invalidate = useInvalidateJournal();
  const { toast } = useToast();
  const [note, setNote] = useState(session.improve_note);
  const best = (trades.data ?? []).filter((t) => t.r_multiple !== null).sort((a, b) => (b.r_multiple ?? 0) - (a.r_multiple ?? 0))[0] as Trade | undefined;
  const shot = best?.screenshots.find((s) => s.slot === "outcome") ?? best?.screenshots.find((s) => s.slot === "entry") ?? best?.screenshots[0];
  const s = session.stats;
  const saveNote = async () => {
    if (note === session.improve_note) return;
    await api.patch(`/api/journal/sessions/${session.id}`, { improve_note: note });
    invalidate(session.strategy_id);
    toast({ title: "Saved" });
  };
  return (
    <motion.div
      initial={level === "full" ? { opacity: 0, y: 12, scale: 0.98 } : { opacity: 0 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: level === "off" ? 0 : dur.emphasis(), ease: easeEnter }}
      className={className}
    >
      <Card
        title="Session recap"
        subtitle={`${session.kind === "manual" ? "Logged by hand" : "Imported"} · ${fmtRange(session.range_start, session.range_end)}`}
        controls={
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Close recap" onClick={onClose}>
            <X aria-hidden className="size-4" />
          </button>
        }
      >
        <div className="grid gap-4 laptop:grid-cols-[1fr_280px]">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-2 tablet:grid-cols-4">
              <StatTile
                label="Net P&L"
                value={s.total_pnl === null ? fmtR(s.total_r) : fmtPnl(s.total_pnl)}
                hint={s.total_pnl === null ? undefined : <span className="num">{fmtR(s.total_r)}</span>}
                tone={((s.total_pnl ?? s.total_r) ?? 0) > 0 ? "win" : ((s.total_pnl ?? s.total_r) ?? 0) < 0 ? "loss" : "neutral"}
              />
              <StatTile label="Trades" value={s.trades} />
              <StatTile label="Win rate" value={fmtPct(s.win_rate)} />
              <StatTile label="Rules followed" value={fmtPct(s.rules_followed_rate)} hint={s.rules_followed_rate === null ? "Tick them in Annotate mode" : undefined} />
            </div>
            <SessionInsights sessionId={session.id} />
            <label className="flex flex-col gap-1.5">
              <span className="text-body font-medium">One thing to improve</span>
              <textarea className="input min-h-16 py-2" value={note} onChange={(e) => setNote(e.target.value)} onBlur={saveNote} maxLength={2000} placeholder="Next session, I will…" disabled={!session.can_edit} />
            </label>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="num text-label text-muted">Best trade {best ? `· ${fmtR(best.r_multiple)}` : ""}</span>
            {shot ? (
              <img src={shot.thumb_url} alt={`Best trade of the session, ${fmtR(best?.r_multiple)}`} className="aspect-video w-full rounded-panel border border-border object-cover" />
            ) : (
              <div className="grid aspect-video place-items-center rounded-panel border border-dashed border-border-strong text-label text-muted">No screenshot yet</div>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

/** U11 on the recap: this session against the strategy's baseline, then the strategy's top differences. */
function SessionInsights({ sessionId }: { sessionId: number }) {
  const q = useSessionInsights(sessionId);
  if (q.isPending) return <SkeletonText lines={2} />;
  if (q.isError)
    return (
      <p className="flex flex-wrap items-center gap-2 text-body text-muted">
        Couldn&rsquo;t load the comparison.
        <button type="button" className="btn btn-ghost" onClick={() => q.refetch()}>
          Try again
        </button>
      </p>
    );
  const items = [...(q.data.session_vs_baseline ? [q.data.session_vs_baseline] : []), ...q.data.top].slice(0, 3);
  return (
    <div className="flex flex-col gap-1.5" data-testid="recap-insights">
      <span className="text-body font-medium">How it compares</span>
      {items.length ? (
        <ul className="flex flex-col gap-1.5">
          {items.map((i) => (
            <li key={`${i.dimension}-${i.key}`} className="flex items-start gap-2 text-body">
              <Lightbulb aria-hidden className="mt-0.5 size-4 shrink-0 text-subtle" strokeWidth={1.75} />
              <span className="num min-w-0 flex-1">{i.text.replace(" · early signal", "")}</span>
              {i.early ? <Chip className="shrink-0">Early signal</Chip> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body text-muted">
          Nothing stands out yet: insights need at least {q.data.min_slice} trades in a slice and the session has {q.data.session_trades}.
        </p>
      )}
    </div>
  );
}
