import { Bell, BookOpen, CalendarDays, Home, Newspaper, Search, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { ukClock } from "../lib/time.ts";
import { useNow } from "../lib/useNow.ts";

const TOOLS = [
  { to: "/", label: "Hub", icon: Home, end: true },
  { to: "/journal", label: "Replay Journal", short: "Journal", icon: BookOpen },
  { to: "/news", label: "News Room", short: "News", icon: Newspaper },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
];

const navItem = ({ isActive }: { isActive: boolean }) =>
  [
    "flex min-h-11 items-center gap-3 rounded-panel px-3 text-body transition-colors duration-(--dur-quick)",
    isActive ? "bg-accent-soft text-text" : "text-muted hover:bg-surface-2 hover:text-text",
  ].join(" ");

/** App shell. Laptop+: full sidebar. Tablet: icon rail. Phone: top bar + bottom tab bar. */
export default function AppShell({ children }: { children: ReactNode }) {
  const now = useNow();
  return (
    <div className="min-h-dvh">
      {/* Sidebar / rail */}
      <aside
        aria-label="Tools"
        className="fixed inset-y-0 left-0 z-20 hidden w-[72px] flex-col border-r border-border bg-bg px-3 py-4 tablet:flex laptop:w-60"
      >
        <a href="/" className="mb-6 flex min-h-11 items-center px-1" aria-label="Trading Portal home">
          <img src="/brand/t-tile.png" alt="" className="size-10 laptop:hidden" />
          <img src="/brand/tradingportal-logo.png" alt="Trading Portal" className="hidden h-7 w-auto laptop:block" />
        </a>
        <nav className="flex flex-col gap-1">
          {TOOLS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={navItem} title={label}>
              <Icon aria-hidden className="size-5 shrink-0" strokeWidth={1.75} />
              <span className="sr-only laptop:not-sr-only">{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="tablet:pl-[72px] laptop:pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-bg/95 px-(--gutter-phone) tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
          <a href="/" className="flex min-h-11 min-w-11 items-center tablet:hidden" aria-label="Trading Portal home">
            <img src="/brand/t-tile.png" alt="" className="size-9" />
          </a>
          <button
            type="button"
            className="ml-auto flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-panel border border-border px-3 text-muted tablet:justify-start hover:border-border-strong hover:text-text tablet:ml-0 tablet:min-w-64"
            aria-label="Search (coming soon)"
          >
            <Search aria-hidden className="size-4" />
            <span className="hidden tablet:inline">Search</span>
            <kbd className="ml-auto hidden rounded border border-border px-1.5 font-mono text-label text-muted laptop:inline">⌘K</kbd>
          </button>
          <div className="ml-auto hidden items-center gap-1 tablet:flex">
            <span className="num px-2 font-mono text-body text-muted" aria-label="UK time">
              UK {ukClock(now)}
            </span>
          </div>
          <button type="button" className="grid size-11 place-items-center rounded-panel text-muted hover:text-text" aria-label="Notifications">
            <Bell aria-hidden className="size-5" strokeWidth={1.75} />
          </button>
          <button type="button" className="grid size-11 place-items-center rounded-panel text-muted hover:text-text" aria-label="Account">
            <UserRound aria-hidden className="size-5" strokeWidth={1.75} />
          </button>
        </header>

        <main className="mx-auto max-w-[1760px] px-(--gutter-phone) pt-6 pb-28 tablet:px-(--gutter-tablet) tablet:pb-10 desktop:px-(--gutter-desktop)">
          {children}
        </main>
      </div>

      {/* Phone tab bar */}
      <nav
        aria-label="Tools"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t border-border bg-bg/95 pb-[env(safe-area-inset-bottom)] tablet:hidden"
      >
        {TOOLS.map(({ to, label, short, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center gap-0.5 text-label ${isActive ? "text-accent" : "text-muted"}`
            }
          >
            <Icon aria-hidden className="size-5" strokeWidth={1.75} />
            <span>{short ?? label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
