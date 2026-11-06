/** Replay Journal types, queries and formatters. Mirrors backend/app/schemas/journal.py. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type PublicUser, type Tag } from "./api.ts";
import type { NewsEvent } from "./news.ts";

export type TradeKind = "ideal" | "backtest" | "missed";
export type SessionKind = "ideal" | "backtest" | "manual";
export type Side = "buy" | "sell";
export type Slot = "htf" | "entry" | "outcome" | "extra";
/** The three images Jamie fills per trade, in order. */
export const LABELLED_SLOTS = ["htf", "entry", "outcome"] as const;
export type LabelledSlot = (typeof LABELLED_SLOTS)[number];
export const SLOT_LABEL: Record<Slot, string> = { htf: "HTF", entry: "Entry", outcome: "Outcome", extra: "Extra" };
export type Outcome = "win" | "loss" | "breakeven";
export type Stage = "ideal" | "ready" | "backtesting";

export interface Rule {
  key: string;
  text: string;
}
export interface TemplateField {
  key: string;
  label: string;
}

export interface CoverageMonth {
  month: string;
  trades: number;
  covered: boolean;
}
export interface Coverage {
  months: CoverageMonth[];
  covered_count: number;
  best_run: number;
  current_run: number;
  trade_count: number;
  unlocked: boolean;
  first_month: string | null;
  last_month: string | null;
  next_uncovered: string | null;
  progress: number;
  target_months: number;
  min_trades: number;
}

export interface Stats {
  trades: number;
  win_rate: number | null;
  total_r: number | null;
  avg_r: number | null;
  total_pnl: number | null;
  rules_followed_rate: number | null;
  profit_factor?: number | null;
  max_dd_r?: number | null;
}

export interface Strategy {
  id: number;
  name: string;
  description: string;
  instruments: string[];
  timeframes: string[];
  entry_models: string[];
  csv_timezone: "Europe/London" | "UTC";
  rules: Rule[];
  reasoning_template: TemplateField[];
  backtest_opened_early: boolean;
  owner_id: number;
  owner: PublicUser;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  stage: Stage;
  ideal_count: number;
  backtest_count: number;
  missed_count: number;
  range_start: string | null;
  range_end: string | null;
  coverage: Coverage;
  backtest_stats: Stats | null;
  sparkline: number[];
  last_trade_at: string | null;
  can_edit: boolean;
}

export interface Screenshot {
  id: number;
  trade_id: number;
  slot: Slot;
  position: number;
  width: number;
  height: number;
  bytes: number;
  content_type: string;
  captured_at: string | null;
  original_filename: string | null;
  created_at: string;
  full_url: string;
  thumb_url: string;
}

export interface Trade {
  id: number;
  strategy_id: number;
  session_id: number | null;
  owner_id: number;
  owner: PublicUser;
  kind: TradeKind;
  fx_id: string | null;
  instrument: string;
  side: Side;
  opened_at: string;
  closed_at: string | null;
  market_date: string;
  session_label: string;
  duration_seconds: number | null;
  entry_price: number | null;
  initial_sl: number | null;
  max_tp: number | null;
  ideal_tp: number | null;
  exit_price: number | null;
  sl_distance: number | null;
  tp_distance: number | null;
  tp_r: number | null;
  r_multiple: number | null;
  pnl: number | null;
  outcome: Outcome | null;
  entry_model: string | null;
  reasoning: Record<string, string>;
  notes: string;
  rules_followed: Record<string, boolean>;
  mae_r: number | null;
  mfe_r: number | null;
  news_impact: string | null;
  news_status?: "inside" | "outside" | "no_data";
  news_events?: { event_id: number; name: string; currency: string; at: string; minutes_from_entry: number }[] | null;
  annotated_at: string | null;
  tags: Tag[];
  screenshots: Screenshot[];
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  can_edit: boolean;
}

export interface SessionProgress {
  trades: number;
  screenshots: number;
  screenshots_target: number;
  reasons: number;
  reasons_target: number;
  completed: number;
}

export interface JournalSession {
  id: number;
  strategy_id: number;
  owner_id: number;
  owner: PublicUser;
  kind: SessionKind;
  csv_timezone: string;
  range_start: string | null;
  range_end: string | null;
  trade_count: number;
  source_filename: string | null;
  improve_note: string;
  import_report: Record<string, unknown> | null;
  undone_at: string | null;
  created_at: string;
  deleted_at: string | null;
  progress: SessionProgress;
  stats: Stats;
  can_edit: boolean;
}

export interface PreviewRow {
  fx_id: string;
  line: number;
  instrument: string;
  side: Side;
  opened_at: string;
  closed_at: string | null;
  opened_uk: string;
  pnl: number;
  r_multiple: number | null;
  outcome: Outcome | null;
  duplicate: { ideal: boolean; backtest: boolean };
  tags: string[];
}

export interface ImportPreview {
  filename: string;
  file_hash: string;
  timezone: string;
  rows_parsed: number;
  rows_total: number;
  problems: string[];
  unknown_columns: string[];
  range_start: string | null;
  range_end: string | null;
  winners: number;
  losers: number;
  breakevens: number;
  duplicates: { ideal: number; backtest: number };
  would_import: { ideal: number; backtest: number };
  breakeven_threshold: number;
  rows: PreviewRow[];
}

export interface ImportResult {
  session: JournalSession;
  report: { imported: number; duplicates: string[]; skipped_not_winners: number; problems: string[]; unresolved_tags: string[] };
  trades: Trade[];
}

export interface Match {
  file: string;
  trade_id: number | null;
  slot: Slot | null;
  confidence: "high" | "medium" | "low" | "none";
  reason: string;
}

export interface Profile {
  trades: number;
  avg_tp_distance: number | null;
  avg_sl_distance: number | null;
  avg_tp_r: number | null;
  avg_r: number | null;
  typical_duration_seconds: number | null;
  entry_hours: { label: string; count: number }[];
  sessions: { label: string; count: number }[];
  entry_models: { label: string; count: number }[];
  weekdays: { label: string; count: number }[];
  tags: { label: string; count: number }[];
  confluences: { label: string; count: number }[];
  instruments: { label: string; count: number }[];
  sides: { label: string; count: number }[];
}

export interface Brief {
  strategy: Strategy;
  profile: Profile | null;
  rules: Rule[];
  recent_improve_notes: { session_id: number; note: string; at: string; kind: SessionKind }[];
  next_uncovered: string | null;
  news: BriefNews | null;
}

export interface BriefNews {
  month: string | null;
  status: "ok" | "partial" | "no_data";
  high_count: number;
  events: NewsEvent[];
  note: string | null;
}

export interface Trash {
  days: number;
  strategies: Strategy[];
  sessions: JournalSession[];
  trades: Trade[];
}

export interface Summary {
  strategies: number;
  trades: number;
  unlocked: number;
  last_session: JournalSession | null;
  my_last_session: JournalSession | null;
}

export interface Instrument {
  id: number;
  symbol: string;
  name: string;
  asset_class: string;
  pip_size: number;
  unit: "pips" | "points";
  price_decimals: number;
  aliases: string[];
}

// ---- queries ----

export const keys = {
  strategies: (scope: string) => ["strategies", scope] as const,
  strategy: (id: number) => ["strategy", id] as const,
  trades: (id: number, kind?: string) => ["trades", id, kind ?? "all"] as const,
  trade: (id: number) => ["trade", id] as const,
  sessions: (id: number) => ["sessions", id] as const,
  session: (id: number) => ["session", id] as const,
  sessionTrades: (id: number) => ["session-trades", id] as const,
  profile: (id: number) => ["profile", id] as const,
  brief: (id: number) => ["brief", id] as const,
  trash: ["trash"] as const,
  summary: ["journal-summary"] as const,
  instruments: ["instruments"] as const,
};

export function useStrategies(scope: string) {
  return useQuery({ queryKey: keys.strategies(scope), queryFn: () => api.get<Strategy[]>(`/api/strategies?scope=${scope}`) });
}
export function useStrategy(id: number) {
  return useQuery({ queryKey: keys.strategy(id), queryFn: () => api.get<Strategy>(`/api/strategies/${id}`), enabled: Number.isFinite(id) });
}
export function useTrades(id: number, kind?: TradeKind) {
  return useQuery({
    queryKey: keys.trades(id, kind),
    queryFn: () => api.get<Trade[]>(`/api/strategies/${id}/trades${kind ? `?kind=${kind}` : ""}`),
    enabled: Number.isFinite(id),
  });
}
export function useTrade(id: number) {
  return useQuery({ queryKey: keys.trade(id), queryFn: () => api.get<Trade>(`/api/trades/${id}`), enabled: Number.isFinite(id) });
}
export function useSessions(id: number) {
  return useQuery({ queryKey: keys.sessions(id), queryFn: () => api.get<JournalSession[]>(`/api/strategies/${id}/sessions`), enabled: Number.isFinite(id) });
}
export function useSession(id: number) {
  return useQuery({ queryKey: keys.session(id), queryFn: () => api.get<JournalSession>(`/api/journal/sessions/${id}`), enabled: Number.isFinite(id) });
}
export function useSessionTrades(id: number) {
  return useQuery({ queryKey: keys.sessionTrades(id), queryFn: () => api.get<Trade[]>(`/api/journal/sessions/${id}/trades`), enabled: Number.isFinite(id) });
}
export function useProfile(id: number, enabled = true) {
  return useQuery({ queryKey: keys.profile(id), queryFn: () => api.get<Profile | null>(`/api/strategies/${id}/profile`), enabled: enabled && Number.isFinite(id) });
}
export function useBrief(id: number, enabled: boolean) {
  return useQuery({ queryKey: keys.brief(id), queryFn: () => api.get<Brief>(`/api/strategies/${id}/brief`), enabled });
}
export function useTrash() {
  return useQuery({ queryKey: keys.trash, queryFn: () => api.get<Trash>("/api/journal/trash") });
}
export function useSummary() {
  return useQuery({ queryKey: keys.summary, queryFn: () => api.get<Summary>("/api/journal/summary"), staleTime: 30_000 });
}
export function useInstruments() {
  return useQuery({ queryKey: keys.instruments, queryFn: () => api.get<Instrument[]>("/api/instruments"), staleTime: 300_000 });
}

/** Invalidate everything that shows a strategy's numbers after a change. */
export function useInvalidateJournal() {
  const qc = useQueryClient();
  return (strategyId?: number) => {
    void qc.invalidateQueries({ queryKey: ["strategies"] });
    void qc.invalidateQueries({ queryKey: keys.trash });
    void qc.invalidateQueries({ queryKey: keys.summary });
    if (strategyId !== undefined) {
      void qc.invalidateQueries({ queryKey: keys.strategy(strategyId) });
      void qc.invalidateQueries({ queryKey: ["trades", strategyId] });
      void qc.invalidateQueries({ queryKey: keys.sessions(strategyId) });
      void qc.invalidateQueries({ queryKey: keys.profile(strategyId) });
      void qc.invalidateQueries({ queryKey: keys.brief(strategyId) });
    }
    void qc.invalidateQueries({ queryKey: ["session"] });
    void qc.invalidateQueries({ queryKey: ["session-trades"] });
    void qc.invalidateQueries({ queryKey: ["trade"] });
  };
}

export type TradePatch = Omit<Partial<Trade>, "tags"> & { tags?: string[]; annotated?: boolean };

export function useUpdateTrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: TradePatch }) => api.patch<Trade>(`/api/trades/${id}`, body),
    onSuccess: (t) => {
      qc.setQueryData(keys.trade(t.id), t);
      qc.setQueryData<Trade[]>(keys.sessionTrades(t.session_id ?? -1), (list) => list?.map((x) => (x.id === t.id ? t : x)));
      void qc.invalidateQueries({ queryKey: ["trades", t.strategy_id] });
      void qc.invalidateQueries({ queryKey: ["session", t.session_id] });
      void qc.invalidateQueries({ queryKey: keys.strategy(t.strategy_id) });
    },
  });
}

/** Multipart upload of one screenshot (plus the browser-made thumbnail). */
export async function uploadScreenshot(
  tradeId: number,
  full: Blob,
  slot: Slot,
  opts: { thumb?: Blob; capturedAt?: Date | null; originalFilename?: string } = {},
): Promise<Trade> {
  const form = new FormData();
  form.append("file", full, opts.originalFilename ?? "screenshot.webp");
  form.append("slot", slot);
  if (opts.thumb) form.append("thumb", opts.thumb, "thumb.webp");
  if (opts.capturedAt) form.append("captured_at", opts.capturedAt.toISOString());
  if (opts.originalFilename) form.append("original_filename", opts.originalFilename);
  return api.upload<Trade>(`/api/trades/${tradeId}/screenshots`, form);
}

// ---- formatters ----

export const UK = "Europe/London";

export function fmtR(r: number | null | undefined, withSign = true): string {
  if (r === null || r === undefined || Number.isNaN(r)) return "—";
  const sign = r > 0 && withSign ? "+" : r < 0 ? "−" : "";
  return `${sign}${Math.abs(r).toFixed(2)}R`;
}

export function fmtPnl(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}$${Math.abs(v).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${Math.round(v * 100)}%`;
}

export function fmtPrice(v: number | null | undefined, decimals = 2): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-GB", { minimumFractionDigits: Math.min(decimals, 5), maximumFractionDigits: 5 });
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h < 24) return rest ? `${h}h ${rest}m` : `${h}h`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

export function fmtUkDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}
export function fmtUkTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}
export function fmtUkDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.length === 10 ? new Date(`${iso}T12:00:00Z`) : new Date(iso);
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, day: "numeric", month: "short", year: "numeric" }).format(d);
}
export function fmtMonth(key: string | null | undefined): string {
  if (!key) return "—";
  const [y, m] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric" }).format(new Date(Date.UTC(y, m - 1, 15)));
}
export function fmtRange(start: string | null, end: string | null): string {
  if (!start) return "No trades yet";
  if (!end || start === end) return fmtUkDate(start);
  return `${fmtUkDate(start)} – ${fmtUkDate(end)}`;
}

export const STAGE_LABEL: Record<Stage, string> = { ideal: "Ideal trades", ready: "Ready to backtest", backtesting: "Backtesting" };

export function outcomeTone(o: Outcome | null | undefined): "win" | "loss" | "breakeven" | "neutral" {
  return o ?? "neutral";
}

/** A trade "has a reason" once any template field or the notes carry text. */
export function hasReason(t: Trade): boolean {
  return Object.values(t.reasoning ?? {}).some((v) => String(v ?? "").trim()) || Boolean(t.notes?.trim());
}
/** What a "complete" trade would still be missing: named so the warning can list it. Never blocks. */
export function missingForCompletion(t: Trade): string[] {
  const out: string[] = [];
  const shots = (t.kind === "missed" ? (["entry"] as const) : LABELLED_SLOTS).filter((s) => !slotShot(t, s));
  if (shots.length) out.push(`${shots.map((s) => (t.kind === "missed" ? "the setup" : SLOT_LABEL[s])).join(", ")} ${shots.length === 1 ? "screenshot" : "screenshots"}`);
  if (!hasReason(t)) out.push("the reasoning");
  return out;
}

/** Completed is a manual mark Jamie sets once the three images and the reasoning are in. */
export function isCompleted(t: Trade): boolean {
  return t.annotated_at !== null;
}
export function slotShot(t: Trade, slot: Slot): Screenshot | undefined {
  return t.screenshots.find((s) => s.slot === slot);
}
