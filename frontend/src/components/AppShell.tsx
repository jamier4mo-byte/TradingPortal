import {
  Bell,
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  Home,
  LineChart,
  MoreHorizontal,
  Newspaper,
  Plus,
  Search,
  Settings,
  Shield,
  Tags,
} from "lucide-react";
import { lazy, type ReactNode, Suspense, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth.tsx";
import { session, ukClock } from "../lib/time.ts";
import { useNow } from "../lib/useNow.ts";
import { useOnline } from "../lib/useMediaQuery.ts";
import { AvatarButton } from "./AvatarButton.tsx";
import { Logo, Tile } from "./Brand.tsx";
import { PageTransition } from "./PageTransition.tsx";
import { OfflineBanner } from "./ui/index.ts";
import { UpdateReady } from "./UpdateReady.tsx";
import { setPrintMode } from "../lib/print.ts";
import { onChimeMessage, playChime } from "../lib/push.ts";
import { takeIntro } from "../lib/intro.ts";
import { installVisibilityPause } from "../lib/motion.ts";

// The portal intro and the Cmd+K palette are their own chunks so the Hub's initial JS stays under budget
// (F18). Login prefetches the intro; the palette is fetched when the Jump button is pointed at or focused,
// and mounted on its first open (then kept mounted so its close animation can run).
const PortalIntro = lazy(() => import("./PortalIntro.tsx"));
// The account menu (Radix menu + floating-ui) loads after first paint: the avatar shows meanwhile.
const AccountMenu = lazy(() => import("./AccountMenu.tsx"));
const CommandPalette = lazy(() => import("./CommandPalette.tsx").then((m) => ({ default: m.CommandPalette })));
const prefetchPalette = () => void import("./CommandPalette.tsx");

const TOOLS = [
  { to: "/", label: "Hub", icon: Home, end: true, dot: "live" },
  { to: "/journal", label: "Replay Journal", short: "Journal", icon: BookOpen, dot: "live" },
  { to: "/news", label: "News Room", short: "News", icon: Newspaper, dot: "live" },
];

const SECONDARY = [
  { to: "/markets", label: "Markets", icon: LineChart },
  { to: "/tags", label: "Tags", icon: Tags },
  { to: "/settings", label: "Settings", icon: Settings },
];

const PAGE_TITLES: Record<string, string> = {
  "/": "Hub",
  "/journal": "Replay Journal",
  "/news": "News Room",
  "/markets": "Markets",
  "/settings/alerts": "Alerts",
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
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteMounted, setPaletteMounted] = useState(false);
  const openPalette = (open: boolean) => {
    if (open) setPaletteMounted(true);
    setPaletteOpen(open);
  };
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "icons";
    } catch {
      return false;
    }
  });

  // Optional soft chime: the service worker asks an open page to play it (only when the alert says so).
  useEffect(() => onChimeMessage(() => playChime()), []);

  // Portal intro: once per UK day, only right after a sign-in, only in Full motion (lib/intro.ts decides).
  // The Hub mounts underneath it, so no time is lost.
  const [intro, setIntro] = useState(() => takeIntro(user?.motion_pref));
  // Looping decoration (.pulse, .skeleton) pauses while the tab is hidden.
  useEffect(() => installVisibilityPause(), []);
  // Fetch the palette chunk once the first paint is out of the way, so the first ⌘K opens at once.
  useEffect(() => {
    const timer = window.setTimeout(prefetchPalette, 1500);
    return () => window.clearTimeout(timer);
  }, []);

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
        setPaletteMounted(true);
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
        <header className="safe-top safe-x sticky top-0 z-10 print:hidden flex min-h-14 items-center gap-2 border-b border-border bg-bg/95">
          <NavLink to="/" className="flex min-h-11 min-w-11 items-center tablet:hidden" aria-label="Trading Portal home">
            <Tile />
          </NavLink>
          <h1 className="truncate text-title font-semibold tablet:sr-only">{title}</h1>

          <button
            type="button"
            onClick={() => openPalette(true)}
            onPointerEnter={prefetchPalette}
            onFocus={prefetchPalette}
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

          <NavLink to="/settings/alerts" className="btn btn-ghost size-11 px-0" aria-label="News alerts">
            <Bell aria-hidden className="size-5" strokeWidth={1.75} />
          </NavLink>

          <Suspense fallback={<AvatarButton disabled aria-disabled="true" />}>
            <AccountMenu />
          </Suspense>
        </header>

        <main className="safe-x mx-auto max-w-[1760px] pt-6 pb-32 tablet:pb-10">
          {online ? null : <OfflineBanner className="mb-4" />}
          <UpdateReady className="mb-4" />
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

      {paletteMounted ? (
        <Suspense fallback={null}>
          <CommandPalette open={paletteOpen} onOpenChange={openPalette} />
        </Suspense>
      ) : null}
      {intro ? (
        <Suspense fallback={null}>
          <PortalIntro onDone={() => setIntro(false)} />
        </Suspense>
      ) : null}
    </div>
  );
}
