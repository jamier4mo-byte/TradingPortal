import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, KeyRound, UserPlus } from "lucide-react";
import { useState } from "react";

import Card from "../../components/Card.tsx";
import { PeopleEmpty } from "../../components/ui/Illustrations.tsx";
import { ConfirmDialog, Drawer, EmptyState, ErrorState, OwnerChip, PillToggle, SkeletonText, useToast } from "../../components/ui/index.ts";
import { api, type Invite, type ResetLink, type Role, type User } from "../../lib/api.ts";
import { useAuth } from "../../lib/auth.tsx";
import { relativeTime, shortDateTime } from "../../lib/format.ts";
import { AdminTabs } from "./AdminTabs.tsx";

export default function AdminUsers() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { user: me } = useAuth();
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: () => api.get<User[]>("/api/admin/users") });
  const [inviteOpen, setInviteOpen] = useState(false);
  const [confirm, setConfirm] = useState<{ user: User; status: "active" | "deactivated" } | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "users"] });

  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) => api.patch<User>(`/api/admin/users/${id}/role`, { role }),
    onSuccess: (u) => {
      void refresh();
      toast({ title: `${u.display_name} is now ${u.role === "admin" ? "an admin" : "a member"}` });
    },
    onError: (err) => toast({ title: "Couldn't change the role", text: err.message, tone: "loss" }),
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "deactivated" }) => api.patch<User>(`/api/admin/users/${id}/status`, { status }),
    onSuccess: (u) => {
      void refresh();
      setConfirm(null);
      toast({ title: u.status === "deactivated" ? `${u.display_name} deactivated` : `${u.display_name} reactivated`, text: u.status === "deactivated" ? "Signed out everywhere. Their work stays visible." : undefined });
    },
    onError: (err) => toast({ title: "Couldn't change the status", text: err.message, tone: "loss" }),
  });
  const resetLink = useMutation({
    mutationFn: (id: number) => api.post<ResetLink>(`/api/admin/users/${id}/reset-link`),
    onSuccess: async (r) => {
      await copy(r.url);
      toast({ title: "Reset link copied", text: "It works once and expires in an hour. Send it to them yourself." });
    },
    onError: (err) => toast({ title: "Couldn't make a reset link", text: err.message, tone: "loss" }),
  });

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <AdminTabs />
      <Card
        title="Users"
        subtitle="Accounts come from invite links. Nobody is ever deleted."
        controls={
          <button type="button" className="btn btn-primary" onClick={() => setInviteOpen(true)}>
            <UserPlus aria-hidden className="size-4" />
            <span className="hidden tablet:inline">Invite someone</span>
            <span className="tablet:hidden">Invite</span>
          </button>
        }
      >
        {users.isPending ? (
          <SkeletonText lines={4} />
        ) : users.isError ? (
          <ErrorState text={users.error.message} onRetry={() => users.refetch()} />
        ) : users.data.length === 0 ? (
          <EmptyState illustration={<PeopleEmpty />} title="Just you so far" text="Invite a mate and they'll appear here." />
        ) : (
          <ul className="divide-y divide-border">
            {users.data.map((u) => {
              const self = u.id === me?.id;
              const deactivated = u.status === "deactivated";
              return (
                <li key={u.id} className="flex flex-col gap-3 py-3 tablet:flex-row tablet:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <OwnerChip name={u.display_name} colourIndex={u.colour_index} deactivated={deactivated} compact />
                    <div className="min-w-0">
                      <p className={`truncate text-body ${deactivated ? "text-muted" : ""}`}>
                        {u.label}
                        {self ? <span className="text-muted"> (you)</span> : null}
                      </p>
                      <p className="num truncate text-label text-muted">
                        {u.email} · seen {relativeTime(u.last_seen_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <PillToggle<Role>
                      size="sm"
                      label={`Role for ${u.display_name}`}
                      value={u.role}
                      options={[
                        { value: "member", label: "Member" },
                        { value: "admin", label: "Admin" },
                      ]}
                      onChange={(role) => !self && setRole.mutate({ id: u.id, role })}
                    />
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => resetLink.mutate(u.id)}
                      disabled={deactivated || resetLink.isPending}
                      aria-label={`Copy a reset link for ${u.display_name}`}
                    >
                      <KeyRound aria-hidden className="size-4" />
                      <span className="hidden laptop:inline">Reset link</span>
                    </button>
                    <button
                      type="button"
                      className={`btn ${deactivated ? "btn-secondary" : "btn-ghost"}`}
                      disabled={self}
                      onClick={() => setConfirm({ user: u, status: deactivated ? "active" : "deactivated" })}
                    >
                      {deactivated ? "Reactivate" : "Deactivate"}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <InviteDrawer open={inviteOpen} onOpenChange={setInviteOpen} />

      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={confirm?.status === "deactivated" ? `Deactivate ${confirm.user.display_name}?` : `Reactivate ${confirm?.user.display_name}?`}
        text={
          confirm?.status === "deactivated"
            ? "They're signed out everywhere and can't sign in again. Their strategies, trades and tasks stay visible, labelled “(deactivated)”."
            : "They can sign in again with their existing password or passkey."
        }
        confirmLabel={confirm?.status === "deactivated" ? "Deactivate" : "Reactivate"}
        danger={confirm?.status === "deactivated"}
        busy={setStatus.isPending}
        onConfirm={() => confirm && setStatus.mutate({ id: confirm.user.id, status: confirm.status })}
      />
    </div>
  );
}

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function InviteDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [role, setRole] = useState<Role>("member");
  const [invite, setInvite] = useState<Invite | null>(null);
  const [copied, setCopied] = useState(false);
  const create = useMutation({
    mutationFn: () => api.post<Invite>("/api/admin/invites", { role }),
    onSuccess: (inv) => {
      setInvite(inv);
      setCopied(false);
    },
  });
  const close = (o: boolean) => {
    onOpenChange(o);
    if (!o) {
      setInvite(null);
      setRole("member");
    }
  };
  return (
    <Drawer open={open} onOpenChange={close} title="Invite someone" description="The link works once and lasts 7 days. Send it to them yourself.">
      {invite ? (
        <div className="flex flex-col gap-4">
          <div className="rounded-panel border border-border bg-surface-2 p-3">
            <p className="num text-label text-muted">Invite link · {invite.role} · expires {shortDateTime(invite.expires_at)}</p>
            <p className="mt-1 break-all font-mono text-label" data-testid="invite-url">
              {invite.url}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={async () => {
              setCopied(await copy(invite.url));
            }}
          >
            {copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />}
            {copied ? "Copied" : "Copy link"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setInvite(null)}>
            Make another
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div>
            <p className="mb-2 text-body font-medium">Role</p>
            <PillToggle<Role>
              label="Role"
              value={role}
              onChange={setRole}
              options={[
                { value: "member", label: "Member" },
                { value: "admin", label: "Admin" },
              ]}
            />
            <p className="mt-2 text-label text-muted">Members edit only their own work and see everyone&rsquo;s. Admins can change anything.</p>
          </div>
          {create.isError ? <p className="text-body text-loss">{create.error.message}</p> : null}
          <button type="button" className="btn btn-primary" onClick={() => create.mutate()} disabled={create.isPending}>
            Create invite link
          </button>
        </div>
      )}
    </Drawer>
  );
}
