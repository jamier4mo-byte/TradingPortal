import { useEffect, useRef } from "react";

import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";

/** Intraday sparkline. Inline SVG (no chart library on the Hub). When a point is added the line extends:
 * the path is drawn with a dash that grows to the new end instead of redrawing from nothing. Colour is
 * the first chart series, not win/loss: direction is carried by the change line next to it. */
export function PriceSparkline({
  values,
  width = 140,
  height = 40,
  label,
  className = "",
}: {
  values: number[];
  width?: number;
  height?: number;
  label: string;
  className?: string;
}) {
  const pathRef = useRef<SVGPathElement>(null);
  const prevLen = useRef<number | null>(null);
  const ok = values.length >= 2;
  const min = ok ? Math.min(...values) : 0;
  const max = ok ? Math.max(...values) : 1;
  const span = max - min || 1;
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (width - 4) + 2;
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6);
  const d = ok ? values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ") : "";

  useEffect(() => {
    const path = pathRef.current;
    if (!path || !ok) return;
    const total = path.getTotalLength();
    const from = prevLen.current;
    prevLen.current = total;
    if (from === null || from >= total || motionLevel() !== "full") return;
    // Extend smoothly from the previous end to the new one.
    path.animate(
      [
        { strokeDasharray: `${total}`, strokeDashoffset: `${total - from}` },
        { strokeDasharray: `${total}`, strokeDashoffset: "0" },
      ],
      { duration: dur.emphasis() * 1000, easing: `cubic-bezier(${easeEnter.join(",")})` },
    );
  }, [d, ok]);

  if (!ok) {
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: no intraday data yet`} className={`text-subtle ${className}`}>
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="currentColor" strokeDasharray="2 4" strokeWidth="1" />
      </svg>
    );
  }
  const first = values[0];
  const last = values[values.length - 1];
  const pct = first ? ((last - first) / first) * 100 : 0;
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${label}: ${values.length} points, ${pct >= 0 ? "up" : "down"} ${Math.abs(pct).toFixed(2)}% over the period`}
      className={`text-(--chart-series-1) ${className}`}
    >
      <path ref={pathRef} d={d} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r="2" fill="currentColor" />
    </svg>
  );
}
