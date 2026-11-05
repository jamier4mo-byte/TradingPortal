/** UK time helpers. Sessions are approximate and in UK local time. */

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

export function ukDate(now: Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: UK,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(now);
}

export function greeting(now: Date): string {
  const { hour } = ukParts(now);
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export type Session = "Asia" | "London" | "London · New York" | "New York" | "Markets closed";

export function session(now: Date): Session {
  const { hour, minute, weekday } = ukParts(now);
  if (weekday === "Sat" || weekday === "Sun") return "Markets closed";
  const t = hour * 60 + minute;
  const london = t >= 8 * 60 && t < 16 * 60 + 30;
  const newYork = t >= 13 * 60 + 30 && t < 21 * 60;
  if (london && newYork) return "London · New York";
  if (london) return "London";
  if (newYork) return "New York";
  return "Asia";
}
