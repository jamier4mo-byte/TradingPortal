import Card from "../../../components/Card.tsx";
import type { AnalyticsResult, AroundNewsRow } from "../../../lib/analytics.ts";

const FIXED = ["Inside news window", "Outside", "No news data"];

/** Event types present in the answer, for the News event filter. */
export function newsTypesOf(data: AnalyticsResult | undefined): string[] {
  const rows = data?.backtest?.around_news ?? data?.ideal?.around_news ?? [];
  return rows.map((r) => r.key).filter((k) => !FIXED.includes(k));
}

function r(v: number | null): string {
  if (v === null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}R`;
}

/** Around news (3.6): does this strategy do better, worse or the same around news? */
export function AroundNewsCard({ rows, status, note }: { rows: AroundNewsRow[]; status: AnalyticsResult["news_status"]; note: string | null }) {
  const fixed = FIXED.map((k) => rows.find((x) => x.key === k)).filter((x): x is AroundNewsRow => !!x && x.trades > 0);
  const types = rows.filter((x) => !FIXED.includes(x.key) && x.trades > 0);
  return (
    <Card title="Around news" subtitle="Trades entered inside a news window vs outside, and by event">
      {status === "no_data" || rows.length === 0 ? (
        <p className="text-body text-muted">{note ?? "No news data: these trades fall outside the stored news history."}</p>
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 tablet:mx-0 tablet:px-0">
          <table className="w-full min-w-[30rem] text-body">
            <caption className="sr-only">Results inside and outside news windows</caption>
            <thead>
              <tr className="border-b border-border text-left text-label text-muted">
                <th scope="col" className="sticky left-0 bg-surface-1 py-2 pr-3 font-normal">Group</th>
                <th scope="col" className="py-2 pr-3 text-right font-normal">Trades</th>
                <th scope="col" className="py-2 pr-3 text-right font-normal">Win rate</th>
                <th scope="col" className="py-2 pr-3 text-right font-normal">Avg R</th>
                <th scope="col" className="py-2 text-right font-normal">Total R</th>
              </tr>
            </thead>
            <tbody>
              {[...fixed, ...types].map((row, i) => (
                <tr key={row.key} className={`border-b border-border last:border-0 ${i === fixed.length && types.length ? "border-t border-t-border-strong" : ""}`}>
                  <th scope="row" className={`sticky left-0 bg-surface-1 py-2 pr-3 text-left font-normal ${FIXED.includes(row.key) ? "" : "pl-3 text-muted"}`}>
                    {row.key}
                  </th>
                  <td className="num py-2 pr-3 text-right">{row.trades}</td>
                  <td className="num py-2 pr-3 text-right">{row.win_rate === null ? "—" : `${Math.round(row.win_rate * 100)}%`}</td>
                  <td className="num py-2 pr-3 text-right">{r(row.avg_r)}</td>
                  <td className="num py-2 text-right">{r(row.total_r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {status === "partial" && note ? <p className="mt-2 text-label text-muted">{note}</p> : null}
        </div>
      )}
    </Card>
  );
}
