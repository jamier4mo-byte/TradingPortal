import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { ErrorState, OfflineState, OwnerChip, SkeletonText, useToast } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { relativeTime } from "../../lib/format.ts";
import { api } from "../../lib/api.ts";
import { fmtRange, fmtUkDateTime, useInvalidateJournal, useTrash } from "../../lib/journal.ts";

/** Trash (F5): deleted strategies, sessions and trades, restorable for 30 days. */
export default function Trash() {
  const trash = useTrash();
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const restore = useMutation({
    mutationFn: ({ kind, id }: { kind: "strategies" | "journal/sessions" | "trades"; id: number }) => api.post(`/api/${kind}/${id}/restore`),
    onSuccess: () => {
      invalidate();
      toast({ title: "Restored" });
    },
    onError: (err) => toast({ title: "Couldn't restore", text: err.message, tone: "loss" }),
  });
  const Row = ({ title, meta, owner, onRestore }: { title: string; meta: string; owner: { display_name: string; colour_index: number }; onRestore: () => void }) => (
    <li className="flex flex-wrap items-center gap-3 rounded-panel border border-border bg-surface-2 px-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="truncate text-body">{title}</p>
        <p className="text-label text-muted">{meta}</p>
      </div>
      <OwnerChip name={owner.display_name} colourIndex={owner.colour_index} compact />
      <button type="button" className="btn btn-secondary" onClick={onRestore} disabled={restore.isPending}>
        <RotateCcw aria-hidden className="size-4" /> Restore
      </button>
    </li>
  );
  const d = trash.data;
  const empty = d && !d.strategies.length && !d.sessions.length && !d.trades.length;
  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-2">
        <Link to="/journal" className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text">
          <ArrowLeft aria-hidden className="size-4" /> Strategies
        </Link>
        <h1 className="text-heading font-semibold">Trash</h1>
        <p className="text-body text-muted">Deleted items stay here for {d?.days ?? 30} days, then they're removed for good.</p>
      </header>
      {offlinePending(trash) ? (
        <div className="card">
          <OfflineState what="The Trash" />
        </div>
      ) : trash.isPending ? (
        <Card title="Loading">
          <SkeletonText lines={4} />
        </Card>
      ) : trash.isError ? (
        <ErrorState text={trash.error.message} onRetry={() => trash.refetch()} />
      ) : empty || !d ? (
        <Card title="Nothing in the Trash">
          <p className="text-body text-muted">Deleted strategies, sessions and trades appear here.</p>
        </Card>
      ) : (
        <>
          {d.strategies.length ? (
            <Card title="Strategies">
              <ul className="flex flex-col gap-2">
                {d.strategies.map((s) => (
                  <Row key={s.id} title={s.name} meta={`${s.ideal_count + s.backtest_count} trades · deleted ${relativeTime(s.deleted_at)}`} owner={s.owner} onRestore={() => restore.mutate({ kind: "strategies", id: s.id })} />
                ))}
              </ul>
            </Card>
          ) : null}
          {d.sessions.length ? (
            <Card title="Sessions">
              <ul className="flex flex-col gap-2">
                {d.sessions.map((s) => (
                  <Row key={s.id} title={`${s.kind} session · ${fmtRange(s.range_start, s.range_end)}`} meta={`${s.trade_count} trades · deleted ${relativeTime(s.deleted_at)}`} owner={s.owner} onRestore={() => restore.mutate({ kind: "journal/sessions", id: s.id })} />
                ))}
              </ul>
            </Card>
          ) : null}
          {d.trades.length ? (
            <Card title="Trades">
              <ul className="flex flex-col gap-2">
                {d.trades.map((t) => (
                  <Row key={t.id} title={`${t.instrument} ${t.side === "buy" ? "long" : "short"} · ${fmtUkDateTime(t.opened_at)}`} meta={`${t.kind} · deleted ${relativeTime(t.deleted_at)}`} owner={t.owner} onRestore={() => restore.mutate({ kind: "trades", id: t.id })} />
                ))}
              </ul>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
