import { lazy } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card.tsx";
import { LaunchOverlay } from "../components/launch/LaunchOverlay.tsx";
import { useLaunch } from "../components/launch/useLaunch.ts";
import { SkeletonText, Stagger } from "../components/ui/index.ts";
import { useAuth } from "../lib/auth.tsx";
import { INSTALL_DONE_KEY, isStandalone, queryState, remembered, useHub } from "../lib/hub.ts";
import { useSummary } from "../lib/journal.ts";
import { countdownText, useNextEvent } from "../lib/news.ts";
import { useDevice } from "../lib/useMediaQuery.ts";
import { Checklist } from "./hub/Checklist.tsx";
import { Hero } from "./hub/Hero.tsx";
import { LaunchIsland } from "./hub/LaunchIsland.tsx";
import { LazyMount } from "./hub/LazyMount.tsx";
import { TodaysNews } from "./hub/TodaysNews.tsx";

// Below the fold: each is its own chunk, mounted when it scrolls near the viewport (F18). ECharts and
// FullCalendar never reach this chunk; the calendar card is another build's component, imported lazily.
const CalendarCard = lazy(() => import("../components/calendar/CalendarCard.tsx"));
const MarketPanel = lazy(() => import("./hub/MarketPanel.tsx"));
const Streak = lazy(() => import("./hub/Streak.tsx"));
const Bests = lazy(() => import("./hub/Bests.tsx"));
const WeekPair = lazy(() => import("./hub/WeekPair.tsx"));

/** The Hub (Foundations §1), top to bottom per 1.6: hero → today's news → launch islands → team calendar →
 * live market data, then the engagement cards. From 1440 px the market panel becomes a side column beside
 * the hero, news and islands instead of a stretched full-width card. */
export default function Hub() {
  const { user } = useAuth();
  const device = useDevice();
  const hub = useHub();
  const summary = useSummary();
  const next = useNextEvent(true);
  const { tool, launch } = useLaunch();

  const firstName = (user?.display_name ?? "there").trim().split(/\s+/)[0] || "there";
  const last = summary.data?.last_session;
  // A mini-stat is `undefined` while loading (skeleton line) and `null` when it can't load (offline or
  // errored): the island then shows its subtitle alone rather than shimmering forever.
  const journalStat = summary.data
    ? last
      ? `Last session: ${last.trade_count} ${last.trade_count === 1 ? "trade" : "trades"}${last.strategy_name ? ` · ${last.strategy_name}` : ""}`
      : summary.data.strategies
        ? `${summary.data.strategies} ${summary.data.strategies === 1 ? "strategy" : "strategies"} · no sessions yet`
        : "Create your first strategy"
    : queryState(summary) === "pending"
      ? undefined
      : null;
  const newsStat = next.data
    ? next.data.event && next.data.seconds_until !== null
      ? `Next event: ${next.data.event.currency} ${next.data.event.name} in ${countdownText(next.data.seconds_until)}`
      : "No high-impact news ahead"
    : queryState(next) === "pending"
      ? undefined
      : null;
  const showWeek = hub.data?.week_recap.show ?? false;
  // When the checklist is finished its slot goes, so the streak and bests share the row at desktop and up.
  const checklistGone = hub.data ? hub.data.checklist.all_done_server && (isStandalone() || remembered(INSTALL_DONE_KEY)) : false;
  const engagementSpan = checklistGone ? "col-span-full laptop:col-span-6" : "col-span-full laptop:col-span-6 desktop:col-span-4";

  return (
    <>
      {/* First load of the Hub this session: the sections fade and rise in 40 ms apart; revisits render at once. */}
      <Stagger screenKey="hub" className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6">
        <Hero firstName={firstName} welcomeBack={hub.data?.welcome_back ?? false} className="col-span-full desktop:col-span-8" />

        <TodaysNews className="col-span-full desktop:col-span-8" />

        <LaunchIsland
          tool="journal"
          logo="/brand/replayjournal-logo.png"
          subtitle="Ideal trades, backtests and analytics"
          stat={journalStat}
          onLaunch={launch}
          className="col-span-2 tablet:col-span-4 laptop:col-span-6 desktop:col-span-4"
        />
        <LaunchIsland
          tool="news"
          logo="/brand/newsroom-logo.png"
          subtitle="Economic calendar and alerts"
          stat={newsStat}
          onLaunch={launch}
          className="col-span-2 tablet:col-span-4 laptop:col-span-6 desktop:col-span-4"
        />

        <Card
          title="Team calendar"
          subtitle={device === "phone" ? "Today and the next two days" : "This week"}
          className="col-span-full"
          controls={
            <Link to="/calendar" className="btn btn-ghost">
              Open calendar
            </Link>
          }
        >
          <LazyMount fallback={<SkeletonText lines={4} />}>
            <CalendarCard variant={device === "phone" ? "agenda" : "week"} />
          </LazyMount>
        </Card>

        {/* 1.5: from 1440 px this becomes the side column beside the hero, news and islands (extra panel, not a stretched card). */}
        <LazyMount
          className="col-span-full desktop:col-span-4 desktop:col-start-9 desktop:row-span-3 desktop:row-start-1"
          fallback={
            <Card title="Live market data" subtitle="Delayed prices from your Twelve Data key" className="h-full">
              <SkeletonText lines={5} />
            </Card>
          }
        >
          <MarketPanel />
        </LazyMount>

        <Checklist className="col-span-full laptop:col-span-6 desktop:col-span-4" />

        <Card title="Showing up" subtitle="Process streak" className={engagementSpan}>
          <LazyMount fallback={<SkeletonText lines={3} />}>
            <Streak />
          </LazyMount>
        </Card>

        <Card title="Personal bests" subtitle="Milestones in process, not profit" className={engagementSpan}>
          <LazyMount fallback={<SkeletonText lines={3} />}>
            <Bests />
          </LazyMount>
        </Card>

        {showWeek ? (
          <LazyMount className="col-span-full" fallback={<SkeletonText lines={4} />}>
            <WeekPair />
          </LazyMount>
        ) : null}
      </Stagger>

      <LaunchOverlay tool={tool} />
    </>
  );
}
