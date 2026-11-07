import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { OfflineGlyph } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonText, useToast } from "../../components/ui/index.ts";
import { celebratedKey, type PersonalBest, queryState, remember, remembered, useHub } from "../../lib/hub.ts";
import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";
import { StaleFigures } from "./StaleStamp.tsx";

function describe(b: PersonalBest): string {
  if (b.key === "longest_rule_run") return `${b.value_text} following every rule`;
  return `${b.value_text}${b.detail ? ` in ${b.detail}` : ""}`;
}

/** Personal bests: best month in R and the longest run of rule-following trades. One restrained
 * celebration (a ring sweep and a quiet toast) the first time a new best is seen on this device.
 * No confetti; nothing for individual wins. Lazy: lives below the fold. */
export default function Bests() {
  const hub = useHub();
  const { toast } = useToast();
  const [celebrating, setCelebrating] = useState<string | null>(null);
  const bests = hub.data?.personal_bests;

  useEffect(() => {
    const fresh = bests?.find((b) => b.is_new && !remembered(celebratedKey(b.key, b.achieved_at)));
    if (!fresh) return;
    remember(celebratedKey(fresh.key, fresh.achieved_at));
    if (motionLevel() !== "off") setCelebrating(fresh.key);
    toast({ title: `New personal best: ${describe(fresh)}` });
  }, [bests, toast]);

  const state = queryState(hub);
  if (state === "pending") return <SkeletonText lines={3} />;
  if (state === "offline") return <EmptyState illustration={<OfflineGlyph className="size-8" />} title="You're offline" text="Your bests load when you're back online." />;
  if (!hub.data) return <ErrorState title="Personal bests didn't load" text={hub.error?.message} onRetry={() => void hub.refetch()} />;
  if (!bests || bests.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-body text-muted">Your bests appear after your first backtest month and your first run of trades with every rule followed.</p>
        <Link to="/journal" className="btn btn-ghost self-start">
          Open the journal
        </Link>
      </div>
    );
  }
  return (
    <StaleFigures paths={["/api/hub"]} dataUpdatedAt={hub.dataUpdatedAt}>
      <ul className="grid gap-3 tablet:grid-cols-2" aria-label="Personal bests">
      {bests.map((b) => (
        <li key={b.key} className="relative rounded-panel border border-border bg-surface-2 p-3">
          <AnimatePresence>{celebrating === b.key ? <RingSweep onDone={() => setCelebrating(null)} /> : null}</AnimatePresence>
          <p className="flex items-center gap-2 text-label text-muted">
            {b.label}
            {b.is_new ? <span className="rounded-pill border border-accent px-1.5 text-label text-text">New</span> : null}
          </p>
          <p className="num mt-1 text-heading font-semibold leading-none">{b.value_text}</p>
          {b.detail ? <p className="num mt-1 text-label text-muted">{b.detail}</p> : null}
        </li>
      ))}
      </ul>
    </StaleFigures>
  );
}

/** The celebration: a single accent ring drawn around the badge over --dur-emphasis, then it fades. In
 * Reduced motion the ring fades in and out instead of sweeping. */
function RingSweep({ onDone }: { onDone: () => void }) {
  const full = motionLevel() === "full";
  return (
    <motion.svg
      aria-hidden
      className="pointer-events-none absolute inset-0 size-full overflow-visible text-accent"
      exit={{ opacity: 0 }}
      transition={{ duration: dur.standard() }}
    >
      <motion.rect
        x={1}
        y={1}
        rx={9}
        style={{ width: "calc(100% - 2px)", height: "calc(100% - 2px)" }}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        initial={full ? { pathLength: 0, opacity: 1 } : { pathLength: 1, opacity: 0 }}
        animate={full ? { pathLength: 1, opacity: 1 } : { pathLength: 1, opacity: 1 }}
        transition={{ duration: dur.emphasis(), ease: [...easeEnter] }}
        onAnimationComplete={() => window.setTimeout(onDone, dur.standard() * 1000)}
      />
    </motion.svg>
  );
}
