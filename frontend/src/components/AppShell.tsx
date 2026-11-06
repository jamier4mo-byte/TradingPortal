import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  Home,
  LogOut,
  MoreHorizontal,
  Newspaper,
  Plus,
  Search,
  Settings,
  Shield,
  Tags,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth.tsx";
import { initials } from "../lib/format.ts";
import { session, ukClock } from "../lib/time.ts";
import { useNow } from "../lib/useNow.ts";
import { useOnline } from "../lib/useMediaQuery.ts";
import { Logo, Tile } from "./Brand.tsx";
import { CommandPalette } from "./CommandPalette.tsx";
import { PageTransition } from "./PageTransition.tsx";
import { OfflineBanner, ownerBg } from "./ui/index.ts";
import { setPrintMode } from "../lib/print.ts";

const TOOLS = [
  { to: "/", label: "Hub", icon: Home, end: true, dot: "live" },
  { to: "/journal", label: "Replay Journal", short: "Journal", icon: BookOpen, dot: "live" },
  { to: "/news", label: "News Room", short: "News", icon: Newspaper, dot: "stale" },
  { to: "/calendar", label: "Calendar", icon: CalendarDays, dot: "stale" },
];

const SECONDARY = [
  { to: "/tags", label: "Tags", icon: Tags },
  { to: "/settings", label: "Settings", icon: Settings },
];

const PAGE_TITLES: Record<string, string> = {
  "/": "Hub",
  "/journal": "Replay Journal",
  "/news": "News Room",
  "/calendar": "Calendar",
  "/tags": "Tags",
  "/settings": "Settings",
  "/more": "More",
  "/admin/users": "Users",
  "/admin/tags": "Tags",
  "/dev/components": "Components",
};

const SIDEBAR_KEY = "tp.sidebar";

/** App shell. Laptop+: sidebar (collapsible to icons). Tablet: icon rail. Phone: top bar + bottom tabs. */
export default function AppShell({ children }: { children: ReactNode }) {
  const now = useNow();
  const online = useOnline();
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "icons";
    } catch {
      return false;
    }
  });

  // Save as PDF: the light print tokens for the whole page (charts read them when they redraw).
  useEffect(() => {
    const on = () => setPrintMode(true);
    const off = () => setPrintMode(false);
    window.addEventListener("beforeprint", on);
    window.addEventListener("afterprint", off);
    return () => {
      window.removeEventListener("beforeprint", on);
      window.removeEventListener("afterprint", off);
    };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleSidebar = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(SIDEBAR_KEY, c ? "full" : "icons");
      } catch {
        /* private mode */
      }
      return !c;
    });
  };

  const sess = session(now);
  const closed = sess === "Markets closed";
  const title = PAGE_TITLES[location.pathname] ?? PAGE_TITLES[`/${location.pathname.split("/")[1]}`] ?? "Trading Portal";
  const isAdmin = user?.role === "admin";
  const sidebarWidth = collapsed ? "laptop:w-[72px]" : "laptop:w-72";
  const contentPad = collapsed ? "laptop:pl-[72px]" : "laptop:pl-72";

  const navItem = ({ isActive }: { isActive: boolean }) =>
    [
      "group relative flex min-h-11 items-center gap-3 rounded-panel px-3 text-body transition-colors duration-(--dur-quick)",
      isActive ? "bg-accent-soft text-text" : "text-muted hover:bg-surface-2 hover:text-text",
    ].join(" ");

  return (
    <div className="min-h-dvh">
      {/* Sidebar (laptop+) / rail (tablet) */}
      <aside
        aria-label="Tools"
        className={`print:hidden fixed inset-y-0 left-0 z-20 hidden w-[72px] flex-col border-r border-border bg-bg px-3 py-4 tablet:flex ${sidebarWidth} transition-[width] duration-(--dur-standard) ease-(--ease-in-enter)`}
      >
        <NavLink to="/" className="mb-6 flex min-h-11 items-center px-1" aria-label="Trading Portal home">
          <Tile className={`size-10 ${collapsed ? "" : "laptop:hidden"}`} />
          {collapsed ? null : <Logo className="hidden h-10 laptop:block" />}
        </NavLink>
        <nav className="flex flex-col gap-1">
          {TOOLS.map(({ to, label, icon: Icon, end, dot }) => (
            <NavLink key={to} to={to} end={end} className={navItem} title={label}>
              <Icon aria-hidden className="size-5 shrink-0" strokeWidth={1.75} />
              <span className={collapsed ? "sr-only" : "sr-only laptop:not-sr-only"}>{label}</span>
              <span
                aria-hidden
                className={`absolute right-2.5 top-2.5 size-1.5 rounded-full ${dot === "live" ? "bg-live" : "bg-stale"} ${
                  collapsed ? "" : "laptop:static laptop:ml-auto"
                }`}
              />
            </NavLink>
          ))}
        </nav>
        <div className="mt-6 border-t border-border pt-4">
          <nav className="flex flex-col gap-1" aria-label="More">
            {SECONDARY.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={navItem} title={label}>
                <Icon aria-hidden className="size-5 shrink-0" strokeWidth={1.75} />
                <span className={collapsed ? "sr-only" : "sr-only laptop:not-sr-only"}>{label}</span>
              </NavLink>
            ))}
            {isAdmin ? (
              <NavLink to="/admin/users" className={navItem} title="Admin">
                <Shield aria-hidden className="size-5 shrink-0" strokeWidth={1.75} />
                <span className={collapsed ? "sr-only" : "sr-only laptop:not-sr-only"}>Admin</span>
              </NavLink>
            ) : null}
          </nav>
        </div>
        <button
          type="button"
          onClick={toggleSidebar}
          className="btn btn-ghost mt-auto hidden size-11 px-0 laptop:grid"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar to icons"}
          aria-pressed={collapsed}
        >
          {collapsed ? <ChevronsRight aria-hidden className="size-5" /> : <ChevronsLeft aria-hidden className="size-5" />}
        </button>
      </aside>

      <div className={`tablet:pl-[72px] ${contentPad} print:pl-0 transition-[padding] duration-(--dur-standard) ease-(--ease-in-enter)`}>
        {/* Top bar */}
        <header className="safe-top sticky top-0 z-10 print:hidden flex min-h-14 items-center gap-2 border-b border-border bg-bg/95 px-(--gutter-phone) tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
          <NavLink to="/" className="flex min-h-11 min-w-11 items-center tablet:hidden" aria-label="Trading Portal home">
            <Tile />
          </NavLink>
          <h1 className="truncate text-title font-semibold tablet:sr-only">{title}</h1>

          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="ml-auto flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-panel border border-border px-3 text-muted hover:border-border-strong hover:text-text tablet:ml-0 tablet:min-w-64 tablet:justify-start"
            aria-label="Jump to a screen (⌘K)"
          >
            <Search aria-hidden className="size-4" />
            <span className="hidden tablet:inline">Jump to…</span>
            <kbd className="ml-auto hidden rounded border border-border px-1.5 font-mono text-label text-muted laptop:inline">⌘K</kbd>
          </button>

          <div className="ml-auto hidden items-center gap-3 tablet:flex">
            <span className="inline-flex items-center gap-2 text-body text-muted" aria-label={`Session: ${sess}`}>
              <span aria-hidden className={`size-2 rounded-full ${closed ? "bg-stale" : "bg-live"}`} />
              <span className="hidden laptop:inline">{closed ? "Markets closed" : `${sess} open`}</span>
            </span>
            <span className="num font-mono text-body text-muted" aria-label="UK time">
              UK {ukClock(now)}
            </span>
          </div>

          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Notifications (coming with the News Room)" disabled>
            <Bell aria-hidden className="size-5" strokeWidth={1.75} />
          </button>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Account menu">
                <span className={`grid size-8 place-items-center rounded-full text-label font-semibold text-bg ${ownerBg(user?.colour_index ?? 0)}`}>
                  {initials(user?.display_name ?? "?")}
                </span>
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" sideOffset={6} className="card z-30 min-w-56 p-1.5 data-[state=open]:animate-[page-enter_var(--dur-quick)_var(--ease-in-enter)]">
                <div className="px-3 py-2">
                  <p className="truncate text-body font-medium">{user?.display_name}</p>
                  <p className="truncate text-label text-muted">{user?.email}</p>
                </div>
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <MenuItem onSelect={() => navigate("/settings")} icon={Settings}>
                  Settings
                </MenuItem>
                {isAdmin ? (
                  <MenuItem onSelect={() => navigate("/admin/users")} icon={Shield}>
                    Admin
                  </MenuItem>
                ) : null}
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <MenuItem
                  onSelect={() => {
                    void signOut().then(() => navigate("/login"));
                  }}
                  icon={LogOut}
                >
                  Sign out
                </MenuItem>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </header>

        <main className="mx-auto max-w-[1760px] px-(--gutter-phone) pt-6 pb-32 tablet:px-(--gutter-tablet) tablet:pb-10 desktop:px-(--gutter-desktop)">
          {online ? null : <OfflineBanner className="mb-4" />}
          <PageTransition>{children}</PageTransition>
        </main>
      </div>

      {/* Phone: floating "+" for quick logging (wired up in Prompt 2) */}
      <button
        type="button"
        className="fixed right-4 bottom-[calc(72px+env(safe-area-inset-bottom))] z-20 grid size-14 place-items-center rounded-full bg-accent text-on-accent shadow-none tablet:hidden"
        aria-label="Quick log a trade"
        onClick={() => navigate("/journal?quicklog=1")}
      >
        <Plus aria-hidden className="size-6" strokeWidth={2} />
      </button>

      {/* Phone tab bar */}
      <nav
        aria-label="Tools"
        className="safe-bottom fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 print:hidden border-t border-border bg-bg/95 tablet:hidden"
      >
        {TOOLS.map(({ to, label, short, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center gap-0.5 text-label ${isActive ? "font-medium text-accent" : "text-muted"}`
            }
          >
            <Icon aria-hidden className="size-5" strokeWidth={1.75} />
            <span>{short ?? label}</span>
          </NavLink>
        ))}
        <NavLink
          to="/more"
          className={({ isActive }) =>
            `flex min-h-14 flex-col items-center justify-center gap-0.5 text-label ${isActive ? "font-medium text-accent" : "text-muted"}`
          }
        >
          <MoreHorizontal aria-hidden className="size-5" strokeWidth={1.75} />
          <span>More</span>
        </NavLink>
      </nav>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}

function MenuItem({ children, onSelect, icon: Icon }: { children: ReactNode; onSelect: () => void; icon: typeof Settings }) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className="flex min-h-11 cursor-pointer items-center gap-3 rounded-panel px-3 text-body text-muted outline-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-text"
    >
      <Icon aria-hidden className="size-4" strokeWidth={1.75} />
      {children}
    </DropdownMenu.Item>
  );
}
