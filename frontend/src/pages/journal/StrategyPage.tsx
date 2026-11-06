import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ClipboardList, Lock, LockOpen, Pencil, Play, Plus, Trash2, Upload } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { Chip, ConfirmDialog, EmptyState, ErrorState, OwnerChip, PillToggle, ReadOnlyBanner, RingGauge, SkeletonCard, SkeletonText, StatTile, useToast } from "../../components/ui/index.ts";
import { ChartEmpty } from "../../components/ui/Illustrations.tsx";
import { api } from "../../lib/api.ts";
import { fmtPct, fmtR, type JournalSession, STAGE_LABEL, type Strategy, type TradeKind, useInvalidateJournal, useProfile, useSessions, useStrategy, useTrades } from "../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";
import { BriefDrawer } from "./components/BriefDrawer.tsx";
import { CoverageTracker } from "./components/Coverage.tsx";
import { ImportDrawer } from "./components/ImportDrawer.tsx";
import { QuickLogDrawer } from "./components/QuickLogDrawer.tsx";
import { RecapCard } from "./components/RecapCard.tsx";
import { SessionInbox } from "./components/SessionInbox.tsx";
import { StrategyForm } from "./components/StrategyForm.tsx";
import { StrategyProfile } from "./components/StrategyProfile.tsx";
import { TradeList } from "./components/TradeList.tsx";

type Tab = "ideal" | "backtest" | "analytics";
const TABS = [
  { value: "ideal" as const, label: "Ideal trades" },
  { value: "backtest" as const, label: "Backtest" },
  { value: "analytics" as const, label: "Analytics" },
];

/** Strategy page (2.2, 2.3): tabs, session inbox, coverage, trades, profile, imports and the brief. */
export default function StrategyPage() {
  const id = Number(useParams().id);
  const strategy = useStrategy(id);
  const [params, setParams] = useSearchParams();
  const tab = (["ideal", "backtest", "analytics"].includes(params.get("tab") ?? "") ? params.get("tab") : "ideal") as Tab;
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params);
    if (t === "ideal") next.delete("tab");
    else next.set("tab", t);
    setParams(next, { replace: true });
  };

  if (strategy.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        <SkeletonText lines={2} className="max-w-sm" />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  if (strategy.isError) {
    return (
      <div className="card">
        <ErrorState title={strategy.error.message.includes("No such") ? "That strategy isn't here" : "Strategy didn't load"} text={strategy.error.message.includes("No such") ? "It may be in the Trash." : strategy.error.message} onRetry={() => strategy.refetch()} />
        <Link to="/journal" className="btn btn-ghost mx-auto mb-4 flex w-fit">
          Back to strategies
        </Link>
      </div>
    );
  }
  return <StrategyScreen strategy={strategy.data} tab={tab} setTab={setTab} />;
}

function StrategyScreen({ strategy: s, tab, setTab }: { strategy: Strategy; tab: Tab; setTab: (t: Tab) => void }) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const [params, setParams] = useSearchParams();
  const sessions = useSessions(s.id);
  const [editing, setEditing] = useState(false);
  const [importing, setImporting] = useState<null | "ideal" | "backtest">(null);
  const [logging, setLogging] = useState<null | TradeKind>(params.get("quicklog") === "1" ? "ideal" : null);
  const [brief, setBrief] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [openEarly, setOpenEarly] = useState(false);
  const [recap, setRecap] = useState<JournalSession | null>(null);
  const level = motionLevel();

  const closeLog = () => {
    setLogging(null);
    if (params.get("quicklog")) {
      const next = new URLSearchParams(params);
      next.delete("quicklog");
      setParams(next, { replace: true });
    }
  };

  const del = useMutation({
    mutationFn: () => api.delete(`/api/strategies/${s.id}`),
    onSuccess: () => {
      invalidate(s.id);
      toast({
        title: "Strategy moved to Trash",
        text: "It can be restored for 30 days.",
        undo: async () => {
          await api.post(`/api/strategies/${s.id}/restore`);
          invalidate(s.id);
          toast({ title: "Strategy restored" });
        },
      });
      navigate("/journal");
    },
    onError: (err) => toast({ title: "Couldn't delete", text: err.message, tone: "loss" }),
  });
  const unlockEarly = useMutation({
    mutationFn: () => api.patch<Strategy>(`/api/strategies/${s.id}`, { backtest_opened_early: true }),
    onSuccess: () => {
      invalidate(s.id);
      setOpenEarly(false);
      toast({ title: "Backtest opened early", text: "The profile is based on fewer than six months of winners." });
    },
  });

  const unlocked = s.coverage.unlocked || s.backtest_opened_early;
  const latestRecap = recap ?? null;

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-3">
        <Link to="/journal" className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text">
          <ArrowLeft aria-hidden className="size-4" /> Strategies
        </Link>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-heading font-semibold">{s.name}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <OwnerChip name={s.owner.display_name} colourIndex={s.owner.colour_index} deactivated={s.owner.status === "deactivated"} />
              <Chip dot dotClass={s.stage === "backtesting" ? "bg-win" : s.stage === "ready" ? "bg-accent" : "bg-muted"}>
                {STAGE_LABEL[s.stage]}
              </Chip>
              {s.instruments.map((i) => (
                <Chip key={i} className="font-mono">
                  {i}
                </Chip>
              ))}
              {s.timeframes.map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
            </div>
            {s.description ? <p className="mt-2 max-w-prose text-body text-muted">{s.description}</p> : null}
          </div>
          {s.can_edit ? (
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-secondary" onClick={() => setBrief(true)}>
                <Play aria-hidden className="size-4" /> Start session
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setImporting(tab === "backtest" ? "backtest" : "ideal")}>
                <Upload aria-hidden className="size-4" /> <span className="hidden tablet:inline">Import CSV</span><span className="tablet:hidden">Import</span>
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setLogging(tab === "backtest" ? "backtest" : "ideal")}>
                <Plus aria-hidden className="size-4" /> <span className="hidden tablet:inline">Log trade</span><span className="tablet:hidden">Log</span>
              </button>
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Edit strategy" onClick={() => setEditing(true)}>
                <Pencil aria-hidden className="size-4" />
              </button>
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Delete strategy" onClick={() => setDeleting(true)}>
                <Trash2 aria-hidden className="size-4" />
              </button>
            </div>
          ) : null}
        </div>
        {!s.can_edit ? <ReadOnlyBanner owner={s.owner.display_name} what="strategy" /> : null}
      </header>

      {latestRecap ? <RecapCard session={latestRecap} onClose={() => setRecap(null)} /> : null}

      <Card title="Sessions" subtitle="Each import or logging run. Finish annotating adds the screenshots and reasons.">
        {sessions.isPending ? <SkeletonText lines={2} /> : sessions.isError ? <ErrorState text={sessions.error.message} onRetry={() => sessions.refetch()} /> : <SessionInbox sessions={sessions.data} strategyId={s.id} onRecap={setRecap} />}
      </Card>

      <div className="flex items-center justify-between gap-3">
        <PillToggle value={tab} onChange={setTab} options={TABS} label="Strategy tab" />
      </div>

      <motion.div key={tab} initial={level === "full" ? { opacity: 0, y: 8 } : { opacity: 0 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }} className="flex flex-col gap-4 laptop:gap-6">
        {tab === "ideal" ? <IdealTab strategy={s} onLog={() => setLogging("ideal")} onMissed={() => setLogging("missed")} /> : null}
        {tab === "backtest" ? (
          unlocked ? (
            <BacktestTab strategy={s} onLog={() => setLogging("backtest")} onImport={() => setImporting("backtest")} />
          ) : (
            <Card title="Backtest" subtitle="Unlocks after six consecutive months of ideal trades">
              <div className="flex flex-col items-center gap-4 py-4 text-center tablet:flex-row tablet:text-left">
                <RingGauge value={Math.min(s.coverage.best_run, s.coverage.target_months)} max={s.coverage.target_months} label="Coverage" display={`${Math.min(s.coverage.best_run, s.coverage.target_months)}/${s.coverage.target_months}`} size={112} />
                <div className="flex-1">
                  <p className="flex items-center justify-center gap-2 text-title font-semibold tablet:justify-start">
                    <Lock aria-hidden className="size-4 text-muted" /> Locked
                  </p>
                  <p className="mt-1 text-body text-muted">
                    <span className="num">{s.coverage.best_run}</span> of <span className="num">{s.coverage.target_months}</span> consecutive months covered, <span className="num">{s.coverage.trade_count}</span> ideal trades. The backtest runs against the profile those winners define.
                  </p>
                  {s.can_edit ? (
                    <button type="button" className="btn btn-secondary mt-4" onClick={() => setOpenEarly(true)}>
                      <LockOpen aria-hidden className="size-4" /> Open early
                    </button>
                  ) : null}
                </div>
              </div>
            </Card>
          )
        ) : null}
        {tab === "analytics" ? <AnalyticsPlaceholder strategy={s} /> : null}
      </motion.div>

      <StrategyForm open={editing} onClose={() => setEditing(false)} strategy={s} />
      <ImportDrawer open={importing !== null} onClose={() => setImporting(null)} strategy={s} destination={importing ?? "ideal"} onImported={(r) => setRecap(r.session)} />
      {logging ? <QuickLogDrawer open onClose={closeLog} strategy={s} kind={logging} /> : null}
      <BriefDrawer open={brief} onClose={() => setBrief(false)} strategy={s} />
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={`Move “${s.name}” to Trash?`}
        text="Its trades and sessions go with it. Everything can be restored from Trash for 30 days."
        confirmLabel="Move to Trash"
        danger
        busy={del.isPending}
        onConfirm={() => del.mutate()}
      />
      <ConfirmDialog
        open={openEarly}
        onOpenChange={setOpenEarly}
        title="Open the backtest early?"
        text={`Only ${s.coverage.best_run} of ${s.coverage.target_months} months are covered, so the strategy profile will be built on a thin sample. Useful for setups that trade rarely; treat the numbers as provisional.`}
        confirmLabel="Open early"
        busy={unlockEarly.isPending}
        onConfirm={() => unlockEarly.mutate()}
      />
    </div>
  );
}

function IdealTab({ strategy: s, onLog, onMissed }: { strategy: Strategy; onLog: () => void; onMissed: () => void }) {
  const trades = useTrades(s.id, "ideal");
  const missed = useTrades(s.id, "missed");
  return (
    <>
      <Card title="Coverage" subtitle="Months with at least one ideal trade, by UK date">
        <CoverageTracker coverage={s.coverage} />
      </Card>
      <Card
        title="Ideal trades"
        subtitle="Winners only: the textbook examples of the setup"
        controls={
          s.can_edit ? (
            <button type="button" className="btn btn-secondary" onClick={onLog}>
              <Plus aria-hidden className="size-4" /> Log
            </button>
          ) : undefined
        }
      >
        {trades.isPending ? (
          <SkeletonText lines={5} />
        ) : trades.isError ? (
          <ErrorState text={trades.error.message} onRetry={() => trades.refetch()} />
        ) : (
          <TradeList
            trades={trades.data}
            strategyId={s.id}
            mode="ideal"
            emptyTitle="No ideal trades yet"
            emptyText="Log your first winner, or import an FX Replay session."
            emptyAction={
              s.can_edit ? (
                <button type="button" className="btn btn-primary" onClick={onLog}>
                  Log a trade
                </button>
              ) : undefined
            }
          />
        )}
      </Card>
      <Card
        title="Missed setups"
        subtitle="Saw it, didn't take it. Kept out of P&L."
        controls={
          s.can_edit ? (
            <button type="button" className="btn btn-ghost" onClick={onMissed}>
              <Plus aria-hidden className="size-4" /> Log a miss
            </button>
          ) : undefined
        }
      >
        {missed.isPending ? <SkeletonText lines={2} /> : missed.isError ? <ErrorState text={missed.error.message} /> : missed.data.length ? <TradeList trades={missed.data} strategyId={s.id} mode="missed" emptyTitle="" /> : <p className="text-body text-muted">Nothing missed so far.</p>}
      </Card>
    </>
  );
}

function BacktestTab({ strategy: s, onLog, onImport }: { strategy: Strategy; onLog: () => void; onImport: () => void }) {
  const trades = useTrades(s.id, "backtest");
  const profile = useProfile(s.id);
  const unit = s.instruments.some((i) => /^[A-Z]{6}$/.test(i) && !i.startsWith("XAU")) ? "pips" : "pts";
  return (
    <>
      <Card title="Strategy profile" subtitle={s.coverage.unlocked ? "The reference rules from six months of winners" : "Opened early: based on fewer than six months of winners"}>
        {profile.isPending ? <SkeletonText lines={4} /> : profile.data ? <StrategyProfile profile={profile.data} unit={unit} /> : <p className="text-body text-muted">Log a few ideal trades and the profile appears here.</p>}
        {s.rules.length ? (
          <ol className="mt-4 grid gap-1.5 tablet:grid-cols-2">
            {s.rules.map((r, i) => (
              <li key={r.key} className="flex gap-2 rounded-panel border border-border px-3 py-2 text-body">
                <span className="num text-muted">{i + 1}.</span> {r.text}
              </li>
            ))}
          </ol>
        ) : null}
      </Card>
      <Card
        title="Backtest trades"
        subtitle="Every valid setup: wins, losses and breakevens"
        controls={
          s.can_edit ? (
            <>
              <button type="button" className="btn btn-ghost" onClick={onImport}>
                <Upload aria-hidden className="size-4" /> Import
              </button>
              <button type="button" className="btn btn-secondary" onClick={onLog}>
                <Plus aria-hidden className="size-4" /> Log
              </button>
            </>
          ) : undefined
        }
      >
        {trades.isPending ? (
          <SkeletonText lines={5} />
        ) : trades.isError ? (
          <ErrorState text={trades.error.message} onRetry={() => trades.refetch()} />
        ) : (
          <TradeList
            trades={trades.data}
            strategyId={s.id}
            mode="backtest"
            emptyTitle="No backtest trades yet"
            emptyText="Import an FX Replay session with the Backtest destination, or log trades by hand."
            emptyAction={
              s.can_edit ? (
                <button type="button" className="btn btn-primary" onClick={onImport}>
                  Import CSV
                </button>
              ) : undefined
            }
          />
        )}
      </Card>
    </>
  );
}

function AnalyticsPlaceholder({ strategy: s }: { strategy: Strategy }) {
  const st = s.backtest_stats;
  return (
    <Card title="Analytics" subtitle="Full analytics arrive in Prompt 3. The headline numbers are live now.">
      {st ? (
        <div className="grid grid-cols-2 gap-2 tablet:grid-cols-4">
          <StatTile label="Backtest trades" value={st.trades} />
          <StatTile label="Win rate" value={fmtPct(st.win_rate)} />
          <StatTile label="Total R" value={fmtR(st.total_r)} tone={(st.total_r ?? 0) > 0 ? "win" : (st.total_r ?? 0) < 0 ? "loss" : "neutral"} />
          <StatTile label="Average R" value={fmtR(st.avg_r)} />
        </div>
      ) : (
        <EmptyState illustration={<ChartEmpty />} title="Nothing to chart yet" text="Backtest trades feed the equity curve, distributions and heatmaps." />
      )}
      <p className="mt-4 flex items-center gap-2 text-label text-muted">
        <ClipboardList aria-hidden className="size-4" /> Ideal · Backtest · Compare views, filters and the export come next.
      </p>
    </Card>
  );
}
