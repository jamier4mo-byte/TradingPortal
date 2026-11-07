import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BellRing, Send, Share, Smartphone, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { ConfirmDialog, EmptyState, ErrorState, OfflineState, SkeletonText, useToast } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { api } from "../../lib/api.ts";
import { relativeTime } from "../../lib/format.ts";
import { CURRENCIES } from "../../lib/news.ts";
import { alertConfig, currentSubscription, disablePush, enablePush, playChime, pushSupport } from "../../lib/push.ts";
import { Switch, ToggleChip } from "../../components/ui/Toggles.tsx";

interface AlertPrefs {
  enabled: boolean;
  minutes_before: number;
  currencies: string[] | null;
  effective_currencies: string[];
  impacts: string[];
  quiet_start: string | null;
  quiet_end: string | null;
  chime: boolean;
}
interface Device {
  id: number;
  device_label: string;
  created_at: string;
  last_success_at: string | null;
  last_error: string | null;
  endpoint_hash: string;
}

const MINUTES = [5, 10, 15, 30, 60];
const IMPACTS = [
  { value: "high", label: "High", dot: "bg-impact-high" },
  { value: "medium", label: "Med", dot: "bg-impact-medium" },
  { value: "low", label: "Low", dot: "bg-impact-low" },
];

async function endpointHash(endpoint: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

function deviceName(): string {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "iPad";
  if (/Android/.test(ua)) return "Android phone";
  if (/Mac/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows PC";
  return "This device";
}

/** Settings → Alerts (3.5, F7): Web Push before high-impact events. Permission is asked only after a
 * button press. iPhone and iPad need the portal on the Home Screen first (iOS 16.4+). */
export default function AlertsSettings() {
  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/settings" className="btn btn-ghost -ml-3">
          <ArrowLeft aria-hidden className="size-4" />
          Settings
        </Link>
      </div>
      <header>
        <h1 className="text-heading font-semibold">News alerts</h1>
        <p className="mt-1 max-w-2xl text-body text-muted">A notification on your phone or computer before high-impact news for the instruments you follow.</p>
      </header>
      <div className="grid grid-cols-1 gap-4 laptop:grid-cols-12 laptop:gap-6">
        <div className="flex flex-col gap-4 laptop:col-span-6 laptop:gap-6">
          <ThisDevice />
          <Devices />
        </div>
        <div className="laptop:col-span-6">
          <PrefsCard />
        </div>
      </div>
    </div>
  );
}

function useDevices() {
  return useQuery({ queryKey: ["alerts", "devices"], queryFn: () => api.get<Device[]>("/api/alerts/devices") });
}

function ThisDevice() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const config = useQuery({ queryKey: ["alerts", "config"], queryFn: alertConfig });
  const devices = useDevices();
  const support = pushSupport();
  const [hash, setHash] = useState<string | null | undefined>(undefined);
  const [permission, setPermission] = useState(support.permission);

  useEffect(() => {
    let alive = true;
    void currentSubscription()
      .then((s) => (s ? endpointHash(s.endpoint) : null))
      .then((h) => alive && setHash(h))
      .catch(() => alive && setHash(null));
    return () => {
      alive = false;
    };
  }, [devices.data]);

  const mine = devices.data?.find((d) => d.endpoint_hash === hash) ?? null;
  const refresh = () => void qc.invalidateQueries({ queryKey: ["alerts"] });

  const enable = useMutation({
    mutationFn: () => enablePush(deviceName()),
    onSuccess: () => {
      setPermission("granted");
      refresh();
      toast({ title: "Alerts are on for this device" });
    },
    onError: (err) => {
      setPermission(pushSupport().permission);
      toast({ title: "Couldn't turn alerts on", text: err.message, tone: "loss" });
    },
  });
  const disable = useMutation({
    mutationFn: () => disablePush(mine?.id),
    onSuccess: () => {
      refresh();
      toast({ title: "Alerts are off for this device" });
    },
  });
  const test = useMutation({
    mutationFn: (id?: number) => api.post<{ sent: number; failed: number; pruned: number }>("/api/alerts/test", id ? { subscription_id: id } : {}),
    onSuccess: (r) => {
      refresh();
      toast(
        r.sent
          ? { title: "Test notification sent", text: "It should arrive in a few seconds." }
          : { title: "Nothing was delivered", text: r.pruned ? "That device's subscription had expired and was removed." : "The push service refused it.", tone: "loss" },
      );
    },
    onError: (err) => toast({ title: "Couldn't send a test", text: err.message, tone: "loss" }),
  });

  let body;
  if (offlinePending(config)) {
    body = <OfflineState what="Alert setup" />;
  } else if (config.isPending || hash === undefined) {
    body = <SkeletonText lines={3} />;
  } else if (config.isError) {
    body = <ErrorState text={config.error.message} onRetry={() => config.refetch()} />;
  } else if (support.needsInstall) {
    body = (
      <div className="flex flex-col gap-3 text-body">
        <p className="font-medium">Add to Home Screen to get alerts</p>
        <p className="text-muted">On iPhone and iPad, notifications only work for apps on your Home Screen (iOS 16.4 or later).</p>
        <ol className="flex flex-col gap-2">
          <li className="flex items-start gap-3">
            <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-label">1</span>
            <span>
              Tap <Share aria-label="Share" className="inline size-4 align-text-bottom" /> Share in Safari&rsquo;s toolbar.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-label">2</span>
            <span>Choose &ldquo;Add to Home Screen&rdquo;, then Add.</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-label">3</span>
            <span>Open Trading Portal from the Home Screen and come back to Settings → Alerts.</span>
          </li>
        </ol>
      </div>
    );
  } else if (!support.supported) {
    body = <p className="text-body text-muted">This browser can&rsquo;t receive notifications. Try Chrome, Edge, Firefox or Safari 16.4+.</p>;
  } else if (!config.data.push_configured) {
    body = (
      <p className="text-body text-muted">
        Push isn&rsquo;t set up on the server yet. The admin runs <code className="font-mono">make vapid</code> (or sets the VAPID secrets) and restarts the portal.
      </p>
    );
  } else if (permission === "denied") {
    body = (
      <p className="text-body text-muted">
        Notifications are blocked for this site. Allow them in your browser&rsquo;s site settings (or Settings → Notifications on your phone), then reload this page.
      </p>
    );
  } else if (mine) {
    body = (
      <div className="flex flex-col gap-3">
        <p className="flex items-center gap-2 text-body">
          <span aria-hidden className="size-2 rounded-full bg-live" />
          Alerts are on for this {mine.device_label}.
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary" onClick={() => test.mutate(mine.id)} disabled={test.isPending}>
            <Send aria-hidden className="size-4" />
            Send test notification
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => disable.mutate()} disabled={disable.isPending}>
            Turn off on this device
          </button>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="flex flex-col gap-3">
        <p className="text-body text-muted">Your browser will ask for permission after you press the button.</p>
        <div>
          <button type="button" className="btn btn-primary" onClick={() => enable.mutate()} disabled={enable.isPending}>
            <BellRing aria-hidden className="size-4" />
            {enable.isPending ? "Turning on…" : "Turn on alerts on this device"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <Card title="This device" subtitle="Web Push to this browser or installed app">
      {body}
    </Card>
  );
}

function Devices() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const devices = useDevices();
  const [removing, setRemoving] = useState<Device | null>(null);
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/alerts/subscriptions/${id}`),
    onSuccess: () => {
      setRemoving(null);
      void qc.invalidateQueries({ queryKey: ["alerts"] });
      toast({ title: "Device removed" });
    },
  });
  return (
    <Card title="Your devices" subtitle="Each gets its own notification">
      {offlinePending(devices) ? (
        <OfflineState what="The device list" />
      ) : devices.isPending ? (
        <SkeletonText lines={2} />
      ) : devices.isError ? (
        <ErrorState text={devices.error.message} onRetry={() => devices.refetch()} />
      ) : devices.data.length === 0 ? (
        <EmptyState title="No devices yet" text="Turn alerts on above, on each phone or computer you want them on." />
      ) : (
        <ul className="divide-y divide-border">
          {devices.data.map((d) => (
            <li key={d.id} className="flex min-h-11 items-center gap-3 py-2">
              <Smartphone aria-hidden className="size-4 text-muted" />
              <div className="min-w-0 flex-1">
                <p className="text-body">{d.device_label}</p>
                <p className="num text-label text-muted">
                  Added {relativeTime(d.created_at)}
                  {d.last_success_at ? ` · last alert ${relativeTime(d.last_success_at)}` : ""}
                  {d.last_error ? ` · last attempt failed` : ""}
                </p>
              </div>
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Remove ${d.device_label}`} onClick={() => setRemoving(d)}>
                <Trash2 aria-hidden className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove ${removing?.device_label ?? "device"}?`}
        text="It stops getting news alerts. You can turn them on again from that device."
        confirmLabel="Remove device"
        danger
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
      />
    </Card>
  );
}

function PrefsCard() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const prefs = useQuery({ queryKey: ["alerts", "prefs"], queryFn: () => api.get<AlertPrefs>("/api/alerts/prefs") });
  const save = useMutation({
    mutationFn: (body: Partial<AlertPrefs>) => api.put<AlertPrefs>("/api/alerts/prefs", body),
    onSuccess: (p) => qc.setQueryData(["alerts", "prefs"], p),
    onError: (err) => toast({ title: "Couldn't save", text: err.message, tone: "loss" }),
  });
  const [quiet, setQuiet] = useState<{ start: string; end: string } | null>(null);

  if (offlinePending(prefs)) return <Card title="What to alert"><OfflineState what="Alert preferences" /></Card>;
  if (prefs.isPending) return <Card title="What to alert"><SkeletonText lines={6} /></Card>;
  if (prefs.isError) return <Card title="What to alert"><ErrorState text={prefs.error.message} onRetry={() => prefs.refetch()} /></Card>;
  const p = prefs.data;
  const quietOn = p.quiet_start !== null && p.quiet_end !== null;
  const q = quiet ?? { start: p.quiet_start ?? "22:00", end: p.quiet_end ?? "07:00" };
  const toggle = (list: string[], item: string) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  return (
    <Card title="What to alert" subtitle="Saved as you change it">
      <div className="flex flex-col gap-5">
        <Switch checked={p.enabled} onChange={(enabled) => save.mutate({ enabled })} label="News alerts" description={p.enabled ? "On for every device you've added" : "Off: no notifications are sent"} />

        <fieldset disabled={!p.enabled} className="flex flex-col gap-5 disabled:opacity-80">
          <label className="flex flex-col gap-1.5">
            <span className="text-label text-muted">How long before</span>
            <select className="input num w-40" value={p.minutes_before} onChange={(e) => save.mutate({ minutes_before: Number(e.target.value) })}>
              {MINUTES.map((m) => (
                <option key={m} value={m}>
                  {m} minutes
                </option>
              ))}
            </select>
          </label>

          <fieldset>
            <legend className="mb-2 text-label text-muted">Impact</legend>
            <div className="flex flex-wrap gap-2">
              {IMPACTS.map((i) => (
                <ToggleChip
                  key={i.value}
                  pressed={p.impacts.includes(i.value)}
                  onClick={() => {
                    const next = toggle(p.impacts, i.value);
                    if (next.length) save.mutate({ impacts: next });
                    else toast({ title: "Keep at least one impact level", text: "Turn alerts off above to stop them entirely." });
                  }}
                >
                  <span aria-hidden className={`size-2 rounded-full ${i.dot}`} />
                  {i.label}
                </ToggleChip>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="sr-only">Currencies</legend>
            <Switch
              checked={p.currencies === null}
              onChange={(mineOnly) => save.mutate({ currencies: mineOnly ? null : p.effective_currencies })}
              label="Currencies of my instruments"
              description={`Now: ${p.effective_currencies.filter((c) => /^[A-Z]{3}$/.test(c)).join(", ") || "none"}`}
            />
            {p.currencies !== null ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {CURRENCIES.map((c) => (
                  <ToggleChip key={c} pressed={p.currencies!.includes(c)} onClick={() => save.mutate({ currencies: toggle(p.currencies!, c) })}>
                    <span className="font-mono">{c}</span>
                  </ToggleChip>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-label text-muted">
                Change the instruments you follow in <Link to="/settings#news" className="inline-flex min-h-11 items-center underline underline-offset-4">Settings → News Room</Link>.
              </p>
            )}
          </fieldset>

          <div>
            <Switch
              checked={quietOn}
              onChange={(on) => save.mutate(on ? { quiet_start: q.start, quiet_end: q.end } : { quiet_start: null, quiet_end: null })}
              label="Quiet hours"
              description="No alerts between these UK times"
            />
            {quietOn ? (
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-label text-muted">From</span>
                  <input type="time" className="input num w-32" value={q.start} onChange={(e) => setQuiet({ ...q, start: e.target.value })} onBlur={() => save.mutate({ quiet_start: q.start, quiet_end: q.end })} />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-label text-muted">Until</span>
                  <input type="time" className="input num w-32" value={q.end} onChange={(e) => setQuiet({ ...q, end: e.target.value })} onBlur={() => save.mutate({ quiet_start: q.start, quiet_end: q.end })} />
                </label>
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Switch checked={p.chime} onChange={(chime) => save.mutate({ chime })} label="Soft chime" description="Plays when an alert arrives while the portal is open" />
            <button type="button" className="btn btn-ghost" onClick={() => playChime()}>
              Play sample
            </button>
          </div>
        </fieldset>
      </div>
    </Card>
  );
}
