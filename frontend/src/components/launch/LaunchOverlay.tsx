import { AnimatePresence, motion } from "motion/react";

import { dur, easeEnter, easeLeave, motionLevel } from "../../lib/motion.ts";
import { type Tool, TOOLS } from "./useLaunch.ts";

/** Full-screen layer over the content (the shell stays visible above it). `role="status"` so the
 * "Opening …" text is announced. Inline SVG and `motion` only (F18): no Lottie, nothing heavy. */
export function LaunchOverlay({ tool }: { tool: Tool | null }) {
  const level = motionLevel();
  return (
    <AnimatePresence>
      {tool ? (
        <motion.div
          key={tool}
          role="status"
          aria-live="polite"
          className="fixed inset-0 z-[5] grid place-items-center bg-bg/95"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: level === "off" ? 0 : dur.standard(), ease: [...easeLeave] } }}
          transition={{ duration: level === "off" ? 0 : dur.standard(), ease: [...easeEnter] }}
        >
          <div className="flex flex-col items-center gap-6 px-(--gutter-phone)">
            {level === "full" ? tool === "journal" ? <RewindLoader /> : <RadarLoader /> : null}
            <p className="text-body text-muted">Opening {TOOLS[tool].name}…</p>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

// Deterministic candles (open, close, high, low in 0–1 of the drawing height), 14 of them.
const CANDLES: [number, number, number, number][] = [
  [0.55, 0.42, 0.62, 0.38],
  [0.42, 0.5, 0.56, 0.4],
  [0.5, 0.36, 0.52, 0.3],
  [0.36, 0.3, 0.44, 0.26],
  [0.3, 0.46, 0.5, 0.28],
  [0.46, 0.52, 0.6, 0.44],
  [0.52, 0.4, 0.56, 0.34],
  [0.4, 0.33, 0.45, 0.3],
  [0.33, 0.44, 0.48, 0.3],
  [0.44, 0.58, 0.64, 0.42],
  [0.58, 0.5, 0.62, 0.46],
  [0.5, 0.38, 0.54, 0.36],
  [0.38, 0.28, 0.42, 0.24],
  [0.28, 0.34, 0.4, 0.22],
];
const W = 168;
const H = 72;
const STEP = 12;

/** Replay Journal: a rewind. Candles draw in right to left while a playhead sweeps back across them.
 * Candles use the accent (up) and the subtle grey (down), never the reserved win/loss colours: a loader is
 * decoration, and green/red mean profit and loss only. Loops while the chunk loads. */
function RewindLoader() {
  const cycle = dur.launch() * 2; // ~1.2 s per pass
  const n = CANDLES.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden className="overflow-visible">
      {CANDLES.map(([o, c, h, l], i) => {
        const x = 4 + i * STEP;
        const up = c < o; // y grows downwards: a lower close value is a higher price
        const top = Math.min(o, c) * H;
        const body = Math.max(2, Math.abs(o - c) * H);
        const start = ((n - 1 - i) / n) * 0.6; // rightmost first
        return (
          <motion.g
            key={i}
            className={up ? "text-accent" : "text-subtle"}
            style={{ transformBox: "fill-box", transformOrigin: "50% 50%" }}
            initial={{ opacity: 0, scaleY: 0.4 }}
            animate={{ opacity: [0, 1, 1, 0], scaleY: [0.4, 1, 1, 1] }}
            transition={{ duration: cycle, times: [start, Math.min(start + 0.12, 0.84), 0.86, 1], repeat: Infinity, ease: [...easeEnter] }}
          >
            <line x1={x + 3.5} x2={x + 3.5} y1={h * H} y2={l * H} stroke="currentColor" strokeWidth={1.25} />
            <rect x={x} y={top} width={7} height={body} rx={1} fill="currentColor" />
          </motion.g>
        );
      })}
      <motion.line
        x1={0}
        x2={0}
        y1={0}
        y2={H}
        stroke="currentColor"
        strokeWidth={1.5}
        className="text-accent"
        initial={{ x: W }}
        animate={{ x: [W, W, 0, 0] }}
        transition={{ duration: cycle, times: [0, 0.02, 0.62, 1], repeat: Infinity, ease: [...easeLeave] }}
      />
    </svg>
  );
}

/** News Room: a radar pulse. Rings expand and fade (scale + opacity) under a sweeping arm. */
function RadarLoader() {
  const cycle = dur.launch() * 2;
  return (
    <svg viewBox="-40 -40 80 80" width={96} height={96} aria-hidden className="text-news">
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i}
          r={34}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.25}
          initial={{ scale: 0.15, opacity: 0 }}
          animate={{ scale: [0.15, 1], opacity: [0.7, 0] }}
          transition={{ duration: cycle, delay: (i * cycle) / 3, repeat: Infinity, ease: [...easeEnter] }}
        />
      ))}
      <circle r={2} fill="currentColor" />
      <motion.line
        x1={0}
        y1={0}
        x2={0}
        y2={-34}
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        animate={{ rotate: 360 }}
        transition={{ duration: cycle, repeat: Infinity, ease: "linear" }} /* a constant sweep: linear on purpose */
      />
    </svg>
  );
}
