import { ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { ErrorState, SkeletonText } from "../../components/ui/index.ts";
import { type Checklist as ChecklistData, INSTALL_DONE_KEY, isStandalone, queryState, remember, remembered, useHub } from "../../lib/hub.ts";
import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";

type ServerKey = Exclude<keyof ChecklistData, "all_done_server">;

const ITEMS: { key: ServerKey; label: string; hint: string; to: string }[] = [
  { key: "twelve_data_key", label: "Add your Twelve Data key", hint: "Live prices use your own free key", to: "/settings#keys" },
  { key: "strategy_created", label: "Create a strategy", hint: "Rules, instruments and a reasoning template", to: "/journal" },
  { key: "first_csv_imported", label: "Import your first CSV", hint: "An FX Replay export, ideal trades or a backtest", to: "/journal" },
  { key: "alerts_enabled", label: "Enable alerts", hint: "A nudge before high-impact news", to: "/settings/alerts" },
];

/** First-run checklist (F15): four server-side facts and one the device knows (installed to the home
 * screen). Ticks draw themselves in when an item flips to done; the card hides once all five are done.
 * Everyone sees it for their own account. */
export function Checklist({ className = "" }: { className?: string }) {
  const hub = useHub();
  const [installed, setInstalled] = useState(() => isStandalone() || remembered(INSTALL_DONE_KEY));

  const state = queryState(hub);
  if (state === "pending") {
    return (
      <Card title="Getting set up" className={className}>
        <SkeletonText lines={5} />
      </Card>
    );
  }
  if (state === "offline") return null; // nothing cached: the checklist waits for a connection rather than shimmering
  if (!hub.data) {
    return (
      <Card title="Getting set up" className={className}>
        <ErrorState title="The checklist didn't load" text={hub.error?.message} onRetry={() => void hub.refetch()} />
      </Card>
    );
  }
  const data = hub.data.checklist;
  const done = ITEMS.filter((i) => data[i.key]).length + (installed ? 1 : 0);
  if (done === 5) return null;

  const markInstalled = () => {
    remember(INSTALL_DONE_KEY);
    setInstalled(true);
  };

  return (
    <Card title="Getting set up" subtitle={`${done} of 5 done`} className={className}>
      <ol className="flex flex-col divide-y divide-border">
        {ITEMS.map((item) => (
          <li key={item.key}>
            <Link to={item.to} className="flex min-h-11 items-center gap-3 py-2 text-body hover:text-text" aria-describedby={`chk-${item.key}`}>
              <Tick done={data[item.key]} />
              <span className="min-w-0 flex-1">
                <span className={data[item.key] ? "text-muted line-through" : ""}>{item.label}</span>
                <span id={`chk-${item.key}`} className="block text-label text-muted">
                  {item.hint}
                </span>
              </span>
              <ChevronRight aria-hidden className="size-4 shrink-0 text-subtle" />
            </Link>
          </li>
        ))}
        <li className="flex min-h-11 items-center gap-3 py-2 text-body">
          <Tick done={installed} />
          <span className="min-w-0 flex-1">
            <span className={installed ? "text-muted line-through" : ""}>Install to the home screen</span>
            {installed ? null : (
              <span className="block text-label text-muted">
                iPhone: Share → Add to Home Screen. Android and desktop Chrome: the install icon in the address bar.
              </span>
            )}
          </span>
          {installed ? null : (
            <button type="button" className="btn btn-ghost shrink-0" onClick={markInstalled}>
              Done
            </button>
          )}
        </li>
      </ol>
    </Card>
  );
}

/** A tick that draws itself in (`pathLength`) when it flips to done. Reduced: a fade. Off: instant. */
function Tick({ done }: { done: boolean }) {
  const level = motionLevel();
  const duration = level === "off" ? 0 : dur.emphasis();
  return (
    <span className="relative grid size-6 shrink-0 place-items-center">
      <span aria-hidden className={`absolute inset-0 rounded-full border ${done ? "border-accent bg-accent-soft" : "border-border-strong"}`} />
      <svg aria-hidden viewBox="0 0 24 24" className="relative size-4 text-accent" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
        <motion.path
          d="M5 12.5l4.5 4.5L19 7"
          initial={false}
          animate={level === "full" ? { pathLength: done ? 1 : 0, opacity: done ? 1 : 0 } : { pathLength: 1, opacity: done ? 1 : 0 }}
          transition={{ duration, ease: [...easeEnter] }}
        />
      </svg>
      <span className="sr-only">{done ? "Done" : "To do"}</span>
    </span>
  );
}
