/** News Room types and queries. Mirrors docs/build/prompt4-api.md (backend/app/schemas/news.py). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api.ts";

export type Impact = "high" | "medium" | "low" | "holiday" | "none";

export interface Surprise {
  direction: "up" | "down" | "inline";
  diff: number;
  diff_text: string;
  better: boolean | null;
  wording: string;
}

export interface NewsEvent {
  id: number;
  title: string;
  name: string;
  currency: string;
  at: string;
  uk_date: string;
  uk_time: string;
  all_day: boolean;
  impact: Impact;
  impact_label: string;
  forecast: string | null;
  previous: string | null;
  actual: string | null;
  revised: string | null;
  released: boolean;
  surprise: Surprise | null;
  instruments: string[];
  mine: boolean;
  event_type_id: number | null;
  has_explanation: boolean;
}

export interface EventsAnswer {
  events: NewsEvent[];
  from: string;
  to: string;
  last_updated_at: string | null;
  window_minutes: number;
  my_instruments: string[];
}

export interface HorizonReaction {
  status: string;
  range: number | null;
  move: number | null;
  direction: "up" | "down" | "flat" | null;
}

export interface InstrumentReactions {
  instrument: string;
  unit: string;
  releases: number;
  average_range: Record<string, number | null>;
  rows: { event_id: number; at: string; horizons: Record<string, HorizonReaction> }[];
}

export interface EventDetail {
  event: NewsEvent;
  type: {
    id: number;
    name: string;
    category: string;
    explanation: string | null;
    why_it_matters: string | null;
    higher_is_better: boolean | null;
  } | null;
  history: { event_id: number; at: string; actual: string | null; forecast: string | null; previous: string | null; surprise: Surprise | null }[];
  reactions: InstrumentReactions[];
  summary: string | null;
  empty: { history: string | null; reactions: string | null };
}

export interface NewsStatus {
  last_updated_at: string | null;
  feeds: { feed: string; last_success_at: string | null; last_attempt_at: string | null; last_status: string | null; last_error: string | null }[];
  coverage: { source: string; start_date: string; end_date: string }[];
  jblanked: { configured: boolean; requests_today: number; daily_budget: number; next_slot_at: string | null };
}

export interface WeekAhead {
  start: string;
  end: string;
  default_view: boolean;
  days: { date: string; label: string; events: NewsEvent[] }[];
}

export interface Timeline {
  date: string;
  window_minutes: number;
  sessions: { name: "Asia" | "London" | "New York"; start: string; end: string }[];
  events: NewsEvent[];
  windows: { event_id: number; start: string; end: string }[];
}

export interface NewsPrefs {
  instruments: string[];
  news_window_minutes: number;
  available: { code: string; name: string }[];
}

export interface NextEvent {
  event: NewsEvent | null;
  seconds_until: number | null;
  server_now: string;
}

/** GET /api/news/today: the Hub's headline ("3 high-impact events today – USD CPI at 13:30"). */
export interface TodayOut {
  headline: string;
  high_count: number;
  events: NewsEvent[];
  last_updated_at: string | null;
}

export const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "CNY"] as const;
export const IMPACT_ORDER: Impact[] = ["high", "medium", "low", "holiday", "none"];

export interface EventFilters {
  from: string;
  to: string;
  currencies: string[];
  impacts: Impact[];
  mine: boolean;
}

function qs(f: EventFilters): string {
  const p = new URLSearchParams({ from: f.from, to: f.to });
  if (f.currencies.length) p.set("currencies", f.currencies.join(","));
  if (f.impacts.length) p.set("impacts", f.impacts.join(","));
  if (f.mine) p.set("mine", "1");
  return p.toString();
}

/** News changes slowly: refetch every 5 minutes while the tab is visible (TanStack pauses when hidden). */
const NEWS_REFRESH = 5 * 60_000;

export function useEvents(f: EventFilters) {
  return useQuery({
    queryKey: ["news", "events", f],
    queryFn: () => api.get<EventsAnswer>(`/api/news/events?${qs(f)}`),
    refetchInterval: NEWS_REFRESH,
    placeholderData: (prev) => prev,
  });
}
export function useEventDetail(id: number) {
  return useQuery({ queryKey: ["news", "event", id], queryFn: () => api.get<EventDetail>(`/api/news/events/${id}`), enabled: id > 0 });
}
export function useToday() {
  return useQuery({ queryKey: ["news", "today"], queryFn: () => api.get<TodayOut>("/api/news/today"), refetchInterval: NEWS_REFRESH });
}
export function useNextEvent(mine = true) {
  return useQuery({
    queryKey: ["news", "next", mine],
    queryFn: () => api.get<NextEvent>(`/api/news/next?mine=${mine ? 1 : 0}`),
    refetchInterval: 60_000,
  });
}
export function useWeekAhead(start?: string) {
  return useQuery({
    queryKey: ["news", "week", start ?? "default"],
    queryFn: () => api.get<WeekAhead>(`/api/news/week-ahead${start ? `?start=${start}` : ""}`),
    refetchInterval: NEWS_REFRESH,
  });
}
export function useTimeline(date: string) {
  return useQuery({
    queryKey: ["news", "timeline", date],
    queryFn: () => api.get<Timeline>(`/api/news/timeline?date=${date}`),
    refetchInterval: NEWS_REFRESH,
  });
}
export function useNewsStatus() {
  return useQuery({ queryKey: ["news", "status"], queryFn: () => api.get<NewsStatus>("/api/news/status"), refetchInterval: NEWS_REFRESH });
}
export function useNewsPrefs() {
  return useQuery({ queryKey: ["news", "prefs"], queryFn: () => api.get<NewsPrefs>("/api/news/prefs") });
}
export function useSaveNewsPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Pick<NewsPrefs, "instruments" | "news_window_minutes">>) => api.patch<NewsPrefs>("/api/news/prefs", body),
    onSuccess: (p) => {
      qc.setQueryData(["news", "prefs"], p);
      void qc.invalidateQueries({ queryKey: ["news"] });
    },
  });
}

// ---- dates in UK time ----

const UK = "Europe/London";

/** "2026-11-06" for the UK calendar date of `d`. */
export function ukISODate(d: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: UK, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return parts; // en-CA formats as YYYY-MM-DD
}

/** Add whole days to a YYYY-MM-DD date (calendar arithmetic, no time zone involved). */
export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return dt.toISOString().slice(0, 10);
}

/** Monday of the week containing `iso` (YYYY-MM-DD). */
export function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const wd = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 = Sunday
  return addDays(iso, wd === 0 ? -6 : 1 - wd);
}

export function dayLabel(iso: string, style: "long" | "short" = "long"): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    weekday: style,
    day: "numeric",
    month: style === "long" ? "long" : "short",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function ukTime(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

/** "2h 05m", "14m 08s", "45s". */
export function countdownText(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}
