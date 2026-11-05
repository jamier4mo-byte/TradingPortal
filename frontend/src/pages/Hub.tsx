import { ArrowUpRight, CalendarDays, Newspaper } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "../components/Card.tsx";
import { useAuth } from "../lib/auth.tsx";
import { greeting, session, ukClock, ukDate } from "../lib/time.ts";
import { useNow } from "../lib/useNow.ts";

/** Hub, first cut: greeting, launch islands and empty states. Real data arrives phase by phase. */
export default function Hub() {
  const now = useNow();
  const sess = session(now);
  const { user } = useAuth();
  return (
    <div className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6">
      {/* Hero greeting — the only place atmosphere is allowed */}
      <section
        aria-label="Greeting"
        className="relative col-span-full overflow-hidden rounded-card border border-border bg-surface-1 p-5 tablet:p-8"
      >
        <div aria-hidden className="hero-atmosphere pointer-events-none absolute inset-0 opacity-60" />
        <div className="relative">
          <p className="text-label uppercase tracking-[0.08em] text-muted">{ukDate(now)}</p>
          <h1 className="mt-2 text-heading font-semibold tablet:text-hero">{greeting(now)}, {user?.display_name ?? "there"}</h1>
          <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-muted">
            <span className="inline-flex items-center gap-2">
              <span
                aria-hidden
                className={`size-2 rounded-full ${sess === "Markets closed" ? "bg-stale" : "bg-live"}`}
              />
              {sess === "Markets closed" ? "Markets closed" : `${sess} session`}
            </span>
            <span className="num font-mono">UK {ukClock(now)}</span>
          </p>
        </div>
      </section>

      {/* Launch islands */}
      <LaunchIsland
        to="/journal"
        logo="/brand/replayjournal-logo.png"
        name="Replay Journal"
        subtitle="Ideal trades, backtests and analytics"
      />
      <LaunchIsland to="/news" logo="/brand/newsroom-logo.png" name="News Room" subtitle="Economic calendar and alerts" />

      <Card
        title="Today's news"
        subtitle="High-impact events for your instruments"
        className="col-span-full laptop:col-span-7"
        controls={<Newspaper aria-hidden className="size-5 text-subtle" />}
      >
        <EmptyState text="No news feed connected yet. The News Room build (Phase 4) fills this card." />
      </Card>
      <Card
        title="Calendar"
        subtitle="Team tasks and events"
        className="col-span-full laptop:col-span-5"
        controls={<CalendarDays aria-hidden className="size-5 text-subtle" />}
      >
        <EmptyState text="No tasks yet. The team calendar arrives with the Hub phase." />
      </Card>
    </div>
  );
}

function LaunchIsland({ to, logo, name, subtitle }: { to: string; logo: string; name: string; subtitle: string }) {
  return (
    <Link
      to={to}
      aria-label={`Open ${name}`}
      className="card group col-span-2 flex min-h-36 flex-col justify-between p-4 transition-[transform,border-color] duration-(--dur-quick) ease-(--ease-in-enter) hover:-translate-y-0.5 hover:border-border-strong tablet:col-span-4 tablet:p-6 laptop:col-span-6"
    >
      <div className="flex items-start justify-between gap-3">
        <img src={logo} alt={name} className="h-auto max-h-10 w-auto min-w-0 max-w-full object-contain object-left" />
        <ArrowUpRight aria-hidden className="hidden size-5 shrink-0 text-subtle transition-colors group-hover:text-accent tablet:block" />
      </div>
      <p className="mt-4 text-label text-muted tablet:text-body">{subtitle}</p>
    </Link>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-panel border border-dashed border-border-strong bg-surface-2/40 px-4 py-8 text-center text-body text-muted">
      {text}
    </div>
  );
}
