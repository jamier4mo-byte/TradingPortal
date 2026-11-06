/** Chart theme built at runtime from the CSS tokens in index.css. No hex values live here. */
import type { MotionLevel } from "../../lib/motion.ts";

export interface ChartTokens {
  text: string;
  muted: string;
  subtle: string;
  grid: string;
  axis: string;
  series1: string;
  series2: string;
  win: string;
  loss: string;
  breakeven: string;
  surface1: string;
  surface2: string;
  border: string;
  borderStrong: string;
  accentSoft: string;
  owners: string[];
  font: string;
  mono: string;
}

export function readTokens(el: Element = document.documentElement): ChartTokens {
  const cs = getComputedStyle(el);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    text: v("--color-text"),
    muted: v("--color-muted"),
    subtle: v("--color-subtle"),
    grid: v("--chart-grid"),
    axis: v("--chart-axis"),
    series1: v("--chart-series-1"),
    series2: v("--chart-series-2"),
    win: v("--color-win"),
    loss: v("--color-loss"),
    breakeven: v("--color-breakeven"),
    surface1: v("--color-surface-1"),
    surface2: v("--color-surface-2"),
    border: v("--color-border"),
    borderStrong: v("--color-border-strong"),
    accentSoft: v("--color-accent-soft"),
    owners: Array.from({ length: 8 }, (_, i) => v(`--color-owner-${i}`)),
    font: v("--font-sans"),
    mono: v("--font-mono"),
  };
}

/** Escape anything user-typed (entry models, tags, names) before it goes into a tooltip's HTML. */
export function esc(text: unknown): string {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

/** Tokens → the base option every chart starts from: thin axes, faint grid, one tooltip style, motion. */
export function baseOption(t: ChartTokens, level: MotionLevel, touch: boolean) {
  const animate = level === "full";
  return {
    animation: animate,
    animationDuration: animate ? 600 : 0,
    animationEasing: "cubicOut",
    animationDurationUpdate: animate ? 500 : 0,
    animationEasingUpdate: "cubicInOut",
    textStyle: { fontFamily: t.font, color: t.muted, fontSize: 12 },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      show: true,
      confine: true,
      // Touch: press and hold drags the crosshair; a tap pins the tooltip until the next tap.
      triggerOn: touch ? "mousemove|click" : "mousemove",
      alwaysShowContent: touch,
      backgroundColor: t.surface2,
      borderColor: t.borderStrong,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: t.text, fontFamily: t.font, fontSize: 12 },
      extraCssText: "border-radius:10px;box-shadow:none;",
      transitionDuration: animate ? 0.15 : 0,
    },
  };
}

export function valueAxis(t: ChartTokens, extra: Record<string, unknown> = {}) {
  return {
    type: "value",
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: t.grid, width: 1 } },
    axisLabel: { color: t.muted, fontFamily: t.font, fontSize: 11 },
    ...extra,
  };
}

export function categoryAxis(t: ChartTokens, data: string[], extra: Record<string, unknown> = {}) {
  return {
    type: "category",
    data,
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.muted, fontFamily: t.font, fontSize: 11, hideOverlap: true },
    splitLine: { show: false },
    ...extra,
  };
}

/** The tooltip row: a short line key in the series colour, the value strong, the label quiet. */
export function tipRow(colour: string, label: string, value: string): string {
  return `<div style="display:flex;align-items:center;gap:8px;line-height:18px"><span style="width:10px;height:2px;border-radius:1px;background:${colour}"></span><b style="font-variant-numeric:tabular-nums">${esc(value)}</b><span style="opacity:.75">${esc(label)}</span></div>`;
}

export function tipTitle(text: string): string {
  return `<div style="opacity:.75;margin-bottom:4px;font-variant-numeric:tabular-nums">${esc(text)}</div>`;
}
