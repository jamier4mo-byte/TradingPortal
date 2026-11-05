import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Field, TextInput } from "../../components/ui/index.ts";
import { api, ApiError, type User } from "../../lib/api.ts";
import { AuthFrame } from "./AuthFrame.tsx";

export default function ResetPassword() {
  const { token = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [gone, setGone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== again) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const u = await api.post<User>("/api/auth/reset", { token, password });
      qc.setQueryData(["me"], u);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) setGone(err.message);
      else setError(err instanceof Error ? err.message : "Couldn't set the password.");
    } finally {
      setBusy(false);
    }
  };

  if (gone) {
    return (
      <AuthFrame title="This reset link has expired" intro={gone}>
        <p className="text-body text-muted">Reset links last one hour and work once. Ask Jamie for a new one.</p>
        <Link to="/login" className="btn btn-secondary mt-6 w-full">
          Go to sign in
        </Link>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Choose a new password" intro="This signs you out everywhere else once it's saved.">
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="New password" help="At least 10 characters.">
          {(p) => (
            <TextInput {...p} type="password" autoComplete="new-password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} />
          )}
        </Field>
        <Field label="Again, to be sure" error={error}>
          {(p) => <TextInput {...p} type="password" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.target.value)} />}
        </Field>
        <button type="submit" className="btn btn-primary mt-2 w-full" disabled={busy}>
          Save password
        </button>
      </form>
    </AuthFrame>
  );
}
