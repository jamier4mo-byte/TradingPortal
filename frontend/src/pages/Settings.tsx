import { startRegistration } from "@simplewebauthn/browser";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fingerprint, KeyRound, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import Card from "../components/Card.tsx";
import { KeyEmpty } from "../components/ui/Illustrations.tsx";
import { ConfirmDialog, EmptyState, ErrorState, Field, PillToggle, SkeletonText, TextInput, useToast } from "../components/ui/index.ts";
import { api, type ApiKey, type MotionPref, type Passkey, type User } from "../lib/api.ts";
import { useAuth } from "../lib/auth.tsx";
import { relativeTime, shortDateTime } from "../lib/format.ts";
import { useSaveMarketSettings, useUsage } from "../lib/markets.ts";
import { useNewsPrefs, useSaveNewsPrefs } from "../lib/news.ts";
import { CreditsMeter } from "../components/market/CreditsMeter.tsx";
import { Switch, ToggleChip } from "../components/ui/Toggles.tsx";
import { Link } from "react-router-dom";

const MOTION_OPTIONS = [
  { value: "full" as const, label: "Full" },
  { value: "reduced" as const, label: "Reduced" },
  { value: "off" as const, label: "Off" },
];

export default function Settings() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6">
      <div className="col-span-full flex flex-col gap-4 laptop:col-span-7 laptop:gap-6">
        <ProfileCard user={user} />
        <PasswordCard />
        <PasskeysCard />
        <NewsPrefsCard />
      </div>
      <div className="col-span-full flex flex-col gap-4 laptop:col-span-5 laptop:gap-6">
        <MotionCard user={user} />
        <BreakevenCard user={user} />
        <ApiKeysCard />
        <LivePricesCard />
      </div>
    </div>
  );
}

function useProfileMutation() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (body: Partial<Pick<User, "display_name" | "motion_pref" | "breakeven_threshold">>) => api.patch<User>("/api/me", body),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      toast({ title: "Saved" });
    },
    onError: (err) => toast({ title: "Couldn't save", text: err.message, tone: "loss" }),
  });
}

function ProfileCard({ user }: { user: User }) {
  const [name, setName] = useState(user.display_name);
  const save = useProfileMutation();
  return (
    <Card title="Profile" subtitle={user.email}>
      <form
        className="flex flex-col gap-4 tablet:flex-row tablet:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (name.trim() && name !== user.display_name) save.mutate({ display_name: name.trim() });
        }}
      >
        <div className="flex-1">
          <Field label="Display name" help="Shown on your strategies, trades and tasks.">
            {(p) => <TextInput {...p} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />}
          </Field>
        </div>
        <button type="submit" className="btn btn-primary" disabled={save.isPending || name.trim() === user.display_name}>
          Save name
        </button>
      </form>
      <p className="mt-4 text-label text-muted">
        Role: <span className="text-text">{user.role}</span>. Roles are changed by the admin.
      </p>
    </Card>
  );
}

function PasswordCard() {
  const { toast } = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: () => api.post<{ message: string }>("/api/me/password", { current_password: current, new_password: next }),
    onSuccess: (r) => {
      toast({ title: "Password changed", text: r.message });
      setCurrent("");
      setNext("");
      setError(null);
    },
    onError: (err) => setError(err.message),
  });
  return (
    <Card title="Password" subtitle="Changing it signs out your other devices">
      <form
        className="grid gap-4 tablet:grid-cols-2"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <Field label="Current password">
          {(p) => <TextInput {...p} type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />}
        </Field>
        <Field label="New password" help="At least 10 characters." error={error}>
          {(p) => <TextInput {...p} type="password" autoComplete="new-password" required minLength={10} value={next} onChange={(e) => setNext(e.target.value)} />}
        </Field>
        <div className="tablet:col-span-2">
          <button type="submit" className="btn btn-secondary" disabled={change.isPending || !current || !next}>
            Change password
          </button>
        </div>
      </form>
    </Card>
  );
}

function PasskeysCard() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [removing, setRemoving] = useState<Passkey | null>(null);
  const passkeys = useQuery({ queryKey: ["passkeys"], queryFn: () => api.get<Passkey[]>("/api/me/passkeys") });
  const supported = typeof window !== "undefined" && "PublicKeyCredential" in window;

  const add = useMutation({
    mutationFn: async () => {
      const begin = await api.post<{ challenge_key: string; options: Record<string, unknown> }>("/api/me/passkeys/begin");
      const credential = await startRegistration({ optionsJSON: begin.options as never });
      const name = /iPhone|iPad/.test(navigator.userAgent) ? "iPhone" : /Mac/.test(navigator.userAgent) ? "Mac" : "This device";
      return api.post<Passkey>("/api/me/passkeys/finish", { challenge_key: begin.challenge_key, credential, name });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["passkeys"] });
      toast({ title: "Passkey added" });
    },
    onError: (err) => {
      if (err instanceof DOMException && err.name === "NotAllowedError") return;
      toast({ title: "Couldn't add the passkey", text: err.message, tone: "loss" });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/me/passkeys/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["passkeys"] });
      setRemoving(null);
      toast({ title: "Passkey removed" });
    },
  });

  return (
    <Card
      title="Passkeys"
      subtitle="Sign in with Face ID, Touch ID or a security key"
      controls={
        supported ? (
          <button type="button" className="btn btn-secondary" onClick={() => add.mutate()} disabled={add.isPending}>
            <Fingerprint aria-hidden className="size-4" />
            Add passkey
          </button>
        ) : null
      }
    >
      {passkeys.isPending ? (
        <SkeletonText lines={2} />
      ) : passkeys.isError ? (
        <ErrorState text={passkeys.error.message} onRetry={() => passkeys.refetch()} />
      ) : passkeys.data.length === 0 ? (
        <EmptyState
          title="No passkeys yet"
          text={supported ? "Add one to skip typing your password on this device." : "This browser doesn't support passkeys."}
        />
      ) : (
        <ul className="divide-y divide-border">
          {passkeys.data.map((p) => (
            <li key={p.id} className="flex min-h-11 items-center gap-3 py-2">
              <Fingerprint aria-hidden className="size-4 text-muted" />
              <div className="min-w-0 flex-1">
                <p className="text-body">{p.name}</p>
                <p className="num text-label text-muted">
                  Added {shortDateTime(p.created_at)} · last used {relativeTime(p.last_used_at)}
                  {p.backed_up ? " · synced" : ""}
                </p>
              </div>
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Remove ${p.name}`} onClick={() => setRemoving(p)}>
                <Trash2 aria-hidden className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove ${removing?.name ?? "passkey"}?`}
        text="You'll need your password to sign in from that device."
        confirmLabel="Remove passkey"
        danger
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
      />
    </Card>
  );
}

function MotionCard({ user }: { user: User }) {
  const save = useProfileMutation();
  return (
    <Card title="Motion" subtitle="Also follows your device's reduced-motion setting">
      <PillToggle<MotionPref> value={user.motion_pref} onChange={(v) => save.mutate({ motion_pref: v })} options={MOTION_OPTIONS} label="Motion" />
      <p className="mt-3 text-label text-muted">Reduced turns movement into simple fades. Off stops animation entirely.</p>
    </Card>
  );
}

function BreakevenCard({ user }: { user: User }) {
  const save = useProfileMutation();
  const [value, setValue] = useState(String(user.breakeven_threshold));
  const n = Number(value);
  const changed = !Number.isNaN(n) && n !== user.breakeven_threshold;
  return (
    <Card title="Breakeven threshold" subtitle="Trades this close to zero count as breakeven">
      <form
        className="flex items-end gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (changed) save.mutate({ breakeven_threshold: n });
        }}
      >
        <div className="w-32">
          <Field label="± amount ($)">
            {(p) => <TextInput {...p} className="num" type="number" inputMode="decimal" step="0.5" min={0} max={100} value={value} onChange={(e) => setValue(e.target.value)} />}
          </Field>
        </div>
        <button type="submit" className="btn btn-secondary" disabled={!changed || save.isPending}>
          Save
        </button>
      </form>
      <p className="mt-3 text-label text-muted">Default 10. A trade within ± this many dollars of zero is a breakeven, in every stat in the Replay Journal.</p>
    </Card>
  );
}

function ApiKeysCard() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [draft, setDraft] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const keys = useQuery({ queryKey: ["keys"], queryFn: () => api.get<ApiKey[]>("/api/me/keys") });
  const twelve = keys.data?.find((k) => k.provider === "twelve_data");

  const save = useMutation({
    mutationFn: () => api.put<ApiKey>("/api/me/keys/twelve_data", { key: draft }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["keys"] });
      setDraft("");
      toast({ title: "Key saved", text: "Only the last 4 characters are ever shown again." });
    },
    onError: (err) => toast({ title: "Couldn't save the key", text: err.message, tone: "loss" }),
  });
  const test = useMutation({
    mutationFn: () => api.post<{ ok: boolean; message?: string }>("/api/me/keys/twelve_data/test"),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["keys"] });
      void qc.invalidateQueries({ queryKey: ["prices"] });
      toast(r.ok ? { title: "Key works", text: r.message } : { title: "Key failed the check", text: r.message, tone: "loss" });
    },
    onError: (err) => toast({ title: "Couldn't check the key", text: err.message, tone: "loss" }),
  });
  const del = useMutation({
    mutationFn: () => api.delete("/api/me/keys/twelve_data"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["keys"] });
      setConfirmDelete(false);
      toast({ title: "Key removed" });
    },
  });

  return (
    <Card id="keys" title="API keys" subtitle="Your own Twelve Data key, kept encrypted on the server">
      {keys.isPending ? (
        <SkeletonText lines={3} />
      ) : keys.isError ? (
        <ErrorState text={keys.error.message} onRetry={() => keys.refetch()} />
      ) : twelve ? (
        <div className="rounded-panel border border-border bg-surface-2 p-3">
          <div className="flex items-center gap-3">
            <KeyRound aria-hidden className="size-4 text-muted" />
            <div className="min-w-0 flex-1">
              <p className="text-body">
                Twelve Data <span className="num font-mono text-muted">····{twelve.last4}</span>
              </p>
              <p className="num text-label text-muted">
                {twelve.last_tested_at
                  ? `Checked ${relativeTime(twelve.last_tested_at)}: ${twelve.last_test_ok ? "working" : "failed"}`
                  : "Not checked yet"}
              </p>
            </div>
            <span aria-hidden className={`size-2 rounded-full ${twelve.last_test_ok ? "bg-live" : "bg-stale"}`} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="btn btn-secondary" onClick={() => test.mutate()} disabled={test.isPending}>
              Check key
            </button>
            <button type="button" className="btn btn-danger" onClick={() => setConfirmDelete(true)}>
              Remove
            </button>
          </div>
          <p className="mt-3 text-label text-muted">Check key makes one real Twelve Data request (1 credit). Your prices and searches use this key only.</p>
        </div>
      ) : (
        <EmptyState
          illustration={<KeyEmpty />}
          title="No Twelve Data key yet"
          text="Paste your free key (800 credits a day) and the portal will use it for your prices."
        />
      )}
      <form
        className="mt-4 flex flex-col gap-3 tablet:flex-row tablet:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (draft.trim().length >= 8) save.mutate();
        }}
      >
        <div className="flex-1">
          <Field label={twelve ? "Replace key" : "Twelve Data key"}>
            {(p) => <TextInput {...p} type="password" autoComplete="off" spellCheck={false} value={draft} onChange={(e) => setDraft(e.target.value)} />}
          </Field>
        </div>
        <button type="submit" className="btn btn-primary" disabled={draft.trim().length < 8 || save.isPending}>
          Save key
        </button>
      </form>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Remove your Twelve Data key?"
        text="Your prices stop until you add a key again."
        confirmLabel="Remove key"
        danger
        busy={del.isPending}
        onConfirm={() => del.mutate()}
      />
    </Card>
  );
}

function NewsPrefsCard() {
  const prefs = useNewsPrefs();
  const save = useSaveNewsPrefs();
  const { toast } = useToast();
  const [windowDraft, setWindowDraft] = useState<string | null>(null);
  const done = { onSuccess: () => toast({ title: "Saved", text: "Your trades' news tags are being updated." }), onError: (err: Error) => toast({ title: "Couldn't save", text: err.message, tone: "loss" as const }) };
  return (
    <Card id="news" title="News Room" subtitle="The instruments you follow and your news window">
      {prefs.isPending ? (
        <SkeletonText lines={4} />
      ) : prefs.isError ? (
        <ErrorState text={prefs.error.message} onRetry={() => prefs.refetch()} />
      ) : (
        <div className="flex flex-col gap-4">
          <fieldset>
            <legend className="mb-2 text-label text-muted">Instruments I follow</legend>
            <div className="flex flex-wrap gap-2">
              {prefs.data.available.map((i) => {
                const on = prefs.data.instruments.includes(i.code);
                return (
                  <ToggleChip
                    key={i.code}
                    pressed={on}
                    label={`${i.code}, ${i.name}`}
                    onClick={() => save.mutate({ instruments: on ? prefs.data.instruments.filter((c) => c !== i.code) : [...prefs.data.instruments, i.code] }, done)}
                  >
                    <span className="font-mono">{i.code}</span>
                  </ToggleChip>
                );
              })}
            </div>
            <p className="mt-2 text-label text-muted">Filters &ldquo;My instruments only&rdquo;, today&rsquo;s news and your alerts.</p>
          </fieldset>
          <form
            className="flex items-end gap-3"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              const n = Number(windowDraft);
              if (windowDraft !== null && Number.isInteger(n) && n !== prefs.data.news_window_minutes) save.mutate({ news_window_minutes: n }, done);
            }}
          >
            <div className="w-40">
              <Field label="News window (± minutes)">
                {(p) => (
                  <TextInput
                    {...p}
                    className="num"
                    type="number"
                    inputMode="numeric"
                    min={0}
                    max={120}
                    step={5}
                    value={windowDraft ?? String(prefs.data.news_window_minutes)}
                    onChange={(e) => setWindowDraft(e.target.value)}
                  />
                )}
              </Field>
            </div>
            <button type="submit" className="btn btn-secondary" disabled={save.isPending || windowDraft === null || Number(windowDraft) === prefs.data.news_window_minutes}>
              Save
            </button>
          </form>
          <p className="text-label text-muted">
            A trade entered within this many minutes of a high-impact event for its instrument counts as &ldquo;inside a news window&rdquo; in Analytics. Default 15.
          </p>
          <Link to="/settings/alerts" className="btn btn-secondary self-start">
            News alerts
          </Link>
        </div>
      )}
    </Card>
  );
}

function LivePricesCard() {
  const usage = useUsage();
  const save = useSaveMarketSettings();
  return (
    <Card title="Live prices" subtitle="How your Twelve Data credits are used">
      {usage.isPending ? (
        <SkeletonText lines={3} />
      ) : usage.isError ? (
        <ErrorState text={usage.error.message} onRetry={() => usage.refetch()} />
      ) : (
        <div className="flex flex-col gap-4">
          <CreditsMeter usage={usage.data} />
          <Switch
            checked={usage.data.allow_background_jobs}
            onChange={(v) => save.mutate({ allow_background_jobs: v })}
            label="Allow background jobs to use my key"
            description={`Works out price reactions after news, from leftover credits only (at most ${usage.data.background_cap} a day). Off by default.`}
          />
          <Link to="/markets" className="btn btn-secondary self-start">
            Open Markets
          </Link>
        </div>
      )}
    </Card>
  );
}
