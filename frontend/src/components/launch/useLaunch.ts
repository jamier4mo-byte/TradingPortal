/** Launch islands (1.3, F14): the loader is the real loading screen. On click we start fetching the tool's
 * chunk and show the overlay; we navigate once both the chunk and a short minimum have passed, so the
 * loader never flickers and never outlasts the real load by more than the minimum.
 *
 * Minimum: ~600 ms (`--dur-launch`) the first time a tool is opened each UK day, ~250 ms after that.
 * Motion Off: navigate at once (the chunk is still prefetched). Reduced: the overlay is a plain fade. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { launchKey, remember, remembered } from "../../lib/hub.ts";
import { dur, motionLevel } from "../../lib/motion.ts";
import { ukISODate } from "../../lib/news.ts";

export type Tool = "journal" | "news";

export const TOOLS: Record<Tool, { name: string; to: string; load: () => Promise<unknown> }> = {
  journal: { name: "Replay Journal", to: "/journal", load: () => import("../../pages/journal/JournalIndex.tsx") },
  news: { name: "News Room", to: "/news", load: () => import("../../pages/news/NewsRoom.tsx") },
};

export function useLaunch() {
  const navigate = useNavigate();
  const [tool, setTool] = useState<Tool | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const launch = useCallback(
    (which: Tool) => {
      const meta = TOOLS[which];
      const key = launchKey(which, ukISODate(new Date()));
      const first = !remembered(key);
      remember(key);
      const chunk = meta.load().catch(() => undefined); // a failed prefetch still navigates; the route's Suspense retries
      if (motionLevel() === "off") {
        navigate(meta.to);
        return;
      }
      setTool(which);
      // Reduced motion shows only the text, so it never waits for the full loader minimum.
      const minimum = (first && motionLevel() === "full" ? dur.launch() : dur.standard()) * 1000;
      const timer = new Promise<void>((resolve) => setTimeout(resolve, minimum));
      void Promise.all([chunk, timer]).then(() => {
        if (alive.current) navigate(meta.to);
      });
    },
    [navigate],
  );

  return { tool, launch };
}
