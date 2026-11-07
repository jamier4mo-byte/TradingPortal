/** Light offline mode (Foundations: Devices → On the phone like an app).
 *
 * The service worker (public/sw.js) keeps the app shell and a short allow-list of GET API answers. When it
 * serves one from its cache it stamps the response with X-TP-Cached-At; `api.get` remembers that per path
 * (see `cachedAt` in lib/api.ts). This module turns that, plus `navigator.onLine`, into one reading a card
 * can use to dim its figures and show "Last updated HH:MM", and carries the "new version ready" event from
 * main.tsx (outside React) to the shell. */
import { useEffect, useState } from "react";

import { cachedAt } from "./api.ts";
import { useOnline } from "./useMediaQuery.ts";

export { cachedAt, useOnline };

export interface Staleness {
  /** Offline, or the data on screen came from the service worker's cache rather than the server. */
  stale: boolean;
  /** When the figures were last fetched from the server, if known. */
  at: Date | null;
  /** "Last updated HH:MM" (UK time), or null when there's nothing to say. */
  label: string | null;
}

const UK_CLOCK = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" });

/** One reading for a card: `paths` are the API paths it shows (query strings optional), `dataUpdatedAt` the
 * TanStack Query stamp of the newest of them (used when the answer came from the network but we're offline). */
export function useStaleness(paths: string[], dataUpdatedAt: number | undefined | null): Staleness {
  const online = useOnline();
  const stamps = paths.map(cachedAt).filter((n): n is number => n !== null);
  const fromCache = stamps.length > 0;
  const stale = !online || fromCache;
  const ms = fromCache ? Math.max(...stamps) : dataUpdatedAt || null;
  const at = stale && ms ? new Date(ms) : null;
  return { stale, at, label: at ? `Last updated ${UK_CLOCK.format(at)}` : null };
}

// ---- service worker updates ----

const updates = new EventTarget();
let waiting: ServiceWorker | null = null;

/** main.tsx: a new service worker has installed and is waiting. */
export function announceUpdate(worker: ServiceWorker): void {
  waiting = worker;
  updates.dispatchEvent(new Event("update"));
}

/** Tell the waiting worker to take over; the page reloads when it does (controllerchange in main.tsx). */
export function applyUpdate(): void {
  if (waiting) waiting.postMessage({ type: "skip-waiting" });
  else window.location.reload();
}

/** True once a new version is installed and waiting for a reload. */
export function useUpdateReady(): boolean {
  const [ready, setReady] = useState(waiting !== null);
  useEffect(() => {
    const on = () => setReady(true);
    updates.addEventListener("update", on);
    return () => updates.removeEventListener("update", on);
  }, []);
  return ready;
}
