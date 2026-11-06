import { Bell, ChevronRight, LineChart, LogOut, Palette, Settings, Shield, Tags } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth.tsx";
import { ownerBg } from "../components/ui/index.ts";
import { initials } from "../lib/format.ts";

/** Phone-only: everything that doesn't fit in the bottom tabs. */
export default function More() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const items = [
    { to: "/markets", label: "Markets", text: "Watchlist, prices and your Twelve Data credits", icon: LineChart },
    { to: "/settings/alerts", label: "News alerts", text: "Notifications before high-impact news", icon: Bell },
    { to: "/tags", label: "Tags", text: "The shared ICT/SMC vocabulary", icon: Tags },
    { to: "/settings", label: "Settings", text: "Profile, password, passkeys, API keys, motion", icon: Settings },
    ...(user?.role === "admin" ? [{ to: "/admin/users", label: "Admin", text: "Users, invites and tag curation", icon: Shield }] : []),
    ...(import.meta.env.DEV ? [{ to: "/dev/components", label: "Components", text: "Design gallery", icon: Palette }] : []),
  ];
  return (
    <div className="mx-auto max-w-xl">
      <div className="card flex items-center gap-3 p-4">
        <span className={`grid size-11 place-items-center rounded-full text-body font-semibold text-bg ${ownerBg(user?.colour_index ?? 0)}`}>
          {initials(user?.display_name ?? "?")}
        </span>
        <div className="min-w-0">
          <p className="truncate text-title font-semibold">{user?.display_name}</p>
          <p className="truncate text-label text-muted">
            {user?.email} · {user?.role}
          </p>
        </div>
      </div>
      <ul className="card mt-4 divide-y divide-border">
        {items.map(({ to, label, text, icon: Icon }) => (
          <li key={to}>
            <Link to={to} className="flex min-h-14 items-center gap-3 px-4 py-2 hover:bg-surface-2">
              <Icon aria-hidden className="size-5 text-muted" strokeWidth={1.75} />
              <span className="min-w-0 flex-1">
                <span className="block text-body">{label}</span>
                <span className="block text-label text-muted">{text}</span>
              </span>
              <ChevronRight aria-hidden className="size-4 text-subtle" />
            </Link>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="btn btn-secondary mt-4 w-full"
        onClick={() => {
          void signOut().then(() => navigate("/login"));
        }}
      >
        <LogOut aria-hidden className="size-4" />
        Sign out
      </button>
    </div>
  );
}
