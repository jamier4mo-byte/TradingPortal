import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.tsx";
import { ToastProvider } from "./components/ui/index.ts";
import { AuthProvider } from "./lib/auth.tsx";
import { announceUpdate } from "./lib/offline.ts";
import { registerServiceWorker } from "./lib/push.ts";

/** Register /sw.js (push + offline cache) and watch for a new version. The new worker waits until the
 * shell's "Reload" asks it to take over (skip-waiting), then the page reloads on controllerchange so a
 * running page never loses the chunks it was built with. */
window.addEventListener("load", () => {
  void registerServiceWorker().then((reg) => {
    if (!reg) return;
    const watch = (worker: ServiceWorker | null) => {
      if (!worker) return;
      worker.addEventListener("statechange", () => {
        // "installed" with a controller already in place means an update, not the first install.
        if (worker.state === "installed" && navigator.serviceWorker.controller) announceUpdate(worker);
      });
    };
    if (reg.waiting && navigator.serviceWorker.controller) announceUpdate(reg.waiting);
    watch(reg.installing);
    reg.addEventListener("updatefound", () => watch(reg.installing));
  });
  // A first install claims the page too (clients.claim) and must not reload it: only a change of controller counts.
  const hadController = !!navigator.serviceWorker?.controller;
  let reloading = false;
  navigator.serviceWorker?.addEventListener("controllerchange", () => {
    if (!hadController || reloading) return;
    reloading = true;
    window.location.reload();
  });
});

const queryClient = new QueryClient({
  defaultOptions: {
    // offlineFirst: fire the request even when the browser says it's offline so the service worker can answer
    // from its cache; if that fails, retries pause until we're back online (the cards read that as "offline").
    queries: { retry: 1, refetchOnWindowFocus: false, networkMode: "offlineFirst" },
    // Writes fail fast offline (api.ts turns the failure into "You're offline: changes will need a connection").
    mutations: { networkMode: "offlineFirst" },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
