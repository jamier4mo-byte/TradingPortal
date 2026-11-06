import { useMutation } from "@tanstack/react-query";
import { ClipboardList, Images, Undo2 } from "lucide-react";
import { Link } from "react-router-dom";

import { OwnerChip, useToast } from "../../../components/ui/index.ts";
import { relativeTime } from "../../../lib/format.ts";
import { api } from "../../../lib/api.ts";
import { fmtRange, type JournalSession, useInvalidateJournal } from "../../../lib/journal.ts";

/** "10 trades · 14/20 screenshots · 6/10 reasons" with Finish annotating (U1). */
export function SessionInbox({ sessions, strategyId, onRecap }: { sessions: JournalSession[]; strategyId: number; onRecap: (s: JournalSession) => void }) {
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const undo = useMutation({
    mutationFn: (s: JournalSession) => api.delete<{ trades: number }>(`/api/journal/sessions/${s.id}`),
    onSuccess: (r, s) => {
      invalidate(strategyId);
      toast({
        title: "Session undone",
        text: `${r.trades} trades moved to Trash.`,
        undo: async () => {
          await api.post(`/api/journal/sessions/${s.id}/restore`);
          invalidate(strategyId);
          toast({ title: "Session restored" });
        },
      });
    },
    onError: (err) => toast({ title: "Couldn't undo", text: err.message, tone: "loss" }),
  });
  if (!sessions.length) return <p className="text-body text-muted">No sessions yet. Import a CSV or log a trade to start one.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {sessions.map((s) => {
        const p = s.progress;
        const complete = p.trades > 0 && p.completed >= p.trades;
        return (
          <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-panel border border-border bg-surface-2 px-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-body">
                <span className="capitalize">{s.kind}</span> session · {fmtRange(s.range_start, s.range_end)}
              </p>
              <p className="num text-label text-muted">
                {p.trades} trades · {p.screenshots}/{p.screenshots_target} screenshots · {p.reasons}/{p.reasons_target} reasons · {p.completed}/{p.trades} completed · {relativeTime(s.created_at)}
              </p>
            </div>
            <OwnerChip name={s.owner.display_name} colourIndex={s.owner.colour_index} compact />
            <div className="flex w-full flex-wrap items-center gap-1 tablet:w-auto">
              <button type="button" className="btn btn-ghost px-3" onClick={() => onRecap(s)}>
                Recap
              </button>
              {s.can_edit && p.trades > 0 ? (
                <>
                  <Link to={`/journal/sessions/${s.id}/match`} className="btn btn-ghost size-11 px-0" aria-label="Match screenshots">
                    <Images aria-hidden className="size-4" />
                  </Link>
                  <Link to={`/journal/sessions/${s.id}/annotate`} className={`btn flex-1 tablet:flex-none ${complete ? "btn-secondary" : "btn-primary"}`}>
                    <ClipboardList aria-hidden className="size-4" />
                    {complete ? "Review" : "Finish annotating"}
                  </Link>
                  <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Undo this session" onClick={() => undo.mutate(s)} disabled={undo.isPending}>
                    <Undo2 aria-hidden className="size-4" />
                  </button>
                </>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
