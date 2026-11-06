import { Table2 } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { motionLevel } from "../../lib/motion.ts";
import { PREPARE_PRINT, setPrintMode } from "../../lib/print.ts";
import { useMediaQuery } from "../../lib/useMediaQuery.ts";
import { baseOption, type ChartTokens, readTokens } from "./theme.ts";

type EChartsModule = typeof import("./echarts.ts").default;
type Instance = ReturnType<EChartsModule["init"]>;

let loader: Promise<EChartsModule> | null = null;
/** ECharts loads once, on the first chart that scrolls into view. */
function loadECharts(): Promise<EChartsModule> {
  loader ??= import("./echarts.ts").then((m) => m.default);
  return loader;
}

export interface TableData {
  columns: string[];
  rows: (string | number)[][];
}

export type OptionBuilder = (t: ChartTokens, ctx: { phone: boolean }) => Record<string, unknown>;

/**
 * The one chart wrapper. Every chart has a one-line text summary and a "View data table" toggle
 * (Accessibility); shows a skeleton until ECharts is loaded and the chart is on screen; draws in on first
 * view; morphs on data change (same series ids, merged, never re-created); and turns animation off
 * under Reduced or Off motion.
 */
export function Chart({
  option,
  summary,
  table,
  height = 240,
  label,
  dim = false,
  className = "",
  footer,
}: {
  option: OptionBuilder;
  summary: string;
  table?: TableData;
  height?: number;
  label: string;
  dim?: boolean;
  className?: string;
  footer?: ReactNode;
}) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<Instance | null>(null);
  const [ready, setReady] = useState(false);
  const [visible, setVisible] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const phone = useMediaQuery("(max-width: 599px)");
  const touch = useMediaQuery("(pointer: coarse)");
  const tableId = useId();

  // Only start once the chart is near the viewport: that's when the draw-in should play.
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "120px" },
    );
    io.observe(el);
    const wake = () => setVisible(true); // Save as PDF: every chart draws, not only the ones scrolled to
    window.addEventListener(PREPARE_PRINT, wake);
    return () => {
      io.disconnect();
      window.removeEventListener(PREPARE_PRINT, wake);
    };
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let ro: ResizeObserver | null = null;
    let outside: ((e: PointerEvent) => void) | null = null;
    void loadECharts().then((echarts) => {
      if (cancelled || !host.current) return;
      const instance = echarts.init(host.current, undefined, { renderer: "canvas", devicePixelRatio: window.devicePixelRatio || 1 });
      chart.current = instance;
      ro = new ResizeObserver(() => instance.resize());
      ro.observe(host.current);
      // Touch: a pinned tooltip closes on a tap on empty chart space or anywhere outside the chart.
      instance.getZr().on("click", (e: { target?: unknown }) => {
        if (!e.target) instance.dispatchAction({ type: "hideTip" });
      });
      outside = (e: PointerEvent) => {
        if (host.current && !host.current.contains(e.target as Node)) instance.dispatchAction({ type: "hideTip" });
      };
      document.addEventListener("pointerdown", outside);
      setReady(true);
    });
    return () => {
      cancelled = true;
      ro?.disconnect();
      if (outside) document.removeEventListener("pointerdown", outside);
      chart.current?.dispose();
      chart.current = null;
      setReady(false);
    };
  }, [visible]);

  // Draw, then morph: later options merge into the same series (by id), so bars resize and lines bend.
  useEffect(() => {
    const instance = chart.current;
    if (!ready || !instance) return;
    const t = readTokens();
    const built = option(t, { phone });
    instance.setOption({ ...baseOption(t, motionLevel(), touch), ...built } as Parameters<Instance["setOption"]>[0], { replaceMerge: ["series", "xAxis", "yAxis", "visualMap"], lazyUpdate: true });
  }, [ready, option, phone, touch]);

  // Save as PDF: redraw with the light print tokens, without animation, then back again.
  useEffect(() => {
    if (!ready) return;
    const redraw = (printing: boolean) => {
      const instance = chart.current;
      if (!instance) return;
      const t = readTokens();
      const base = printing ? baseOption(t, "off", false) : baseOption(t, motionLevel(), touch);
      instance.setOption({ ...base, ...option(t, { phone }) } as Parameters<Instance["setOption"]>[0], { replaceMerge: ["series", "xAxis", "yAxis", "visualMap"] });
    };
    const before = () => {
      setPrintMode(true);
      resizeChart();
      redraw(true);
    };
    const after = () => {
      setPrintMode(false);
      resizeChart();
      redraw(false);
    };
    const resizeChart = () => chart.current?.resize();
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, [ready, option, phone, touch]);

  return (
    <figure className={`m-0 flex min-w-0 flex-col gap-2 ${className}`}>
      <div className="relative" style={{ height }}>
        {!ready ? <div className="skeleton absolute inset-0" role="status" aria-label={`Loading ${label}`} /> : null}
        <div
          ref={host}
          role="img"
          aria-label={`${label}. ${summary}`}
          className={`absolute inset-0 transition-opacity duration-(--dur-standard) ${dim ? "opacity-50" : "opacity-100"}`}
        />
      </div>
      <figcaption className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <p className="num min-w-0 flex-1 text-label text-muted">{summary}</p>
        {table ? (
          <button
            type="button"
            className="-my-3 inline-flex min-h-11 items-center gap-1.5 rounded-panel px-2 text-label text-muted hover:text-text"
            aria-expanded={showTable}
            aria-controls={tableId}
            onClick={() => setShowTable((v) => !v)}
          >
            <Table2 aria-hidden className="size-4" strokeWidth={1.75} />
            {showTable ? "Hide data table" : "View data table"}
          </button>
        ) : null}
      </figcaption>
      {footer}
      {table && showTable ? <DataTable id={tableId} label={label} table={table} /> : null}
    </figure>
  );
}

export function DataTable({ id, label, table }: { id?: string; label: string; table: TableData }) {
  return (
    <div id={id} className="max-h-72 overflow-auto rounded-panel border border-border" tabIndex={0} role="region" aria-label={`${label}: data table`}>
      <table className="num w-full border-collapse text-left text-label">
        <caption className="sr-only">{label}: data</caption>
        <thead className="sticky top-0 bg-surface-2 text-muted">
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={`px-3 py-2 font-medium ${i === 0 ? "sticky left-0 bg-surface-2" : ""}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r} className="border-t border-border">
              {row.map((cell, i) =>
                i === 0 ? (
                  <th key={i} scope="row" className="sticky left-0 bg-surface-1 px-3 py-1.5 font-normal">
                    {cell}
                  </th>
                ) : (
                  <td key={i} className="px-3 py-1.5">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Placeholder in the shape of a chart (card-level loading). */
export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Loading chart">
      <div className="skeleton w-full" style={{ height }} />
      <div className="skeleton h-3 w-2/3" />
    </div>
  );
}
