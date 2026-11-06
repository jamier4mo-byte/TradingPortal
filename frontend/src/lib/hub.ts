/** Hub engagement data (GET /api/hub) and the small per-device memories the Hub keeps in localStorage.
 * Mirrors backend/app/schemas/hub.py. */
import { useQuery } from "@tanstack/react-query";

import { api } from "./api.ts";

export interface StreakDay {
  date: string;
  active: boolean;
}
export interface Streak {
  current_days: number;
  best_days: number;
  active_today: boolean;
  last_active_date: string | null;
  days: StreakDay[];
}
export interface PersonalBest {
  key: "best_month_r" | "longest_rule_run";
  label: string;
  value: number;
  value_text: string;
  detail: string | null;
  achieved_at: string;
  is_new: boolean;
}
export interface Checklist {
  twelve_data_key: boolean;
  strategy_created: boolean;
  first_csv_imported: boolean;
  alerts_enabled: boolean;
  all_done_server: boolean;
}
export interface WeekRecap {
  show: boolean;
  week_start: string;
  week_end: string;
  sessions: number;
  trades: number;
  total_r: number | null;
  win_rate: number | null;
  rules_kept_rate: number | null;
  best_day: string | null;
  best_day_r: number | null;
}
export interface HubData {
  welcome_back: boolean;
  server_now: string;
  streak: Streak;
  personal_bests: PersonalBest[];
  checklist: Checklist;
  week_recap: WeekRecap;
}

export const hubKey = ["hub"] as const;

/** One call per Hub visit. Each call also records the visit, so it is not refetched on focus. */
export function useHub() {
  return useQuery({
    queryKey: hubKey,
    queryFn: () => api.get<HubData>("/api/hub"),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/** One reading of a query's five states for the cards that share it: offline with nothing cached is not
 * "loading" (no endless skeleton); an error with cached data still shows the data. */
export function queryState(q: { isPending: boolean; fetchStatus: string; data: unknown }): "offline" | "pending" | "error" | "ready" {
  if (q.data !== undefined) return "ready";
  if (q.fetchStatus === "paused") return "offline";
  if (q.isPending) return "pending";
  return "error";
}

// ---- per-device memories (localStorage; every access is guarded for private mode) ----

export function remember(key: string, value = "1"): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode */
  }
}
export function remembered(key: string): boolean {
  try {
    return localStorage.getItem(key) !== null;
  } catch {
    return false;
  }
}

/** Launch loader: the first launch of a tool each UK day plays the full ~600 ms; later ones ~250 ms. */
export const launchKey = (tool: string, ukDate: string) => `tp.launch.${tool}.${ukDate}`;
/** A personal best is celebrated once per device. */
export const celebratedKey = (key: string, achievedAt: string) => `tp.celebrated.${key}.${achievedAt}`;
/** "Install to the home screen" ticked by hand when the browser can't tell. */
export const INSTALL_DONE_KEY = "tp.install.done";

/** Running as an installed app (PWA)? */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const nav = navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches === true;
}
