/** UK time helpers. Sessions are approximate and in UK local time.
 *
 * Session hours (Hub hero, Foundations 1.1 and Engaging touches): Asia 00:00–08:00, London 08:00–16:30,
 * New York 13:30–21:00; the weekend runs from Friday 21:00 to Sunday 22:00. Mon–Thu 21:00–24:00 is
 * between sessions ("Markets closed – opens in …"). Sunday 22:00–24:00 counts as the first Asia session. */

const UK = "Europe/London";

export function ukParts(now: Date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: UK,
    hour: "2-digit",
    minute: "2-digit",
    weekday: "short",
    hourCycle: "h23",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return { hour: Number(get("hour")), minute: Number(get("minute")), weekday: get("weekday") };
}

export function ukClock(now: Date): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit" }).format(now);
}

/** "17:04:09" for the hero's live clock. */
export function ukClockSeconds(now: Date): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).format(now);
}

export function ukDate(now: Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: UK,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(now);
}

/** 1 → "1st", 2 → "2nd", 11 → "11th", 22 → "22nd". */
export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/** "Friday 17th October" (UK date, with an ordinal day). */
export function ukDateOrdinal(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: UK, weekday: "long", day: "numeric", month: "long" }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("weekday")} ${ordinal(Number(get("day")))} ${get("month")}`;
}

/** Morning before 12:00, afternoon until 17:00, evening after (1.1). Small hours keep "Good night". */
export function greeting(now: Date): string {
  const { hour } = ukParts(now);
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** Time-of-day ambience bands for the hero (Engaging touches): dawn 05–08, day 08–17, dusk 17–20, night 20–05. */
export type Daypart = "dawn" | "day" | "dusk" | "night";
export function daypart(now: Date): Daypart {
  const { hour } = ukParts(now);
  if (hour >= 5 && hour < 8) return "dawn";
  if (hour >= 8 && hour < 17) return "day";
  if (hour >= 17 && hour < 20) return "dusk";
  return "night";
}

export type Session = "Asia" | "London" | "London · New York" | "New York" | "Markets closed";

const ASIA_END = 8 * 60;
const LONDON_START = 8 * 60;
const LONDON_END = 16 * 60 + 30;
const NY_START = 13 * 60 + 30;
const NY_END = 21 * 60;
const WEEKEND_FROM = 21 * 60; // Friday
const WEEKEND_TO = 22 * 60; // Sunday
const DAY = 24 * 60;

function isWeekend(weekday: string, t: number): boolean {
  return weekday === "Sat" || (weekday === "Fri" && t >= WEEKEND_FROM) || (weekday === "Sun" && t < WEEKEND_TO);
}

export function session(now: Date): Session {
  const { hour, minute, weekday } = ukParts(now);
  const t = hour * 60 + minute;
  if (isWeekend(weekday, t)) return "Markets closed";
  const london = t >= LONDON_START && t < LONDON_END;
  const newYork = t >= NY_START && t < NY_END;
  if (london && newYork) return "London · New York";
  if (london) return "London";
  if (newYork) return "New York";
  if (t < ASIA_END || weekday === "Sun") return "Asia";
  return "Markets closed"; // Mon–Thu 21:00–24:00: between sessions
}

/** "1h 20m", "40m", "2d 3h". */
export function durationText(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const d = Math.floor(m / DAY);
  const h = Math.floor((m % DAY) / 60);
  const min = m % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return min ? `${h}h ${String(min).padStart(2, "0")}m` : `${h}h`;
  return `${min}m`;
}

export type SessionKey = "asia" | "london" | "newyork" | "closed";

export interface SessionStatus {
  /** Drives the hero ambience. */
  session: SessionKey;
  /** True while any session is open. */
  open: boolean;
  /** "London session · closes in 2h 05m", "Markets closed – weekend (opens Sunday 22:00)". */
  text: string;
}

const WEEKDAY_INDEX: Record<string, number> = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };

/** Minutes from Friday 21:00 (or the current moment, if later) to Sunday 22:00. */
function minutesToSundayOpen(weekday: string, t: number): number {
  const idx = WEEKDAY_INDEX[weekday] ?? 0; // Mon 0 … Sun 6
  const nowAbs = idx * DAY + t;
  const openAbs = 6 * DAY + WEEKEND_TO;
  return openAbs - nowAbs;
}

export function sessionStatus(now: Date): SessionStatus {
  const { hour, minute, weekday } = ukParts(now);
  const t = hour * 60 + minute;
  if (isWeekend(weekday, t)) {
    const left = minutesToSundayOpen(weekday, t);
    const soon = left <= 12 * 60 ? ` · opens in ${durationText(left)}` : " (opens Sunday 22:00)";
    return { session: "closed", open: false, text: `Markets closed – weekend${soon}` };
  }
  if (t >= LONDON_START && t < LONDON_END) {
    const both = t >= NY_START ? "London · New York" : "London";
    return { session: "london", open: true, text: `${both} session · London closes in ${durationText(LONDON_END - t)}` };
  }
  if (t >= NY_START && t < NY_END) {
    return { session: "newyork", open: true, text: `New York session · closes in ${durationText(NY_END - t)}` };
  }
  if (t < ASIA_END || weekday === "Sun") {
    const untilLondon = t < ASIA_END ? LONDON_START - t : DAY - t + LONDON_START;
    return { session: "asia", open: true, text: `Asia session · London opens in ${durationText(untilLondon)}` };
  }
  // Mon–Thu 21:00–24:00: nothing open until Asia at midnight.
  return { session: "closed", open: false, text: `Markets closed – opens in ${durationText(DAY - t)}` };
}
