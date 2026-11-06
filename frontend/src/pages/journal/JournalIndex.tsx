import { ChartLine, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ChartEmpty } from "../../components/ui/Illustrations.tsx";
import { Drawer, EmptyState, ErrorState, SkeletonCard, useViewScope, ViewScopeToggle } from "../../components/ui/index.ts";
import { useAuth } from "../../lib/auth.tsx";
import { useStrategies } from "../../lib/journal.ts";
import { StrategyCard } from "./components/StrategyCard.tsx";
import { StrategyForm } from "./components/StrategyForm.tsx";

/** Strategy overview (2.1): a grid of strategy cards. Everyone's by default; one column on the phone. */
export default function JournalIndex() {
  const [scope] = useViewScope();
  const strategies = useStrategies(scope);
  const [creating, setCreating] = useState(false);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const quickLog = params.get("quicklog") === "1";
  const editable = (strategies.data ?? []).filter((s) => s.can_edit);

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <img src="/brand/replayjournal-logo.png" alt="Replay Journal" className="hidden h-9 w-auto tablet:block" />
        <h1 className="text-heading font-semibold tablet:sr-only">Strategies</h1>
        <div className="ml-auto flex items-center gap-2">
          <ViewScopeToggle size="sm" />
          <Link to="/journal/analytics" className="btn btn-ghost">
            <ChartLine aria-hidden className="size-4" />
            <span className="hidden tablet:inline">Analytics</span>
            <span className="sr-only tablet:hidden">Analytics</span>
          </Link>
          <Link to="/journal/trash" className="btn btn-ghost size-11 px-0" aria-label="Trash">
            <Trash2 aria-hidden className="size-4" />
          </Link>
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden className="size-4" />
            <span className="hidden tablet:inline">New strategy</span>
            <span className="tablet:hidden">New</span>
          </button>
        </div>
      </header>

      {strategies.isPending ? (
        <div className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6" aria-busy>
          <SkeletonCard className="col-span-4" />
          <SkeletonCard className="col-span-4" />
          <SkeletonCard className="col-span-4" />
        </div>
      ) : strategies.isError ? (
        <ErrorState title="Strategies didn't load" text={strategies.error.message} onRetry={() => strategies.refetch()} />
      ) : strategies.data.length === 0 ? (
        <div className="card">
          <EmptyState
            illustration={<ChartEmpty />}
            title={scope === "everyone" ? "No strategies yet" : scope === "mine" ? "You haven't created a strategy yet" : "Nobody else has a strategy yet"}
            text={scope === "others" ? "Switch to Everyone to see your own." : "A strategy starts as a catalogue of winners. Six months of them unlocks the backtest."}
            action={
              scope === "others" ? null : (
                <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
                  <Plus aria-hidden className="size-4" /> New strategy
                </button>
              )
            }
          />
        </div>
      ) : (
        <ul className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6" aria-label="Strategies">
          {strategies.data.map((s) => (
            <li key={s.id} className="col-span-4 large:col-span-3">
              <StrategyCard strategy={s} />
            </li>
          ))}
        </ul>
      )}

      <StrategyForm open={creating} onClose={() => setCreating(false)} onSaved={(s) => navigate(`/journal/strategies/${s.id}`)} />

      {/* Phone "+" lands here: pick where to log */}
      <Drawer
        open={quickLog}
        onOpenChange={(o) => {
          if (!o) {
            const next = new URLSearchParams(params);
            next.delete("quicklog");
            setParams(next, { replace: true });
          }
        }}
        title="Log a trade"
        description={editable.length ? "Which strategy?" : "Create a strategy first."}
      >
        {editable.length ? (
          <ul className="flex flex-col gap-2">
            {editable.map((s) => (
              <li key={s.id}>
                <Link to={`/journal/strategies/${s.id}?quicklog=1`} className="flex min-h-12 items-center rounded-panel border border-border bg-surface-2 px-3 text-body hover:border-border-strong">
                  {s.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <button type="button" className="btn btn-primary w-full" onClick={() => setCreating(true)} disabled={!user}>
            <Plus aria-hidden className="size-4" /> New strategy
          </button>
        )}
      </Drawer>
    </div>
  );
}
