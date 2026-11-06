import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useState } from "react";

import Card from "../../../components/Card.tsx";
import { CountUp } from "../../../components/ui/CountUp.tsx";
import { PillToggle } from "../../../components/ui/index.ts";
import type { CompareBlock, CompareRow } from "../../../lib/analytics.ts";
import { fmtR } from "../../../lib/journal.ts";

const BY = [
  { value: "by_hour" as const, label: "Entry hour" },
  { value: "by_entry_model" as const, label: "Model" },
  { value: "by_session" as const, label: "Session" },
  { value: "by_weekday" as const, label: "Day" },
];

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

/** The backtest set against the ideal profile: how much of the ideal R is captured, and what holds up. */
export function CompareView({ block, dim }: { block: CompareBlock; dim: boolean }) {
  const [by, setBy] = useState<(typeof BY)[number]["value"]>("by_hour");
  const rows = block[by].filter((r) => r.ideal_n || r.backtest_n);
  const maxShare = Math.max(0.01, ...rows.map((r) => r.ideal_share));
  const maxAbsR = Math.max(0.5, ...rows.map((r) => Math.abs(r.backtest_avg_r ?? 0)));
  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-(--dur-standard) laptop:gap-6 ${dim ? "opacity-60" : ""}`}>
      <div className="grid grid-cols-2 gap-2 laptop:grid-cols-4">
        <Capture label="Winners capture" hint="Backtest average win ÷ ideal average R" value={block.capture_winners} />
        <Capture label="Per trade overall" hint="Backtest average R (losses included) ÷ ideal average R" value={block.capture_all} />
        <Pair label="Average R" ideal={fmtR(block.ideal_avg_r)} backtest={fmtR(block.backtest_avg_win_r)} backtestLabel="bt wins" />
        <Pair label="Average stop" ideal={block.ideal_avg_sl === null ? "—" : block.ideal_avg_sl.toFixed(1)} backtest={block.backtest_avg_sl === null ? "—" : block.backtest_avg_sl.toFixed(1)} backtestLabel="backtest" />
      </div>

      <Card title="What holds up" subtitle="Where ideal winners came from, and how the backtest did there. Holds = average R above 0 on 3+ trades." controls={<PillToggle size="sm" value={by} onChange={setBy} options={BY} label="Compare by" />}>
        {rows.length ? (
          <>
          <ul className="flex flex-col gap-2 tablet:hidden" data-testid="compare-cards">
            {rows.map((r) => (
              <CompareCard key={r.key} r={r} />
            ))}
          </ul>
          <div className="hidden overflow-x-auto tablet:block" tabIndex={0} role="region" aria-label="Comparison table">
            <table className="num w-full min-w-[520px] border-collapse text-left text-body" data-testid="compare-table">
              <caption className="sr-only">Ideal share and backtest results by {BY.find((b) => b.value === by)?.label.toLowerCase()}</caption>
              <thead className="text-label text-muted">
                <tr>
                  <th scope="col" className="sticky left-0 bg-surface-1 py-2 pr-3 font-medium">
                    {BY.find((b) => b.value === by)?.label}
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Ideal winners
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Backtest avg R
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Win rate
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Verdict
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <CompareLine key={r.key} r={r} maxShare={maxShare} maxAbsR={maxAbsR} />
                ))}
              </tbody>
            </table>
          </div>
          </>
        ) : (
          <p className="text-body text-muted">No trades to compare in this filter.</p>
        )}
      </Card>
    </div>
  );
}

function Verdict({ holds }: { holds: CompareRow["holds"] }) {
  if (holds === "holds")
    return (
      <span className="inline-flex items-center gap-1">
        <ArrowUpRight aria-hidden className="size-4 text-win" /> Holds
      </span>
    );
  if (holds === "fails")
    return (
      <span className="inline-flex items-center gap-1">
        <ArrowDownRight aria-hidden className="size-4 text-loss" /> Fails
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-muted">
      <Minus aria-hidden className="size-4" /> Too few
    </span>
  );
}

/** Phone: one card per row instead of a table that scrolls sideways. */
function CompareCard({ r }: { r: CompareRow }) {
  const avg = r.backtest_avg_r;
  return (
    <li className="num flex flex-col gap-1 rounded-panel border border-border bg-surface-2 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body font-medium">{r.key}</span>
        <Verdict holds={r.holds} />
      </div>
      <p className="text-label text-muted">
        Ideal: {r.ideal_n} {r.ideal_n === 1 ? "winner" : "winners"} ({pct(r.ideal_share)}) · Backtest:{" "}
        <span className={avg === null ? "" : avg > 0 ? "text-win" : avg < 0 ? "text-loss" : ""}>{fmtR(avg)}</span> avg, {pct(r.backtest_win_rate)} win, n={r.backtest_n}
      </p>
    </li>
  );
}

function CompareLine({ r, maxShare, maxAbsR }: { r: CompareRow; maxShare: number; maxAbsR: number }) {
  const avg = r.backtest_avg_r;
  const width = avg === null ? 0 : (Math.abs(avg) / maxAbsR) * 50;
  return (
    <tr className="border-t border-border">
      <th scope="row" className="sticky left-0 bg-surface-1 py-2 pr-3 font-normal">
        {r.key}
      </th>
      <td className="py-2 pr-3">
        <div className="flex items-center gap-2">
          <span aria-hidden className="h-2 rounded-pill bg-accent" style={{ width: `${Math.max(2, (r.ideal_share / maxShare) * 72)}px` }} />
          <span>
            {r.ideal_n} <span className="text-label text-muted">({pct(r.ideal_share)})</span>
          </span>
        </div>
      </td>
      <td className="py-2 pr-3">
        <div className="flex items-center gap-2">
          <span aria-hidden className="relative h-2 w-24 shrink-0 rounded-pill bg-surface-2">
            <span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
            {avg !== null ? <span className={`absolute inset-y-0 rounded-pill ${avg >= 0 ? "left-1/2 bg-win" : "right-1/2 bg-loss"}`} style={{ width: `${width}%` }} /> : null}
          </span>
          <span className={avg === null ? "text-muted" : avg > 0 ? "text-win" : avg < 0 ? "text-loss" : ""}>{fmtR(avg)}</span>
          <span className="text-label text-muted">n={r.backtest_n}</span>
        </div>
      </td>
      <td className="py-2 pr-3">{pct(r.backtest_win_rate)}</td>
      <td className="py-2">
        <Verdict holds={r.holds} />
      </td>
    </tr>
  );
}

function Capture({ label, hint, value }: { label: string; hint: string; value: number | null }) {
  return (
    <div className="rounded-panel border border-border bg-surface-2 p-3">
      <p className="text-label text-muted">{label}</p>
      <p className="num mt-0.5 text-heading leading-none font-semibold">
        <CountUp value={value} format={(v) => (v === null ? "—" : `${Math.round(v * 100)}%`)} />
      </p>
      <p className="mt-1 text-label text-muted">{hint}</p>
    </div>
  );
}

function Pair({ label, ideal, backtest, backtestLabel }: { label: string; ideal: string; backtest: string; backtestLabel: string }) {
  return (
    <div className="rounded-panel border border-border bg-surface-2 p-3">
      <p className="text-label text-muted">{label}</p>
      <p className="num mt-1 text-title font-semibold">
        {ideal} <span className="text-label font-normal text-muted">ideal</span>
      </p>
      <p className="num text-title font-semibold">
        {backtest} <span className="text-label font-normal text-muted">{backtestLabel}</span>
      </p>
    </div>
  );
}
