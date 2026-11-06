import { Copy, Download, SlidersHorizontal, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Card from "../../../components/Card.tsx";
import { ChartSkeleton } from "../../../components/charts/Chart.tsx";
import { ChartEmpty } from "../../../components/ui/Illustrations.tsx";
import { Drawer, EmptyState, ErrorState, PillToggle, SkeletonCard } from "../../../components/ui/index.ts";
import { activeFilterCount, type AnalyticsResult, metaById, SOURCES, type Source, useAnalytics, useAnalyticsState, WEEKDAYS } from "../../../lib/analytics.ts";
import type { Strategy } from "../../../lib/journal.ts";
import { useMediaQuery } from "../../../lib/useMediaQuery.ts";
import { BacktestViews, OwnersCard } from "./BacktestViews.tsx";
import { CompareView } from "./CompareView.tsx";
import { ExportDrawer, MorphIcon, useCopyForAi } from "./ExportDrawer.tsx";
import { FilterPanel } from "./FilterPanel.tsx";
import { IdealViews } from "./IdealViews.tsx";
import { InsightsCard, ReconcileLine, TradeMiniList } from "./parts.tsx";

/**
 * Analytics (2.4) for one strategy, or for every strategy when `strategy` is omitted.
 * Layout per device: large screens show filters, charts and the trade list side by side; desktop keeps
 * filters at the side; laptop folds them into a collapsible panel; tablet uses a drawer; the phone a
 * bottom sheet. Source, scope, split and every filter live in the URL.
 */
export default function AnalyticsView({ strategy }: { strategy?: Strategy }) {
  const st = useAnalyticsState(strategy?.id ?? null);
  const result = useAnalytics(st.query);
  const [params, setParams] = useSearchParams();
  const wide = useMediaQuery("(min-width: 1440px)");
  const large = useMediaQuery("(min-width: 1920px)");
  const laptop = useMediaQuery("(min-width: 1024px)") && !wide;
  const [panelOpen, setPanelOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const exportOpen = params.get("export") === "1";
  const setExportOpen = (open: boolean) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (open) next.set("export", "1");
        else next.delete("export");
        return next;
      },
      { replace: true },
    );
  const { copy, state: copyState } = useCopyForAi(st.query);
  const data = result.data;
  const dim = result.isPlaceholderData;
  const nFilters = activeFilterCount(st.filters);
  const filtersText = useMemo(() => describe(st.filters, st.source), [st.filters, st.source]);
  const showOwners = !strategy || (data?.options.owners.length ?? 0) > 1;

  const panel = <FilterPanel filters={st.filters} onChange={st.setFilters} onClear={st.clearFilters} options={data?.options} source={st.source} newsStatus={data?.news_status} showOwners={showOwners} />;

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2 print:hidden" data-testid="analytics-toolbar">
      <PillToggle value={st.source} onChange={st.setSource} options={SOURCES} label="Data source" />
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {showOwners ? (
          <button type="button" aria-pressed={st.split} onClick={() => st.setSplit(!st.split)} className={`btn ${st.split ? "btn-secondary border-accent" : "btn-ghost"}`}>
            <Users aria-hidden className="size-4" /> <span className="hidden tablet:inline">Split by owner</span>
            <span className="sr-only tablet:hidden">Split by owner</span>
          </button>
        ) : null}
        {!wide ? (
          <button
            type="button"
            className="btn btn-secondary"
            aria-expanded={laptop ? panelOpen : sheetOpen}
            aria-controls={laptop ? "filters-panel" : undefined}
            onClick={() => (laptop ? setPanelOpen((v) => !v) : setSheetOpen(true))}
          >
            <SlidersHorizontal aria-hidden className="size-4" /> Filters
            {nFilters ? <span className="num grid min-w-5 place-items-center rounded-pill bg-accent px-1.5 text-label text-on-accent">{nFilters}</span> : null}
          </button>
        ) : null}
        <button type="button" className="btn btn-ghost hidden laptop:inline-flex" onClick={() => void copy()} disabled={copyState === "busy" || !data?.counts.filtered}>
          <MorphIcon done={copyState === "done"} Icon={Copy} /> {copyState === "done" ? "Copied" : "Copy for AI"}
        </button>
        <button type="button" className="btn btn-primary" onClick={() => setExportOpen(true)}>
          <Download aria-hidden className="size-4" /> Export
        </button>
      </div>
    </div>
  );

  const body = (() => {
    if (result.isPending) return <AnalyticsSkeleton />;
    if (result.isError || !data) return <div className="card"><ErrorState title="Analytics didn't load" text={result.error?.message} onRetry={() => result.refetch()} /></div>;
    if (data.counts.in_scope === 0) return <NothingYet source={st.source} strategy={strategy} />;
    if (data.counts.filtered === 0)
      return (
        <div className="card">
          <EmptyState illustration={<ChartEmpty />} title="No trades match these filters" text={`None of the ${data.counts.in_scope} trades fit ${filtersText}.`} action={<button type="button" className="btn btn-primary" onClick={st.clearFilters}>Clear filters</button>} />
        </div>
      );
    return <Views data={data} source={st.source} dim={dim} split={st.split} />;
  })();

  return (
    <div className="flex flex-col gap-4 laptop:gap-6" data-testid="analytics">
      {toolbar}
      <p className="num -mt-1 text-label text-muted print:text-body" aria-live="polite">
        {data ? `${data.counts.filtered} of ${data.counts.in_scope} trades · ${filtersText}` : "Loading…"}
        {data?.notes.unresolved_tags.length ? ` · unknown tags: ${data.notes.unresolved_tags.join(", ")}` : ""}
      </p>
      {laptop && panelOpen ? (
        <section id="filters-panel" aria-label="Filters" className="card p-4 print:hidden">
          {panel}
        </section>
      ) : null}
      <div className={wide ? `grid items-start gap-6 ${large ? "grid-cols-[288px_minmax(0,1fr)_340px]" : "grid-cols-[272px_minmax(0,1fr)]"}` : ""}>
        {wide ? (
          <aside aria-label="Filters" className="card sticky top-20 max-h-[calc(100dvh-6rem)] overflow-y-auto p-4 print:hidden">
            {panel}
          </aside>
        ) : null}
        <div className="flex min-w-0 flex-col gap-4 laptop:gap-6">
          {data && data.counts.filtered > 0 ? (
            <>
              <ReconcileLine items={data.reconcile} />
              <InsightsCard insights={data.insights} />
            </>
          ) : null}
          {body}
          {data && data.counts.filtered > 0 && !large ? (
            <Card title="Trades" subtitle="In this filter, newest first" className="print:hidden">
              <TradeMiniList trades={data.trades} total={data.counts.filtered} limit={wide ? 20 : 10} />
            </Card>
          ) : null}
        </div>
        {large && data ? (
          <aside aria-label="Trades in this filter" className="card sticky top-20 max-h-[calc(100dvh-6rem)] overflow-y-auto p-4 print:hidden">
            <h2 className="mb-3 text-title font-semibold">Trades</h2>
            <TradeMiniList trades={data.trades} total={data.counts.filtered} limit={60} />
          </aside>
        ) : null}
      </div>
      {!wide && !laptop ? (
        <Drawer
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          title="Filters"
          description="Every chart, number and the export follow these."
          footer={
            <button type="button" className="btn btn-primary w-full" onClick={() => setSheetOpen(false)}>
              Show {data ? data.counts.filtered : "…"} trades
            </button>
          }
        >
          {panel}
        </Drawer>
      ) : null}
      <ExportDrawer open={exportOpen} onOpenChange={setExportOpen} query={st.query} filtersText={filtersText} tradeCount={data?.counts.filtered ?? 0} />
    </div>
  );
}

function Views({ data, source, dim, split }: { data: AnalyticsResult; source: Source; dim: boolean; split: boolean }) {
  const meta = useMemo(() => metaById(data.registry), [data.registry]);
  if (source === "ideal" && data.ideal) {
    return (
      <>
        <IdealViews block={data.ideal} meta={meta} unit="pips or points" dim={dim} />
        {split && data.owners && data.owners.length > 1 ? <OwnersCard owners={data.owners} /> : null}
      </>
    );
  }
  if (source === "compare" && data.compare) {
    return (
      <>
        <CompareView block={data.compare} dim={dim} />
        {split && data.owners && data.owners.length > 1 ? <OwnersCard owners={data.owners} /> : null}
      </>
    );
  }
  if (data.backtest) return <BacktestViews block={data.backtest} meta={meta} registry={data.registry} owners={split ? data.owners : null} dim={dim} />;
  return null;
}

function NothingYet({ source, strategy }: { source: Source; strategy?: Strategy }) {
  const what = source === "ideal" ? "ideal trades" : source === "compare" ? "ideal and backtest trades" : "backtest trades";
  const tab = source === "ideal" ? "" : "?tab=backtest";
  return (
    <div className="card">
      <EmptyState
        illustration={<ChartEmpty />}
        title={`No ${what} yet`}
        text={source === "compare" ? "Compare needs both: ideal winners for the profile, and backtest trades to test it against." : source === "ideal" ? "Log a winner or import an FX Replay session as Ideal, and its profile appears here." : "Import an FX Replay session with the Backtest destination and the equity curve, breakdowns and Monte Carlo appear here."}
        action={strategy && strategy.can_edit ? <Link className="btn btn-primary" to={`/journal/strategies/${strategy.id}${tab}`}>Go to {source === "ideal" ? "Ideal trades" : "Backtest"}</Link> : undefined}
      />
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="flex flex-col gap-4 laptop:gap-6" aria-busy>
      <div className="grid grid-cols-2 gap-2 tablet:grid-cols-3 laptop:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={`skeleton h-20 ${i === 4 ? "hidden tablet:block" : ""}`} role="status" aria-label="Loading" />
        ))}
      </div>
      <div className="card p-4 tablet:p-5">
        <ChartSkeleton height={280} />
      </div>
      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  );
}

function describe(f: ReturnType<typeof useAnalyticsState>["filters"], source: Source): string {
  const parts: string[] = [];
  if (f.date_from || f.date_to) parts.push(`${f.date_from ?? "start"} to ${f.date_to ?? "now"}`);
  if (f.instruments.length) parts.push(f.instruments.join("/"));
  if (f.sessions.length) parts.push(f.sessions.join("/"));
  if (f.time_from || f.time_to) parts.push(`${f.time_from ?? "00:00"}–${f.time_to ?? "24:00"} UK`);
  if (f.weekdays.length) parts.push(f.weekdays.map((d) => WEEKDAYS[d]).join("/"));
  if (f.entry_models.length) parts.push(f.entry_models.join("/"));
  if (f.directions.length) parts.push(f.directions.map((d) => (d === "buy" ? "longs" : "shorts")).join("/"));
  if (f.tags.length) parts.push(`tags ${f.tags.join("/")}`);
  if (f.outcomes.length) parts.push(f.outcomes.join("/"));
  if (f.owners.length) parts.push(`${f.owners.length} owner${f.owners.length > 1 ? "s" : ""}`);
  if (f.rules) parts.push(f.rules === "all_kept" ? "all rules kept" : "a rule broken");
  if (f.news) parts.push(`news ${f.news}`);
  const src = source === "ideal" ? "Ideal" : source === "compare" ? "Compare" : "Backtest";
  return parts.length ? `${src} · ${parts.join(" · ")}` : `${src} · no filters`;
}
