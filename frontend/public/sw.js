/* Trading Portal service worker: Web Push notifications (F7) and the light offline mode (Prompt 5).
 *
 * Caches (bump VERSION to invalidate both; `activate` deletes every other tp-* cache):
 *   tp-shell-v1  the app shell: "/", index.html, the manifest, icons, brand marks, and the hashed /assets
 *                chunks (cache-first: Vite hashes them, so a URL never changes content).
 *   tp-api-v1    the allow-listed GET API answers (network-first, 4 s timeout, cache fallback), each stamped
 *                with X-TP-Cached-At so the page can say "Last updated HH:MM".
 * Never cached: anything non-GET, /api/auth/* (except /api/auth/me), /api/admin/*, /api/me/*, screenshots
 * (/api/screenshots/*: private images, served straight from the network), and every other API route.
 * The API cache is cleared on every sign-in or sign-out POST, on a {type:"signed-out"} message, and whenever an
 * allow-listed route answers 401/403. A navigation is stored as the shell only when it is HTML outside /api/.
 *
 * Push payload from the server: { title, body, url, tag, event_id, chime }. */

const VERSION = "v1";
const SHELL_CACHE = `tp-shell-${VERSION}`;
const API_CACHE = `tp-api-${VERSION}`;
// POSTs that change who is signed in (exact paths from backend/app/api/auth.py): login, logout, passkey login,
// accepting an invite, resetting a password.
const AUTH_CHANGE = new Set([
  "/api/auth/login",
  "/api/auth/logout",
  "/api/auth/passkey/login/begin",
  "/api/auth/passkey/login/finish",
  "/api/auth/invite/accept",
  "/api/auth/reset",
]);
const API_TIMEOUT_MS = 4000;
const API_MAX_ENTRIES = 40;
const CACHED_AT = "X-TP-Cached-At";

const SHELL_URLS = [
  "/",
  "/index.html",
  "/site.webmanifest",
  "/favicon.ico",
  "/favicon-32.png",
  "/favicon-192.png",
  "/favicon-512.png",
  "/apple-touch-icon-180.png",
  "/brand/t-tile.png",
  "/brand/tradingportal-logo.png",
  "/brand/replayjournal-logo.png",
  "/brand/newsroom-logo.png",
];

/** GET API routes kept for offline. /api/news/events only when the query's from and to are today (UK). */
const API_ALLOW = new Set([
  "/api/hub",
  "/api/news/today",
  "/api/news/next",
  "/api/news/events",
  "/api/prices/quotes",
  "/api/prices/pins",
  "/api/calendar/occurrences",
  "/api/journal/summary",
  "/api/auth/me",
]);

function ukToday() {
  // en-CA gives YYYY-MM-DD; the UK zone matches the app's ukISODate().
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function cacheableApi(url) {
  if (!API_ALLOW.has(url.pathname)) return false;
  if (url.pathname === "/api/news/events") {
    const today = ukToday();
    return url.searchParams.get("from") === today && url.searchParams.get("to") === today;
  }
  return true;
}

// ---- install / activate ----

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // index.html is served no-cache; `reload` makes sure the precache never holds a stale copy.
      const index = await fetch("/index.html", { cache: "reload" }).catch(() => null);
      if (index && index.ok) {
        const html = await index.clone().text();
        await cache.put("/index.html", index.clone());
        await cache.put("/", index);
        // The entry chunks referenced by index.html, so a first visit that goes offline still opens.
        const assets = [...new Set(html.match(/\/assets\/[^"'\s)]+/g) || [])];
        await Promise.all(assets.map((a) => cache.add(a).catch(() => {})));
      }
      await Promise.all(SHELL_URLS.filter((u) => u !== "/" && u !== "/index.html").map((u) => cache.add(u).catch(() => {})));
    })(),
  );
  // The new worker waits until the page asks (skip-waiting message) so a running page keeps its chunks.
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith("tp-") && n !== SHELL_CACHE && n !== API_CACHE).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "skip-waiting") self.skipWaiting();
  if (data.type === "signed-out") event.waitUntil(caches.delete(API_CACHE));
});

// ---- fetch ----

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Any change of who is signed in empties the API cache, so one person's Hub is never served to the next:
  // sign-out, and every sign-in (password, passkey or invite) on this device.
  if (req.method === "POST" && AUTH_CHANGE.has(url.pathname)) {
    event.waitUntil(caches.delete(API_CACHE));
    return; // the request itself goes to the network untouched
  }
  if (req.method !== "GET") return;

  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(cacheFirst(req));
    return;
  }
  if (req.mode === "navigate") {
    event.respondWith(navigation(req));
    return;
  }
  if (url.pathname.startsWith("/api/")) {
    if (cacheableApi(url)) event.respondWith(apiNetworkFirst(event, req));
    return; // every other API route: network only
  }
  if (SHELL_URLS.includes(url.pathname)) {
    event.respondWith(shellStaleWhileRevalidate(req));
  }
});

async function cacheFirst(req) {
  const cache = await caches.open(SHELL_CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) await cache.put(req, res.clone());
  return res;
}

/** Shell files (icons, brand marks, manifest): serve the cached copy, refresh it in the background. */
async function shellStaleWhileRevalidate(req) {
  const cache = await caches.open(SHELL_CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  const refresh = fetch(req)
    .then((res) => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    })
    .catch(() => null);
  if (hit) return hit;
  const res = await refresh;
  return res || Response.error();
}

/** Navigations: network first so a deploy shows at once; the cached index.html when there's no network. */
async function navigation(req) {
  const url = new URL(req.url);
  try {
    const res = await fetch(req);
    // Only the SPA shell is ever stored as /index.html: an HTML answer for a non-API path. A navigation to
    // /api/... (a JSON 404, an export download) must never become the app shell.
    const isHtml = (res.headers.get("Content-Type") || "").includes("text/html");
    if (res.ok && isHtml && !url.pathname.startsWith("/api/")) {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put("/index.html", res.clone());
    }
    return res;
  } catch {
    const cache = await caches.open(SHELL_CACHE);
    const hit = (await cache.match("/index.html")) || (await cache.match("/"));
    return hit || new Response("You're offline and this screen isn't cached yet.", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}

/** Allow-listed API GETs: network (4 s), then the cache. A slow network still refreshes the cache afterwards. */
async function apiNetworkFirst(event, req) {
  const cache = await caches.open(API_CACHE);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const networkReq = new Request(req, { signal: controller.signal });
  const network = fetch(networkReq).then(async (res) => {
    if (res.ok) await storeApi(cache, req, res.clone());
    // The session ended or changed: nothing cached for the old session may be served again.
    else if (res.status === 401 || res.status === 403) await caches.delete(API_CACHE);
    return res;
  });
  try {
    const res = await network;
    clearTimeout(timer);
    return res;
  } catch {
    clearTimeout(timer);
    const hit = await cache.match(req);
    if (hit) return hit;
    throw new TypeError("offline and not cached");
  }
}

async function storeApi(cache, req, res) {
  const headers = new Headers(res.headers);
  headers.set(CACHED_AT, new Date().toISOString());
  const body = await res.arrayBuffer();
  await cache.put(req, new Response(body, { status: res.status, statusText: res.statusText, headers }));
  await trimApi(cache);
}

/** Keep the API cache small: the oldest entries go first (calendar ranges can otherwise pile up). */
async function trimApi(cache) {
  const keys = await cache.keys();
  if (keys.length <= API_MAX_ENTRIES) return;
  const stamped = await Promise.all(
    keys.map(async (k) => {
      const r = await cache.match(k);
      return { k, at: r ? Date.parse(r.headers.get(CACHED_AT) || "") || 0 : 0 };
    }),
  );
  stamped.sort((a, b) => a.at - b.at);
  await Promise.all(stamped.slice(0, keys.length - API_MAX_ENTRIES).map(({ k }) => cache.delete(k)));
}

// ---- push (unchanged) ----

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Trading Portal";
  const url = typeof data.url === "string" && data.url.startsWith("/") ? data.url : "/";

  const tasks = [
    self.registration.showNotification(title, {
      body: data.body || "",
      tag: data.tag || undefined,
      data: { url },
      icon: "/favicon-192.png",
      badge: "/favicon-192.png",
      renotify: false,
    }),
  ];

  // Service workers can't play audio: ask a visible page to play the optional soft chime.
  if (data.chime === true) {
    tasks.push(
      self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
        for (const client of clients) client.postMessage({ type: "chime", event_id: data.event_id ?? null });
      }),
    );
  }

  event.waitUntil(Promise.all(tasks));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = (event.notification.data && event.notification.data.url) || "/";
  const target = new URL(path, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async (clients) => {
      const sameOrigin = clients.filter((c) => new URL(c.url).origin === self.location.origin);
      const client = sameOrigin.find((c) => c.focused) || sameOrigin[0];
      if (client) {
        try {
          const focused = await client.focus();
          const navigated = await focused.navigate(target);
          if (navigated) return navigated;
        } catch {
          /* an uncontrolled client can't be navigated: open a window instead */
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
