/** Team calendar (1.4): types mirroring backend/app/schemas/calendar.py, TanStack queries with optimistic
 * updates, and UK wall-clock helpers. Times travel as UTC ISO strings; the calendar shows UK time. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, type PublicUser } from "./api.ts";
import { addDays, mondayOf, ukISODate } from "./news.ts";

export type Category = "backtesting" | "review" | "admin" | "other";
export type Mode = "series" | "occurrence";

export const CATEGORIES: { value: Category; label: string; short: string }[] = [
  { value: "backtesting", label: "Backtesting", short: "BT" },
  { value: "review", label: "Review", short: "Rev" },
  { value: "admin", label: "Admin", short: "Adm" },
  { value: "other", label: "Other", short: "Oth" },
];

export interface Task {
  id: number;
  title: string;
  description: string | null;
  category: Category;
  category_label: string;
  all_day: boolean;
  start_at: string;
  end_at: string | null;
  tz: string;
  rrule: string | null;
  recurring: boolean;
  owner: PublicUser;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}

export interface Occurrence {
  id: string;
  task_id: number;
  occurrence_date: string;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  title: string;
  description: string | null;
  category: Category;
  category_label: string;
  tz: string;
  owner: PublicUser;
  done: boolean;
  completed_by: PublicUser | null;
  completed_at: string | null;
  recurring: boolean;
  exception: boolean;
  can_edit: boolean;
}

export interface OccurrencesAnswer {
  occurrences: Occurrence[];
  from: string;
  to: string;
  owners: PublicUser[];
}

export interface TaskIn {
  title: string;
  description?: string | null;
  category: Category;
  all_day: boolean;
  start_at: string;
  end_at?: string | null;
  tz?: string;
  rrule?: string | null;
}

export interface TaskPatch extends Partial<TaskIn> {
  mode?: Mode;
  occurrence_date?: string;
}

export interface Completion {
  task_id: number;
  occurrence_date: string;
  done: boolean;
  completed_by: PublicUser | null;
  completed_at: string | null;
}

// ---- queries ----

const KEY = ["calendar"] as const;

export function occurrencesKey(from: string, to: string, owners?: number[]) {
  return [...KEY, "occurrences", from, to, owners && owners.length ? [...owners].sort((a, b) => a - b).join(",") : "all"] as const;
}

/** Occurrences between two UK dates (both inclusive, at most 62 days). `owners` narrows to those user ids. */
export function useOccurrences(from: string, to: string, owners?: number[], enabled = true) {
  const p = new URLSearchParams({ from, to });
  if (owners && owners.length) p.set("owners", owners.join(","));
  return useQuery({
    queryKey: occurrencesKey(from, to, owners),
    queryFn: () => api.get<OccurrencesAnswer>(`/api/calendar/occurrences?${p.toString()}`),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
    enabled,
  });
}

export function useTask(id: number | null) {
  return useQuery({ queryKey: [...KEY, "task", id], queryFn: () => api.get<Task>(`/api/calendar/tasks/${id}`), enabled: id !== null && id > 0 });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TaskIn) => api.post<Task>("/api/calendar/tasks", body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: TaskPatch & { id: number }) => api.patch<Task>(`/api/calendar/tasks/${id}`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, mode, occurrence_date }: { id: number; mode?: Mode; occurrence_date?: string }) => {
      const p = new URLSearchParams();
      if (mode) p.set("mode", mode);
      if (occurrence_date) p.set("occurrence_date", occurrence_date);
      const qs = p.toString();
      return api.delete<{ ok: boolean; message: string }>(`/api/calendar/tasks/${id}${qs ? `?${qs}` : ""}`);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
}

type Snapshot = [readonly unknown[], OccurrencesAnswer | undefined][];

function patchOccurrences(qc: ReturnType<typeof useQueryClient>, fn: (o: Occurrence) => Occurrence): Snapshot {
  const snapshot = qc.getQueriesData<OccurrencesAnswer>({ queryKey: [...KEY, "occurrences"] });
  for (const [key, data] of snapshot) {
    if (!data) continue;
    qc.setQueryData<OccurrencesAnswer>(key, { ...data, occurrences: data.occurrences.map(fn) });
  }
  return snapshot;
}

function restore(qc: ReturnType<typeof useQueryClient>, snapshot: Snapshot | undefined) {
  for (const [key, data] of snapshot ?? []) qc.setQueryData(key, data);
}

/** Mark an occurrence done (or not). Optimistic: the row flips at once and rolls back if the save fails. */
export function useCompleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ task_id, occurrence_date, done }: { task_id: number; occurrence_date: string; done: boolean }) =>
      done
        ? api.post<Completion>(`/api/calendar/tasks/${task_id}/complete`, { occurrence_date })
        : api.delete<Completion>(`/api/calendar/tasks/${task_id}/complete?occurrence_date=${occurrence_date}`),
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: [...KEY, "occurrences"] });
      return patchOccurrences(qc, (o) =>
        o.task_id === vars.task_id && o.occurrence_date === vars.occurrence_date
          ? { ...o, done: vars.done, completed_at: vars.done ? new Date().toISOString() : null }
          : o,
      );
    },
    onError: (_err, _vars, snapshot) => restore(qc, snapshot),
    onSettled: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
}

/** Move an occurrence (or its whole series) to a new start. Optimistic for the dragged occurrence. */
export function useMoveTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ task_id, ...body }: { task_id: number; occurrence_date: string; start_at: string; end_at?: string | null; mode: Mode }) =>
      api.patch<Task>(`/api/calendar/tasks/${task_id}`, body),
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: [...KEY, "occurrences"] });
      return patchOccurrences(qc, (o) =>
        o.task_id === vars.task_id && o.occurrence_date === vars.occurrence_date
          ? { ...o, start_at: vars.start_at, end_at: vars.end_at === undefined ? o.end_at : vars.end_at }
          : o,
      );
    },
    onError: (_err, _vars, snapshot) => restore(qc, snapshot),
    onSettled: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
}

// ---- UK wall-clock helpers ----
// FullCalendar runs with timeZone "UTC" and is fed UK wall-clock strings without an offset, so what it
// shows is UK time whatever the browser's zone. These convert between real UTC instants and that space.

const UK = "Europe/London";
const wallFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: UK,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** "2026-11-09T09:00:00": the UK wall clock of a UTC instant. */
export function ukWall(iso: string | Date): string {
  const parts = wallFmt.formatToParts(typeof iso === "string" ? new Date(iso) : iso);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}:${get("second")}`;
}

/** UK offset (ms) in force at a UTC instant. */
function ukOffsetAt(ms: number): number {
  const wall = ukWall(new Date(ms));
  const asUtc = Date.UTC(+wall.slice(0, 4), +wall.slice(5, 7) - 1, +wall.slice(8, 10), +wall.slice(11, 13), +wall.slice(14, 16), +wall.slice(17, 19));
  return asUtc - ms;
}

/** The UTC instant (ISO) of a UK wall-clock "YYYY-MM-DDTHH:mm[:ss]". Handles the clock changes. */
export function ukWallToUtc(wall: string): string {
  const y = +wall.slice(0, 4);
  const mo = +wall.slice(5, 7) - 1;
  const d = +wall.slice(8, 10);
  const h = +(wall.slice(11, 13) || "0");
  const mi = +(wall.slice(14, 16) || "0");
  const guess = Date.UTC(y, mo, d, h, mi);
  let ms = guess - ukOffsetAt(guess);
  // One more pass for instants right at a transition.
  const again = guess - ukOffsetAt(ms);
  if (again !== ms) ms = again;
  return new Date(ms).toISOString();
}

/** The UK calendar date of a UTC instant. */
export function ukDateOf(iso: string): string {
  return ukISODate(new Date(iso));
}

/** "09:00" in UK time. */
export function ukClockOf(iso: string): string {
  return ukWall(iso).slice(11, 16);
}

/** First day of the month of `iso` (YYYY-MM-DD). */
export function firstOfMonth(iso: string): string {
  return `${iso.slice(0, 7)}-01`;
}

export function addMonths(iso: string, months: number): string {
  const [y, m] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1 + months, 1));
  return dt.toISOString().slice(0, 10);
}

/** Date range (UK dates, both inclusive) a calendar view shows for an anchor date. */
export function viewRange(view: CalendarView, date: string): { from: string; to: string } {
  if (view === "day") return { from: date, to: date };
  if (view === "3day") return { from: date, to: addDays(date, 2) };
  if (view === "week") {
    const mon = mondayOf(date);
    return { from: mon, to: addDays(mon, 6) };
  }
  const first = firstOfMonth(date);
  const last = addDays(addMonths(first, 1), -1);
  const from = mondayOf(first);
  const to = addDays(mondayOf(last), 6);
  return { from, to };
}

export type CalendarView = "day" | "3day" | "week" | "month";

export function stepDate(view: CalendarView, date: string, dir: 1 | -1): string {
  if (view === "day") return addDays(date, dir);
  if (view === "3day") return addDays(date, 3 * dir);
  if (view === "week") return addDays(date, 7 * dir);
  return addMonths(firstOfMonth(date), dir);
}

export function monthLabel(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", month: "long", year: "numeric" }).format(new Date(Date.UTC(y, m - 1, 1)));
}

/** "9 – 15 Nov 2026" / "30 Nov – 6 Dec 2026" / "Monday 9 November 2026". */
export function rangeLabel(view: CalendarView, date: string): string {
  const { from, to } = viewRange(view, date);
  if (view === "month") return monthLabel(date);
  const fmt = (iso: string, opts: Intl.DateTimeFormatOptions) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", ...opts }).format(new Date(Date.UTC(y, m - 1, d)));
  };
  if (view === "day") return fmt(from, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const sameMonth = from.slice(0, 7) === to.slice(0, 7);
  return sameMonth
    ? `${fmt(from, { day: "numeric" })} – ${fmt(to, { day: "numeric", month: "short", year: "numeric" })}`
    : `${fmt(from, { day: "numeric", month: "short" })} – ${fmt(to, { day: "numeric", month: "short", year: "numeric" })}`;
}

// ---- repeat presets ----

export type RepeatPreset = "none" | "daily" | "weekdays" | "weekly" | "monthly" | "custom";

export const REPEAT_OPTIONS: { value: RepeatPreset; label: string }[] = [
  { value: "none", label: "Does not repeat" },
  { value: "daily", label: "Daily" },
  { value: "weekdays", label: "Weekdays (Mon–Fri)" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "custom", label: "Custom (RRULE)" },
];

export const PRESET_RULES: Record<Exclude<RepeatPreset, "none" | "custom">, string> = {
  daily: "FREQ=DAILY",
  weekdays: "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
  weekly: "FREQ=WEEKLY",
  monthly: "FREQ=MONTHLY",
};

export function presetFor(rrule: string | null | undefined): RepeatPreset {
  if (!rrule) return "none";
  const hit = (Object.entries(PRESET_RULES) as [RepeatPreset, string][]).find(([, r]) => r === rrule);
  return hit ? hit[0] : "custom";
}

export function repeatLabel(rrule: string | null | undefined): string {
  const preset = presetFor(rrule);
  if (preset === "custom") return `Repeats · ${rrule}`;
  return REPEAT_OPTIONS.find((o) => o.value === preset)?.label ?? "Does not repeat";
}

// ---- remembered owner filter ----

const HIDDEN_KEY = "tp.calendar.hiddenOwners";
const NEWS_KEY = "tp.calendar.news";

/** Owner ids hidden from the calendar (everyone is on by default), remembered per browser. */
export function useHiddenOwners(): [number[], (next: number[]) => void] {
  const [hidden, setHidden] = useState<number[]>(() => {
    try {
      const raw = localStorage.getItem(HIDDEN_KEY);
      const list = raw ? (JSON.parse(raw) as unknown) : [];
      return Array.isArray(list) ? list.filter((n): n is number => typeof n === "number") : [];
    } catch {
      return [];
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(HIDDEN_KEY, JSON.stringify(hidden));
    } catch {
      /* private mode */
    }
  }, [hidden]);
  return [hidden, setHidden];
}

export function useShowNews(): [boolean, (v: boolean) => void] {
  const [show, setShow] = useState<boolean>(() => {
    try {
      return localStorage.getItem(NEWS_KEY) !== "0";
    } catch {
      return true;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(NEWS_KEY, show ? "1" : "0");
    } catch {
      /* private mode */
    }
  }, [show]);
  return [show, setShow];
}

/** Occurrences grouped by UK date, in order, for a list of dates (empty days included). */
export function groupByDay(occurrences: Occurrence[], dates: string[]): { date: string; items: Occurrence[] }[] {
  const map = new Map<string, Occurrence[]>(dates.map((d) => [d, []]));
  for (const o of occurrences) {
    const d = ukDateOf(o.start_at);
    if (!map.has(d)) map.set(d, []);
    map.get(d)!.push(o);
  }
  return [...map.entries()].map(([date, items]) => ({ date, items }));
}

export function datesBetween(from: string, to: string): string[] {
  const out: string[] = [];
  for (let d = from; d <= to; d = addDays(d, 1)) out.push(d);
  return out;
}
