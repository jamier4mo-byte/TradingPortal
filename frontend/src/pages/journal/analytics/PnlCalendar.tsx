import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import type { CalendarDay } from "../../../lib/analytics.ts";
import { fmtPnl, fmtR } from "../../../lib/journal.ts";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monthLabel(key: string) {
  const [y, m] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, 15)));
}

function compactUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  return `${sign}$${a >= 1000 ? `${(a / 1000).toFixed(1)}k` : Math.round(a)}`;
}

/** Phone cells are ~40px wide: sign plus a short number, no unit (the header says $ or R). */
function shortValue(v: number | null | undefined, unit: "usd" | "r"): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  if (unit === "r") return `${sign}${a >= 10 ? Math.round(a) : a.toFixed(1)}`;
  return `${sign}${a >= 1000 ? `${(a / 1000).toFixed(a >= 10000 ? 0 : 1)}k` : Math.round(a)}`;
}

const tint = (v: number | null | undefined) => (v === null || v === undefined ? "" : v > 0 ? "border-win/40 bg-win/10" : v < 0 ? "border-loss/40 bg-loss/10" : "border-border bg-surface-2");
const ink = (v: number | null | undefined) => (v === null || v === undefined ? "" : v > 0 ? "text-win" : v < 0 ? "text-loss" : "text-breakeven");

/** Daily P&L by the UK date of the open (FX Replay's calendar uses the open). Colour plus a sign, never colour alone. */
export function PnlCalendar({ days, unit }: { days: CalendarDay[]; unit: "usd" | "r" }) {
  const byDate = useMemo(() => new Map(days.map((d) => [d.date, d])), [days]);
  const months = useMemo(() => Array.from(new Set(days.map((d) => d.date.slice(0, 7)))).sort(), [days]);
  const [picked, setPicked] = useState<string | null>(null);
  const month = picked && months.includes(picked) ? picked : months[months.length - 1];
  if (!month) return <p className="text-body text-muted">No trading days yet.</p>;

  const [y, m] = month.split("-").map(Number);
  const lead = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7; // Monday first
  const count = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const cells: (string | null)[] = [...Array<null>(lead).fill(null), ...Array.from({ length: count }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, w) => cells.slice(w * 7, w * 7 + 7));
  const value = (d: CalendarDay | undefined) => (d ? (unit === "usd" ? d.pnl : d.r) : null);
  const fmt = (v: number | null) => (unit === "usd" ? fmtPnl(v) : fmtR(v));
  const inMonth = days.filter((d) => d.date.startsWith(month));
  const total = inMonth.reduce((a, d) => a + (value(d) ?? 0), 0);
  const trades = inMonth.reduce((a, d) => a + d.n, 0);
  const idx = months.indexOf(month);

  return (
    <div className="flex flex-col gap-3" data-testid="pnl-calendar">
      <div className="flex items-center gap-2">
        <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Previous month with trades" disabled={idx <= 0} onClick={() => setPicked(months[idx - 1])}>
          <ChevronLeft aria-hidden className="size-4" />
        </button>
        <p className="min-w-0 flex-1 text-center text-body font-medium" aria-live="polite">
          {monthLabel(month)}
          <span className="num ml-2 font-normal text-muted">
            {trades} {trades === 1 ? "trade" : "trades"} · <span className={ink(total)}>{fmt(total)}</span>
          </span>
        </p>
        <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Next month with trades" disabled={idx >= months.length - 1} onClick={() => setPicked(months[idx + 1])}>
          <ChevronRight aria-hidden className="size-4" />
        </button>
      </div>
      <table className="num w-full table-fixed border-separate border-spacing-1 text-label">
        <caption className="sr-only">
          Daily {unit === "usd" ? "P&L" : "R"} for {monthLabel(month)}
        </caption>
        <thead>
          <tr>
            {DOW.map((d) => (
              <th key={d} scope="col" className="pb-1 font-normal text-muted">
                <abbr title={d} className="no-underline tablet:hidden">
                  {d[0]}
                </abbr>
                <span className="hidden tablet:inline">{d}</span>
              </th>
            ))}
            <th scope="col" className="hidden pb-1 font-normal text-muted laptop:table-cell">
              Week
            </th>
          </tr>
        </thead>
        <tbody>
          {weeks.map((week, w) => {
            const weekTotal = week.reduce((a, date) => a + (date ? (value(byDate.get(date)) ?? 0) : 0), 0);
            const weekTrades = week.reduce((a, date) => a + (date ? (byDate.get(date)?.n ?? 0) : 0), 0);
            return (
              <tr key={w}>
                {week.map((date, i) => {
                  if (!date) return <td key={i} aria-hidden />;
                  const d = byDate.get(date);
                  const v = value(d);
                  return (
                    <td key={i} className={`h-14 rounded-panel border align-top tablet:h-16 ${d ? tint(v) : "border-transparent"}`}>
                      <div className="flex h-full flex-col justify-between p-1 tablet:p-1.5">
                        <span className="text-muted">{Number(date.slice(8))}</span>
                        {d ? (
                          <span className="flex flex-col leading-tight">
                            <span className={`hidden truncate font-medium tablet:block ${ink(v)}`}>{unit === "usd" ? compactUsd(v) : fmtR(v)}</span>
                            <span aria-hidden className={`font-medium tablet:hidden ${ink(v)}`}>{shortValue(v, unit)}</span>
                            <span className="hidden text-muted tablet:inline">{d.n}×</span>
                            <span className="sr-only">
                              {fmt(v)} from {d.n} {d.n === 1 ? "trade" : "trades"}
                            </span>
                          </span>
                        ) : null}
                      </div>
                    </td>
                  );
                })}
                <td className="hidden h-14 align-middle laptop:table-cell">{weekTrades ? <span className={`block text-center font-medium ${ink(weekTotal)}`}>{fmt(weekTotal)}</span> : null}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
