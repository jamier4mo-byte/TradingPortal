/** Prices: types and queries. Every request goes to our backend, never to Twelve Data (F1).
 * Mirrors docs/build/prompt4-api.md (backend/app/schemas/prices.py). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api.ts";
import { useDevice } from "./useMediaQuery.ts";

export type QuoteStatus = "ok" | "stale" | "unavailable" | "no_key" | "error";

export interface Quote {
  symbol: string;
  code: string | null;
  name: string;
  unit: string;
  decimals: number;
  status: QuoteStatus;
  price: number | null;
  change: number | null;
  percent_change: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  previous_close: number | null;
  is_market_open: boolean | null;
  market_time: string | null;
  updated_at: string | null;
  message: string | null;
}

export interface Usage {
  provider: "twelve_data" | "fake";
  has_key: boolean;
  used: number;
  limit: number;
  background_used: number;
  background_cap: number;
  allow_background_jobs: boolean;
  resets_at: string;
  paused: boolean;
  paused_reason: string | null;
}

export interface Pin {
  symbol: string;
  code: string | null;
  name: string;
  position: number;
}

export interface SearchResult {
  symbol: string;
  code: string | null;
  name: string;
  exchange: string;
  type: string;
  available: boolean | null;
}

export interface Sparkline {
  symbol: string;
  status: string;
  interval: string;
  points: { t: string; v: number }[];
  updated_at: string | null;
}

/** 15 minutes on desktop and tablet, 30 on the phone (Devices: refresh less often on mobile). Paused when
 * the tab is hidden: TanStack Query doesn't refetch on an interval in the background by default. */
export function useRefreshMs(): number {
  return useDevice() === "phone" ? 30 * 60_000 : 15 * 60_000;
}

export function useQuotes(enabled = true) {
  const every = useRefreshMs();
  return useQuery({
    queryKey: ["prices", "quotes"],
    queryFn: () => api.get<{ quotes: Quote[]; usage: Usage; refresh_seconds: number }>("/api/prices/quotes"),
    refetchInterval: every,
    refetchIntervalInBackground: false,
    enabled,
  });
}
export function useQuote(symbol: string) {
  const every = useRefreshMs();
  return useQuery({
    queryKey: ["prices", "quote", symbol],
    queryFn: () => api.get<Quote>(`/api/prices/quote?symbol=${encodeURIComponent(symbol)}`),
    refetchInterval: every,
  });
}
export function useSparkline(symbol: string, enabled = true) {
  const every = useRefreshMs();
  return useQuery({
    queryKey: ["prices", "sparkline", symbol],
    queryFn: () => api.get<Sparkline>(`/api/prices/sparkline?symbol=${encodeURIComponent(symbol)}`),
    refetchInterval: every,
    enabled,
  });
}
export function usePins() {
  return useQuery({ queryKey: ["prices", "pins"], queryFn: () => api.get<{ pins: Pin[]; max: number }>("/api/prices/pins") });
}
export function useUsage() {
  return useQuery({ queryKey: ["prices", "usage"], queryFn: () => api.get<Usage>("/api/prices/usage"), refetchInterval: 60_000 });
}
export function useSearch(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ["prices", "search", term.toLowerCase()],
    queryFn: () => api.get<{ results: SearchResult[]; cached: boolean }>(`/api/prices/search?q=${encodeURIComponent(term)}`),
    enabled: term.length >= 2,
    staleTime: 24 * 3600_000,
  });
}

export function usePinMutations() {
  const qc = useQueryClient();
  const done = () => void qc.invalidateQueries({ queryKey: ["prices"] });
  return {
    pin: useMutation({ mutationFn: (symbol: string) => api.post<Pin>("/api/prices/pins", { symbol }), onSuccess: done }),
    unpin: useMutation({ mutationFn: (symbol: string) => api.delete(`/api/prices/pins?symbol=${encodeURIComponent(symbol)}`), onSuccess: done }),
    reorder: useMutation({ mutationFn: (symbols: string[]) => api.put("/api/prices/pins/order", { symbols }), onSuccess: done }),
  };
}

export function useSaveMarketSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Pick<Usage, "allow_background_jobs" | "background_cap">>) =>
      api.patch<Usage>("/api/prices/settings", {
        allow_background_jobs: body.allow_background_jobs,
        background_daily_cap: body.background_cap,
      }),
    onSuccess: (u) => qc.setQueryData(["prices", "usage"], u),
  });
}

// ---- formatting ----

export function formatPrice(v: number | null | undefined, decimals = 5): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return v.toLocaleString("en-GB", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** Signed with a real minus sign: "+0.00280", "−12.5". */
export function signed(v: number | null | undefined, decimals = 2, suffix = ""): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const s = Math.abs(v).toLocaleString("en-GB", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${s}${suffix}`;
}

/** Our codes read better with a slash: EURUSD → EUR/USD; indices and crypto keep theirs. */
export function displaySymbol(code: string | null, symbol: string): string {
  if (code && /^[A-Z]{6}$/.test(code)) return `${code.slice(0, 3)}/${code.slice(3)}`;
  return code ?? symbol;
}
