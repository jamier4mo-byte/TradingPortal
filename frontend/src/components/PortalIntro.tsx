import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";

import { introDone } from "../lib/intro.ts";
import { dur, easeEnter, easeLeave } from "../lib/motion.ts";

// Ten deterministic candles (open, close, high, low as fractions of the height; y grows downwards) and the
// price line through their closes. The line rises, as a journal should, but it's decoration: candles use the
// accent and the subtle grey, never the reserved win/loss colours.
const CANDLES: [number, number, number, number][] = [
  [0.7, 0.6, 0.74, 0.56],
  [0.6, 0.64, 0.68, 0.55],
  [0.64, 0.52, 0.66, 0.48],
  [0.52, 0.44, 0.56, 0.4],
  [0.44, 0.5, 0.54, 0.42],
  [0.5, 0.38, 0.52, 0.34],
  [0.38, 0.3, 0.42, 0.26],
  [0.3, 0.36, 0.4, 0.28],
  [0.36, 0.26, 0.38, 0.22],
  [0.26, 0.2, 0.3, 0.16],
];
const W = 200;
const H = 80;
const STEP = 20;
const LINE = CANDLES.map(([, c], i) => `${i === 0 ? "M" : "L"}${10 + i * STEP + 4} ${(c * H).toFixed(1)}`).join(" ");

/** Portal intro (Loading screens → Portal intro): a full-screen layer in which the logo mark draws in as a
 * price line and candles, then the T tile resolves on top, and the whole thing dissolves into the Hub,
 * which is already mounted underneath. About 1 s (`--dur-intro`), then a --dur-standard fade. Dismiss by tap
 * or Esc. Only mounted in Full motion (see lib/intro.ts), so there is no Reduced variant here. */
export default function PortalIntro({ onDone }: { onDone: () => void }) {
  const intro = dur.intro();
  const [leaving, setLeaving] = useState(false);
  const leave = useCallback(() => setLeaving(true), []);

  useEffect(() => {
    const timer = window.setTimeout(leave, intro * 1000);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") leave();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
    };
  }, [intro, leave]);

  return (
    <motion.div
      role="status"
      aria-live="polite"
      data-testid="portal-intro"
      className={`fixed inset-0 z-[60] grid place-items-center bg-bg ${leaving ? "pointer-events-none" : ""}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: leaving ? 0 : 1 }}
      transition={leaving ? { duration: dur.standard(), ease: [...easeLeave] } : { duration: dur.quick(), ease: [...easeEnter] }}
      onAnimationComplete={() => {
        if (leaving) {
          introDone();
          onDone();
        }
      }}
      onPointerDown={leave}
    >
      <div className="flex flex-col items-center gap-6 px-(--gutter-phone)">
        <div className="relative" style={{ width: W, height: H }}>
          <motion.svg
            viewBox={`0 0 ${W} ${H}`}
            width={W}
            height={H}
            aria-hidden
            className="overflow-visible"
            animate={{ opacity: [1, 1, 0.3] }}
            transition={{ duration: intro, times: [0, 0.55, 0.9], ease: "linear" }}
          >
            {CANDLES.map(([o, c, h, l], i) => {
              const x = 10 + i * STEP;
              const up = c < o;
              const top = Math.min(o, c) * H;
              const body = Math.max(2, Math.abs(o - c) * H);
              return (
                <motion.g
                  key={i}
                  className={up ? "text-accent" : "text-subtle"}
                  style={{ transformBox: "fill-box", transformOrigin: "50% 100%" }}
                  initial={{ opacity: 0, scaleY: 0.2 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  transition={{ duration: intro * 0.25, delay: intro * (0.08 + i * 0.05), ease: [...easeEnter] }}
                >
                  <line x1={x + 4} x2={x + 4} y1={h * H} y2={l * H} stroke="currentColor" strokeWidth={1.25} />
                  <rect x={x} y={top} width={8} height={body} rx={1} fill="currentColor" />
                </motion.g>
              );
            })}
            <motion.path
              d={LINE}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-data-2"
              initial={{ pathLength: 0, opacity: 1 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: intro * 0.55, ease: [...easeEnter] }}
            />
          </motion.svg>
          <motion.img
            src="/brand/t-tile.png"
            alt=""
            aria-hidden
            width={64}
            height={64}
            className="absolute left-1/2 top-1/2 size-16 -translate-x-1/2 -translate-y-1/2"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: intro * 0.3, delay: intro * 0.55, ease: [...easeEnter] }}
          />
        </div>
        <p className="text-body text-muted">Opening the portal</p>
      </div>
    </motion.div>
  );
}
