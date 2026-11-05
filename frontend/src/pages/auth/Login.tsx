import { startAuthentication } from "@simplewebauthn/browser";
import { useQueryClient } from "@tanstack/react-query";
import { Fingerprint, Lock } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Field, TextInput } from "../../components/ui/index.ts";
import { api, ApiError, type User } from "../../lib/api.ts";
import { useAuth } from "../../lib/auth.tsx";
import { AuthFrame } from "./AuthFrame.tsx";

export default function Login() {
  const { user, loading } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const passkeysAvailable = typeof window !== "undefined" && "PublicKeyCredential" in window;

  if (!loading && user) return <Navigate to={from} replace />;

  const finish = (u: User) => {
    qc.setQueryData(["me"], u);
    navigate(from, { replace: true });
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      finish(await api.post<User>("/api/auth/login", { email, password }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) setLocked(err.message);
      else setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const onPasskey = async () => {
    setBusy(true);
    setError(null);
    try {
      const begin = await api.post<{ challenge_key: string; options: Record<string, unknown> }>("/api/auth/passkey/login/begin");
      const credential = await startAuthentication({ optionsJSON: begin.options as never });
      finish(await api.post<User>("/api/auth/passkey/login/finish", { challenge_key: begin.challenge_key, credential }));
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") setError("Passkey sign-in was cancelled.");
      else setError(err instanceof Error ? err.message : "Passkey sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  if (locked) {
    return (
      <AuthFrame title="Locked for now" intro={locked}>
        <div className="rounded-panel border border-border bg-surface-1 p-4 text-body text-muted">
          <p className="flex items-center gap-2 text-text">
            <Lock aria-hidden className="size-4" />
            Five wrong passwords in a row lock the account for 15 minutes.
          </p>
          <p className="mt-2">If you&rsquo;ve forgotten your password, ask Jamie for a reset link.</p>
        </div>
        <button type="button" className="btn btn-secondary mt-6 w-full" onClick={() => setLocked(null)}>
          Back to sign in
        </button>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Sign in"
      intro="Accounts are by invite. Ask Jamie for a link if you don't have one yet."
      aside={<p>Forgotten your password? The admin can send you a one-hour reset link from Users.</p>}
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="Email">
          {(p) => (
            <TextInput
              {...p}
              type="email"
              name="email"
              autoComplete="username webauthn"
              inputMode="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
        <Field label="Password" error={error}>
          {(p) => (
            <TextInput
              {...p}
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <button type="submit" className="btn btn-primary mt-2 w-full" disabled={busy}>
          Sign in
        </button>
        {passkeysAvailable ? (
          <button type="button" className="btn btn-secondary w-full" onClick={onPasskey} disabled={busy}>
            <Fingerprint aria-hidden className="size-4" />
            Use a passkey
          </button>
        ) : null}
      </form>
    </AuthFrame>
  );
}
