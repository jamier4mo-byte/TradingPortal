/** Web Push for news alerts (F7). No UI here: the alert settings screens call these.
 *
 * iOS/iPadOS 16.4+ only delivers Web Push to a portal installed to the home screen, so `pushSupport()`
 * reports `needsInstall` there. Permission is asked only from `enablePush()`, which must run from a
 * button press (browsers block or penalise permission prompts that aren't a user gesture). */

import { api } from "./api.ts";

const SW_URL = "/sw.js";

export interface AlertConfig {
  push_configured: boolean;
  vapid_public_key: string | null;
}

export interface PushSupport {
  /** Service workers, PushManager and notifications are all available in this browser. */
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  isIOS: boolean;
  isStandalone: boolean;
  /** iPhone/iPad in a browser tab: add the portal to the home screen first. */
  needsInstall: boolean;
}

function hasPushApis(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function detectIOS(): boolean {
  const ua = navigator.userAgent;
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  // iPadOS 13+ reports a desktop Mac user agent; touch support gives it away.
  return /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
}

function detectStandalone(): boolean {
  const nav = navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches === true;
}

export function pushSupport(): PushSupport {
  const isIOS = typeof navigator !== "undefined" && detectIOS();
  const isStandalone = typeof window !== "undefined" && detectStandalone();
  const supported = hasPushApis();
  return {
    supported,
    permission: "Notification" in globalThis ? Notification.permission : "unsupported",
    isIOS,
    isStandalone,
    needsInstall: isIOS && !isStandalone,
  };
}

let registration: Promise<ServiceWorkerRegistration | null> | null = null;

/** Register /sw.js once (idempotent). Resolves to null where service workers aren't available. */
export function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (registration) return registration;
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    registration = Promise.resolve(null);
    return registration;
  }
  registration = navigator.serviceWorker.register(SW_URL, { scope: "/" }).catch((err: unknown) => {
    console.warn("Service worker registration failed", err);
    registration = null; // let a later call try again
    return null;
  });
  return registration;
}

async function readyRegistration(): Promise<ServiceWorkerRegistration> {
  const reg = await registerServiceWorker();
  if (!reg) throw new Error("This browser can't receive notifications.");
  return navigator.serviceWorker.ready;
}

/** Base64url (VAPID public key) → bytes for `applicationServerKey`. */
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export function alertConfig(): Promise<AlertConfig> {
  return api.get<AlertConfig>("/api/alerts/config");
}

/** The browser's current push subscription for this portal, if any. */
export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!hasPushApis()) return null;
  const reg = await registerServiceWorker();
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

/** Ask for permission, subscribe this device and register it with the server. Returns the device id.
 * Call it straight from a button's click handler. Throws an Error with a readable message on failure. */
export async function enablePush(deviceLabel: string): Promise<number> {
  const support = pushSupport();
  if (support.needsInstall) {
    throw new Error("On iPhone and iPad, add the portal to your Home Screen first, then turn on alerts there.");
  }
  if (!support.supported) throw new Error("This browser can't receive notifications.");

  // Ask first, while we're still inside the click's user activation.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      permission === "denied"
        ? "Notifications are blocked for this site. Allow them in your browser or phone settings."
        : "Notifications weren't allowed.",
    );
  }

  const config = await alertConfig();
  if (!config.push_configured || !config.vapid_public_key) {
    throw new Error("Push isn't set up on the server yet (VAPID keys missing).");
  }
  const reg = await readyRegistration();
  const key = urlBase64ToUint8Array(config.vapid_public_key);

  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, key)) {
    await sub.unsubscribe(); // the server's VAPID key changed: the old subscription can't be used
    sub = null;
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });

  const json = sub.toJSON();
  const res = await api.post<{ id: number }>("/api/alerts/subscriptions", {
    endpoint: sub.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
    device_label: deviceLabel.trim().slice(0, 80) || "This device",
  });
  return res.id;
}

function sameKey(sub: PushSubscription, key: Uint8Array): boolean {
  const current = sub.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === key.length && bytes.every((b, i) => b === key[i]);
}

/** Unsubscribe this browser and remove the device on the server (by id when known). */
export async function disablePush(subscriptionId?: number): Promise<void> {
  const sub = await currentSubscription();
  if (sub) await sub.unsubscribe();
  if (subscriptionId != null) {
    await api.delete<{ ok: boolean }>(`/api/alerts/subscriptions/${subscriptionId}`);
  }
}

/** Listen for the service worker's `{ type: "chime" }` message. Returns an unsubscribe function. */
export function onChimeMessage(handler: (eventId: number | null) => void): () => void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return () => {};
  const listener = (event: MessageEvent) => {
    const data = event.data as { type?: string; event_id?: number | null } | null;
    if (data?.type === "chime") handler(data.event_id ?? null);
  };
  navigator.serviceWorker.addEventListener("message", listener);
  return () => navigator.serviceWorker.removeEventListener("message", listener);
}

let audioContext: AudioContext | null = null;

/** A soft ~0.4 s two-tone chime (Web Audio, no files). Browsers only allow sound after the user has
 * interacted with the page, so this may stay silent on a page nobody has touched yet. */
export function playChime(): void {
  const Ctor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return;
  audioContext ??= new Ctor();
  const ctx = audioContext;
  if (ctx.state === "suspended") void ctx.resume().catch(() => {});
  const start = ctx.currentTime + 0.01;
  const notes: [number, number][] = [
    [880, 0], // A5
    [1318.5, 0.16], // E6
  ];
  for (const [freq, offset] of notes) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    const t = start + offset;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.06, t + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.24);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.26);
  }
}
