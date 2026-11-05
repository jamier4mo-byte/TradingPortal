import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Field, SkeletonText, TextInput } from "../../components/ui/index.ts";
import { api, type User } from "../../lib/api.ts";
import { AuthFrame } from "./AuthFrame.tsx";

interface InvitePeek {
  role: "admin" | "member";
  email: string | null;
  expires_at: string;
}

export default function AcceptInvite() {
  const { token = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const peek = useQuery({
    queryKey: ["invite", token],
    queryFn: () => api.get<InvitePeek>(`/api/auth/invite/${token}`),
    retry: false,
  });
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await api.post<User>("/api/auth/invite/accept", {
        token,
        email: peek.data?.email ?? email,
        display_name: name,
        password,
      });
      qc.setQueryData(["me"], u);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the account.");
    } finally {
      setBusy(false);
    }
  };

  if (peek.isPending) {
    return (
      <AuthFrame title="Checking your invite">
        <SkeletonText lines={4} />
      </AuthFrame>
    );
  }
  if (peek.isError) {
    return (
      <AuthFrame title="This invite won't work" intro={peek.error.message}>
        <p className="text-body text-muted">Invite links last 7 days and can be used once. Ask Jamie for a fresh one.</p>
        <Link to="/login" className="btn btn-secondary mt-6 w-full">
          Go to sign in
        </Link>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Create your account"
      intro={`You've been invited as ${peek.data.role === "admin" ? "an admin" : "a member"}. Pick a name and a password.`}
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="Email" help={peek.data.email ? "This invite is for this address." : undefined}>
          {(p) => (
            <TextInput
              {...p}
              type="email"
              name="email"
              autoComplete="username"
              inputMode="email"
              required
              readOnly={!!peek.data.email}
              value={peek.data.email ?? email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
        <Field label="Display name" help="How you'll appear on strategies and tasks.">
          {(p) => <TextInput {...p} name="name" autoComplete="nickname" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Password" help="At least 10 characters." error={error}>
          {(p) => (
            <TextInput
              {...p}
              type="password"
              name="new-password"
              autoComplete="new-password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <button type="submit" className="btn btn-primary mt-2 w-full" disabled={busy}>
          Create account
        </button>
      </form>
    </AuthFrame>
  );
}
