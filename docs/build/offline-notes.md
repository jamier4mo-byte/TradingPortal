# Offline mode and the service worker

Foundations → *Devices → On the phone like an app*: "the last-loaded Hub, prices and today's events stay viewable without signal, clearly marked as offline." The worker is hand-written in `frontend/public/sw.js` (no Workbox); the page side is `lib/offline.ts`, `lib/api.ts` (`cachedAt`) and `main.tsx`.

## What is cached

| Cache | Contents | Strategy | Lifetime |
|---|---|---|---|
| `tp-shell-v1` | `/`, `/index.html`, `/site.webmanifest`, the favicons, `apple-touch-icon-180.png`, `/brand/*.png`, and every hashed `/assets/*` chunk the page loads (the entry chunks are precached from `index.html` at install) | `/assets/*`: cache-first (Vite hashes them; a URL never changes content). Navigations: network-first, cached `index.html` as the fallback. Other shell files: cached copy first, refreshed in the background | Until the cache version changes |
| `tp-api-v1` | GET answers for `/api/hub`, `/api/news/today`, `/api/news/next`, `/api/news/events` (**only** when `from` and `to` are today, UK), `/api/prices/quotes`, `/api/prices/pins`, `/api/calendar/occurrences`, `/api/journal/summary`, `/api/auth/me` | Network-first with a 4 s timeout, then the cache. Only `2xx` answers are stored. A slow network still refreshes the cache once it answers | Replaced on every successful fetch; the oldest entries go once there are more than 40 (calendar ranges can pile up); the whole cache is deleted on `POST /api/auth/logout` or a `{type:"signed-out"}` message |

Each cached API answer carries an `X-TP-Cached-At` header (the time it was stored). `api.get` remembers it per path (`cachedAt(path)` in `lib/api.ts`); `useStaleness` in `lib/offline.ts` turns that plus `navigator.onLine` into "Last updated HH:MM" for the Hub cards and the calendar card (`StaleFigures` in `pages/hub/StaleStamp.tsx`).

The startup images (`/startup-*.png`) are not precached: iOS fetches them when the app is installed.

## What is never cached

- Anything non-GET.
- `/api/auth/*` except `/api/auth/me` (so the shell knows who you are offline); `/api/admin/*`; `/api/me/*`.
- Screenshots (`/api/screenshots/{id}/thumb|full`): private images, always from the network. No thumbnail LRU either: the journal is online-only by design, and the browser's own HTTP cache already honours the `private, max-age=31536000, immutable` the backend sends.
- Every other API route (journal, strategies, trades, news detail, settings, alerts).
- Cross-origin requests.

`Cache-Control: no-store` / `private` on the allow-listed routes is not honoured by the worker on purpose: these answers are stored precisely so the last-loaded Hub is viewable offline, they are per browser profile on a single-user device, and they are cleared on sign-out. Everything else respects the server's headers because the worker never stores it.

## Query behaviour offline

`main.tsx` sets TanStack Query's `networkMode` to `offlineFirst` for queries and mutations. A query always fires once (so the worker can answer from its cache); if that fails while offline, retries pause and the cards read `fetchStatus === "paused"` as their "You're offline" empty state. A write fires once and fails fast; `api.ts` turns the fetch failure into `ApiError(0, "You're offline: changes will need a connection")`, which the calendar's optimistic Done surfaces in its toast after rolling back.

## Updates

A new `sw.js` installs in the background but **waits**: it never `skipWaiting`s on its own, so a running page keeps the chunks it was built with. The shell shows "A new version is ready · Reload" (`components/UpdateReady.tsx`); Reload posts `{type:"skip-waiting"}`, the worker takes over, and `main.tsx` reloads the page on `controllerchange` (a first install, which claims the page via `clients.claim()`, does not reload it).

`/sw.js` is served by FastAPI's `FileResponse` with no `Cache-Control`; browsers revalidate the worker script itself on every check regardless (the `updateViaCache` default), so that is fine. `index.html` is `no-cache`.

## Bumping the cache version

Change `const VERSION = "v1"` in `sw.js`. On `activate` the worker deletes every `tp-*` cache that isn't the current shell or API cache. Bump it when the shell list changes shape or when cached API answers become incompatible with the UI; routine deploys don't need it (hashed assets have new URLs, `index.html` is network-first, API answers refresh on the next fetch).

## Testing

`frontend/e2e/offline.spec.ts`: signs in, waits for the worker to control the page, reloads once online so the shell and the Hub's answers go through the worker, then `context.setOffline(true)` + reload and asserts the greeting, the offline banner, a "Last updated" stamp and no page errors; back online, the banner goes. A second test lists every cached URL and asserts none is a private route; a third checks `/sw.js` is JavaScript and not long-cacheable.
