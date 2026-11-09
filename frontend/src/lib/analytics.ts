/** Analytics types, the query hook and the URL ↔ filter state. Mirrors backend/app/services/analytics. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "./api.ts";
import { fmtDuration, fmtPnl, fmtR } from "./journal.ts";

export type Source = "ideal" | "backtest" | "compare";
export type Scope = "mine" | "everyone" | "others";
export type Unit = "count" | "pct" | "r" | "usd" | "duration" | "ratio";

export interface Filters {
  date_from?: string;
  date_to?: string;
  instruments: string[];
  sessions: string[];
  time_from?: string;
  time_to?: string;
  weekdays: number[];
  entry_models: string[];
  directions: ("buy" | "sell")[];
  tags: string[];
  outcomes: ("win" | "loss" | "breakeven")[];
  owners: number[];
  rules?: "all_kept" | "any_broken";
  news?: "inside" | "outside" | "no_data";
  news_event_types: string[];
}

/** "Around news" (3.6): trades inside vs outside news windows, without news data, and by event type. */
export interface AroundNewsRow {
  key: string;
  trades: number;
  win_rate: number | null;
  avg_r: number | null;
  total_r: number | null;
  /** Net $ (backtests); null for ideal trades, which have no P&L. */
  pnl?: number | null;
}

export interface AnalyticsQuery {
  source: Source;
  strategy_id: number | null;
  scope: Scope;
  split_by_owner: boolean;
  filters: Filters;
}

export interface MetricMeta {
  id: string;
  label: string;
  unit: Unit;
  formula: string;
  better: "higher" | "lower" | "neutral";
  sources: string[];
}
export type Kpis = Record<string, number | null>;

export interface Group {
  key: string;
  label: string;
  n: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number | null;
  total_r: number | null;
  avg_r: number | null;
  pnl: number | null;
  profit_factor: number | null;
  avg_sl: number | null;
  avg_tp_r: number | null;
  avg_duration: number | null;
}
export interface EquityPoint {
  i: number;
  id: number;
  at: string;
  r: number | null;
  pnl: number | null;
  outcome: string | null;
  cum_r: number;
  cum_pnl: number;
  dd_r: number;
  dd_pnl: number;
}
export interface Bin {
  from: number;
  to: number;
  n: number;
}
export interface HeatCell {
  weekday: number;
  hour: number;
  n: number;
  avg_r: number | null;
}
export interface CalendarDay {
  date: string;
  n: number;
  wins: number;
  losses: number;
  pnl: number | null;
  r: number | null;
}
export interface RuleCost {
  key: string;
  text: string;
  kept: number;
  broken: number;
  avg_r_kept: number | null;
  avg_r_broken: number | null;
  cost_r: number | null;
}
export interface Rulebook {
  marked: number;
  all_kept: Group;
  any_broken: Group;
  rules: RuleCost[];
}
export interface Streak {
  outcome: string | null;
  length: number;
  start: string;
  r: number;
}
export interface BacktestBlock {
  around_news?: AroundNewsRow[];
  kpis: Kpis;
  equity: EquityPoint[];
  streaks: Streak[];
  breakdowns: Record<"hour" | "weekday" | "session" | "entry_model" | "instrument" | "direction", Group[]>;
  calendar: CalendarDay[];
  r_distribution: Bin[];
  heatmap: HeatCell[];
  rulebook: Rulebook;
  excursions: { n: number; points: { id: number; r: number; mfe: number; outcome: string | null }[] };
  r_sequence: number[];
}
export interface IdealBlock {
  around_news?: AroundNewsRow[];
  kpis: Kpis;
  distributions: { tp_r: Bin[]; sl_distance: Bin[]; tp_distance: Bin[]; duration: { label: string; n: number }[] };
  heatmap: HeatCell[];
  breakdowns: Record<"entry_model" | "weekday" | "session" | "hour" | "direction" | "instrument", Group[]>;
  profile: Record<"entry_hours" | "sessions" | "entry_models" | "weekdays" | "tags" | "instruments" | "sides", { label: string; count: number }[]>;
}
export interface CompareRow {
  key: string;
  ideal_n: number;
  ideal_share: number;
  ideal_avg_r: number | null;
  backtest_n: number;
  backtest_win_rate: number | null;
  backtest_avg_r: number | null;
  holds: "holds" | "fails" | null;
}
export interface CompareBlock {
  ideal_n: number;
  backtest_n: number;
  ideal_avg_r: number | null;
  backtest_avg_win_r: number | null;
  backtest_avg_r: number | null;
  capture_winners: number | null;
  capture_all: number | null;
  ideal_avg_sl: number | null;
  backtest_avg_sl: number | null;
  ideal_avg_tp_r: number | null;
  backtest_avg_tp_r: number | null;
  by_hour: CompareRow[];
  by_entry_model: CompareRow[];
  by_session: CompareRow[];
  by_weekday: CompareRow[];
}
export interface OwnerRef {
  id: number;
  display_name: string;
  colour_index: number;
  status: string;
}
export interface OwnerSplit {
  owner: OwnerRef;
  kpis: Kpis;
  equity: number[];
}
export interface Insight {
  dimension: string;
  key: string;
  metric: string;
  text: string;
  n: number;
  early: boolean;
  slice_value: number;
  baseline_value: number;
  effect: number;
}
export interface Reconcile {
  session_id: number;
  kind: string;
  filename: string | null;
  csv: { trades: number; rpnl_sum: number; balance_start: number | null; balance_end: number | null } | null;
  kept: { trades: number; rpnl_sum: number };
  app: { trades: number; pnl: number };
  diff_trades: number;
  diff_pnl: number;
  balance_ok: boolean | null;
  ok: boolean;
  notes: string[];
}
export interface TradeLine {
  id: number;
  strategy_id: number;
  kind: string;
  opened_at: string;
  instrument: string;
  side: "buy" | "sell";
  r: number | null;
  pnl: number | null;
  outcome: "win" | "loss" | "breakeven" | null;
  entry_model: string | null;
  session_label: string;
  owner_id: number;
}
export interface AnalyticsResult {
  source: Source;
  strategy_id: number | null;
  breakeven_threshold: number;
  counts: { in_scope: number; filtered: number; ideal: number; backtest: number };
  news_status: "ok" | "partial" | "no_data";
  notes: { unresolved_tags: string[]; news: string | null };
  registry: MetricMeta[];
  options: { instruments: string[]; sessions: string[]; entry_models: string[]; tags: string[]; owners: OwnerRef[]; date_min: string | null; date_max: string | null };
  backtest: BacktestBlock | null;
  ideal: IdealBlock | null;
  compare: CompareBlock | null;
  owners: OwnerSplit[] | null;
  insights: Insight[];
  reconcile: Reconcile[];
  trades: TradeLine[];
}

export interface SessionInsights {
  session_vs_baseline: Insight | null;
  session_trades: number;
  min_slice: number;
  top: Insight[];
}

export const EMPTY_FILTERS: Filters = { instruments: [], sessions: [], weekdays: [], entry_models: [], directions: [], tags: [], outcomes: [], owners: [], news_event_types: [] };
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
export const SOURCES: { value: Source; label: string }[] = [
  { value: "ideal", label: "Ideal" },
  { value: "backtest", label: "Backtest" },
  { value: "compare", label: "Compare" },
];

// ---- URL state: every filter is a search param, so a view can be shared and bookmarked ----

const LIST_KEYS = ["instruments", "sessions", "entry_models", "directions", "tags", "outcomes", "news_event_types"] as const;

export function filtersFromParams(p: URLSearchParams): Filters {
  const f: Filters = { ...EMPTY_FILTERS };
  for (const k of LIST_KEYS) {
    const v = p.get(k);
    (f as unknown as Record<string, string[]>)[k] = v ? v.split(",").filter(Boolean) : [];
  }
  f.weekdays = (p.get("weekdays") ?? "").split(",").filter((x) => /^[0-6]$/.test(x)).map(Number);
  f.owners = (p.get("owners") ?? "").split(",").filter((x) => /^\d+$/.test(x)).map(Number);
  for (const k of ["date_from", "date_to", "time_from", "time_to"] as const) {
    const v = p.get(k);
    if (v) f[k] = v;
  }
  const rules = p.get("rules");
  if (rules === "all_kept" || rules === "any_broken") f.rules = rules;
  const news = p.get("news");
  if (news === "inside" || news === "outside" || news === "no_data") f.news = news;
  return f;
}

export function writeFilters(p: URLSearchParams, f: Filters): URLSearchParams {
  const next = new URLSearchParams(p);
  for (const k of [...LIST_KEYS, "weekdays", "owners"] as const) {
    const v = (f as unknown as Record<string, (string | number)[]>)[k];
    if (v.length) next.set(k, v.join(","));
    else next.delete(k);
  }
  for (const k of ["date_from", "date_to", "time_from", "time_to", "rules", "news"] as const) {
    const v = f[k];
    if (v) next.set(k, v);
    else next.delete(k);
  }
  return next;
}

export function activeFilterCount(f: Filters): number {
  let n = 0;
  for (const k of [...LIST_KEYS, "weekdays", "owners"] as const) if ((f as unknown as Record<string, unknown[]>)[k].length) n++;
  if (f.date_from || f.date_to) n++;
  if (f.time_from || f.time_to) n++;
  if (f.rules) n++;
  if (f.news) n++;
  return n;
}

/** Source, scope, split and filters, read from and written to the URL. */
export function useAnalyticsState(strategyId: number | null) {
  const [params, setParams] = useSearchParams();
  const sourceParam = params.get("src");
  const source: Source = sourceParam === "ideal" || sourceParam === "compare" ? sourceParam : "backtest";
  const scopeParam = params.get("scope");
  const scope: Scope = scopeParam === "mine" || scopeParam === "others" ? scopeParam : "everyone";
  const split = params.get("split") === "1";
  const paramString = params.toString();
  const filters = useMemo(() => filtersFromParams(new URLSearchParams(paramString)), [paramString]);
  const query: AnalyticsQuery = useMemo(() => ({ source, strategy_id: strategyId, scope, split_by_owner: split, filters }), [source, strategyId, scope, split, filters]);

  const update = useCallback(
    (fn: (p: URLSearchParams) => URLSearchParams) => setParams((prev) => fn(new URLSearchParams(prev)), { replace: true }),
    [setParams],
  );
  const setSource = useCallback((s: Source) => update((p) => (s === "backtest" ? (p.delete("src"), p) : (p.set("src", s), p))), [update]);
  const setSplit = useCallback((on: boolean) => update((p) => (on ? p.set("split", "1") : p.delete("split"), p)), [update]);
  const setFilters = useCallback((f: Filters) => update((p) => writeFilters(p, f)), [update]);
  const clearFilters = useCallback(() => update((p) => writeFilters(p, EMPTY_FILTERS)), [update]);
  return { query, source, scope, split, filters, setSource, setSplit, setFilters, clearFilters };
}

/** keepPreviousData: a filter change holds the old frame (dimmed) and the charts morph to the new data. */
export function useAnalytics(query: AnalyticsQuery, enabled = true) {
  return useQuery({
    queryKey: ["analytics", query],
    queryFn: () => api.post<AnalyticsResult>("/api/analytics/query", query),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    enabled,
  });
}

export function useSessionInsights(sessionId: number) {
  return useQuery({ queryKey: ["session-insights", sessionId], queryFn: () => api.get<SessionInsights>(`/api/journal/sessions/${sessionId}/insights`), staleTime: 30_000 });
}

export function exportUrl(kind: "ai" | "csv", query: AnalyticsQuery, includeImages = true): string {
  const body = kind === "ai" ? { ...query, include_images: includeImages } : query;
  return `/api/analytics/export/${kind}?q=${encodeURIComponent(JSON.stringify(body))}`;
}

// ---- formatting by unit ----

export function fmtMetric(unit: Unit | undefined, v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  switch (unit) {
    case "pct":
      return `${Math.round(v * 100)}%`;
    case "r":
      return fmtR(v);
    case "usd":
      return fmtPnl(v);
    case "duration":
      return fmtDuration(v);
    case "ratio":
      return v.toFixed(2);
    default:
      return Number.isInteger(v) ? v.toLocaleString("en-GB") : v.toLocaleString("en-GB", { maximumFractionDigits: 1 });
  }
}

export function toneOf(v: number | null | undefined): "win" | "loss" | "neutral" {
  if (v === null || v === undefined || v === 0) return "neutral";
  return v > 0 ? "win" : "loss";
}

export function metaById(registry: MetricMeta[]): Record<string, MetricMeta> {
  return Object.fromEntries(registry.map((m) => [m.id, m]));
}
