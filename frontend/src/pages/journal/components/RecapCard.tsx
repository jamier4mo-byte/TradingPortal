import { X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

import Card from "../../../components/Card.tsx";
import { StatTile, useToast } from "../../../components/ui/index.ts";
import { api } from "../../../lib/api.ts";
import { fmtPct, fmtR, fmtRange, type JournalSession, type Trade, useInvalidateJournal, useSessionTrades } from "../../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../../lib/motion.ts";

/** Session recap: trades, win rate, total R, rules followed, the best trade's screenshot, one thing to improve. */
export function RecapCard({ session, onClose, className = "" }: { session: JournalSession; onClose: () => void; className?: string }) {
  const level = motionLevel();
  const trades = useSessionTrades(session.id);
  const invalidate = useInvalidateJournal();
  const { toast } = useToast();
  const [note, setNote] = useState(session.improve_note);
  const best = (trades.data ?? []).filter((t) => t.r_multiple !== null).sort((a, b) => (b.r_multiple ?? 0) - (a.r_multiple ?? 0))[0] as Trade | undefined;
  const shot = best?.screenshots.find((s) => s.slot === "exit") ?? best?.screenshots[0];
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
              <StatTile label="Trades" value={s.trades} />
              <StatTile label="Win rate" value={fmtPct(s.win_rate)} tone={s.win_rate === null ? "neutral" : s.win_rate >= 0.5 ? "win" : "loss"} />
              <StatTile label="Total R" value={fmtR(s.total_r)} tone={(s.total_r ?? 0) > 0 ? "win" : (s.total_r ?? 0) < 0 ? "loss" : "neutral"} />
              <StatTile label="Rules followed" value={fmtPct(s.rules_followed_rate)} hint={s.rules_followed_rate === null ? "Tick them in Annotate mode" : undefined} />
            </div>
            <label className="flex flex-col gap-1.5">
              <span className="text-body font-medium">One thing to improve</span>
              <textarea className="input min-h-16 py-2" value={note} onChange={(e) => setNote(e.target.value)} onBlur={saveNote} maxLength={2000} placeholder="Next session, I will…" disabled={!session.can_edit} />
            </label>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted">Best trade {best ? `· ${fmtR(best.r_multiple)}` : ""}</span>
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
