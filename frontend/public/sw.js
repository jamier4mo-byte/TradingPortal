/* Trading Portal service worker: Web Push notifications only (F7).
 * No fetch handler and no caching: offline mode comes in Prompt 5.
 * Payload from the server: { title, body, url, tag, event_id, chime }. */

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

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
