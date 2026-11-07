import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Lock, LockOpen, MoreHorizontal, Pencil, Play, Plus, Trash2, Upload } from "lucide-react";
import { motion } from "motion/react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { Chip, ConfirmDialog, ErrorState, OfflineState, OwnerChip, PillToggle, ReadOnlyBanner, RingGauge, SkeletonCard, SkeletonText, useToast } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { api } from "../../lib/api.ts";
import { type JournalSession, STAGE_LABEL, type Strategy, type TradeKind, useInstruments, useInvalidateJournal, useProfile, useSessions, useStrategy, useTrades } from "../../lib/journal.ts";
import { remember, remembered } from "../../lib/hub.ts";
import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";
import { vtName } from "../../lib/vt.ts";
import { BriefDrawer } from "./components/BriefDrawer.tsx";
import { CoverageTracker } from "./components/Coverage.tsx";
import { ImportDrawer } from "./components/ImportDrawer.tsx";
import { QuickLogDrawer } from "./components/QuickLogDrawer.tsx";
import { RecapCard } from "./components/RecapCard.tsx";
import { SessionInbox } from "./components/SessionInbox.tsx";
import { StrategyForm } from "./components/StrategyForm.tsx";
import { StrategyProfile } from "./components/StrategyProfile.tsx";
import { TradeList } from "./components/TradeList.tsx";

const AnalyticsView = lazy(() => import("./analytics/AnalyticsView.tsx"));

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

  if (offlinePending(strategy)) {
    return (
      <div className="card">
        <OfflineState what="This strategy" />
      </div>
    );
  }
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

  // Backtest unlock moment (Engaging touches): when coverage reaches six months after an import or a log,
  // or "Open early" succeeds, the lock opens, the Backtest tab lights up once and a toast confirms it.
  // Process, not profit. Fires once per strategy per device; the previous value comes from the last render
  // of the cached strategy, so a page that opens already unlocked stays quiet.
  const [celebrate, setCelebrate] = useState(false);
  const wasUnlocked = useRef(unlocked);
  useEffect(() => {
    const was = wasUnlocked.current;
    wasUnlocked.current = unlocked;
    if (was || !unlocked) return;
    const key = `tp.unlocked.${s.id}`;
    if (remembered(key)) return;
    remember(key);
    if (s.coverage.unlocked) toast({ title: "Backtest unlocked: six months of winners", text: "The strategy profile is built from them. The Backtest tab is open." });
    if (motionLevel() === "off") return;
    setCelebrate(true);
    const timer = window.setTimeout(() => setCelebrate(false), (dur.emphasis() * 2 + 0.3) * 1000);
    return () => window.clearTimeout(timer);
  }, [unlocked, s.id, s.coverage.unlocked, toast]);

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-3">
        <Link to="/journal" className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text">
          <ArrowLeft aria-hidden className="size-4" /> Strategies
        </Link>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 basis-full laptop:flex-1 laptop:basis-0">
            <h1 className="text-heading font-semibold" style={{ viewTransitionName: vtName("strategy", s.id) }}>
              {s.name}
            </h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <OwnerChip name={s.owner.display_name} colourIndex={s.owner.colour_index} deactivated={s.owner.status === "deactivated"} />
              <Chip dot dotClass={s.stage === "ideal" ? "bg-muted" : "bg-accent"}>
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
              <button type="button" className="btn btn-secondary hidden tablet:inline-flex" onClick={() => setBrief(true)}>
                <Play aria-hidden className="size-4" /> Start session
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setImporting(tab === "backtest" ? "backtest" : "ideal")}>
                <Upload aria-hidden className="size-4" /> <span className="hidden tablet:inline">Import CSV</span><span className="tablet:hidden">Import</span>
              </button>
              <button type="button" className="btn btn-primary hidden tablet:inline-flex" onClick={() => setLogging(tab === "backtest" ? "backtest" : "ideal")}>
                <Plus aria-hidden className="size-4" /> Log trade
              </button>
              <button type="button" className="btn btn-ghost hidden size-11 px-0 tablet:grid" aria-label="Edit strategy" onClick={() => setEditing(true)}>
                <Pencil aria-hidden className="size-4" />
              </button>
              <button type="button" className="btn btn-ghost hidden size-11 px-0 tablet:grid" aria-label="Delete strategy" onClick={() => setDeleting(true)}>
                <Trash2 aria-hidden className="size-4" />
              </button>
              {/* Phone: one primary action (Import); the rest live in a menu. The + button covers logging. */}
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button type="button" className="btn btn-secondary size-11 px-0 tablet:hidden" aria-label="More actions">
                    <MoreHorizontal aria-hidden className="size-5" />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content align="end" sideOffset={6} className="card z-30 min-w-56 p-1.5 data-[state=open]:animate-[page-enter_var(--dur-quick)_var(--ease-in-enter)]">
                    {[
                      { label: "Start session", icon: Play, run: () => setBrief(true) },
                      { label: "Log trade", icon: Plus, run: () => setLogging(tab === "backtest" ? "backtest" : "ideal") },
                      { label: "Edit strategy", icon: Pencil, run: () => setEditing(true) },
                      { label: "Delete strategy", icon: Trash2, run: () => setDeleting(true) },
                    ].map(({ label, icon: Icon, run }) => (
                      <DropdownMenu.Item key={label} onSelect={run} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-panel px-3 text-body text-muted outline-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-text">
                        <Icon aria-hidden className="size-4" strokeWidth={1.75} />
                        {label}
                      </DropdownMenu.Item>
                    ))}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          ) : null}
        </div>
        {!s.can_edit ? <ReadOnlyBanner owner={s.owner.display_name} what="strategy" /> : null}
      </header>

      <div className="flex items-center justify-between gap-3">
        <PillToggle value={tab} onChange={setTab} options={TABS} label="Strategy tab" highlight={celebrate ? "backtest" : undefined} />
      </div>

      {latestRecap ? <RecapCard session={latestRecap} onClose={() => setRecap(null)} /> : null}

      <Card title="Sessions" subtitle="Each import or logging run. Finish annotating adds the screenshots and reasons.">
        {sessions.isPending ? <SkeletonText lines={2} /> : sessions.isError ? <ErrorState text={sessions.error.message} onRetry={() => sessions.refetch()} /> : <SessionInbox sessions={sessions.data} strategyId={s.id} onRecap={setRecap} />}
      </Card>

      <motion.div key={tab} initial={level === "full" ? { opacity: 0, y: 8 } : { opacity: 0 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }} className="flex flex-col gap-4 laptop:gap-6">
        {tab === "ideal" ? <IdealTab strategy={s} celebrate={celebrate} onLog={() => setLogging("ideal")} onMissed={() => setLogging("missed")} /> : null}
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
        {tab === "analytics" ? (
          <Suspense fallback={<SkeletonCard />}>
            <AnalyticsView strategy={s} />
          </Suspense>
        ) : null}
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

function IdealTab({ strategy: s, celebrate, onLog, onMissed }: { strategy: Strategy; celebrate: boolean; onLog: () => void; onMissed: () => void }) {
  const trades = useTrades(s.id, "ideal");
  const missed = useTrades(s.id, "missed");
  return (
    <>
      <Card title="Coverage" subtitle="Months with at least one ideal trade, by UK date">
        <CoverageTracker coverage={s.coverage} celebrate={celebrate} />
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
        {missed.isPending ? <SkeletonText lines={2} /> : missed.isError ? <ErrorState text={missed.error.message} onRetry={() => missed.refetch()} /> : missed.data.length ? <TradeList trades={missed.data} strategyId={s.id} mode="missed" emptyTitle="" /> : <p className="text-body text-muted">Nothing missed so far.</p>}
      </Card>
    </>
  );
}

function BacktestTab({ strategy: s, onLog, onImport }: { strategy: Strategy; onLog: () => void; onImport: () => void }) {
  const trades = useTrades(s.id, "backtest");
  const profile = useProfile(s.id);
  const instruments = useInstruments();
  const units = new Set(s.instruments.map((sym) => instruments.data?.find((i) => i.symbol === sym)?.unit ?? "points"));
  const unit = units.size === 1 && units.has("pips") ? "pips" : "pts";
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
