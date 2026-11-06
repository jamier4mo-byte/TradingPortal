import { ImageOff, Tag } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Chip, EmptyState, OwnerChip } from "../../../components/ui/index.ts";
import { ChartEmpty } from "../../../components/ui/Illustrations.tsx";
import { fmtDuration, fmtPnl, fmtR, fmtUkDate, fmtUkTime, hasReason, slotShot, type Trade } from "../../../lib/journal.ts";
import { useDevice } from "../../../lib/useMediaQuery.ts";
import { OutcomeChip, SideChip } from "./OutcomeChip.tsx";

function RulesFollowed({ t }: { t: Trade }) {
  const entries = Object.values(t.rules_followed ?? {});
  if (!entries.length) return <span className="text-label text-muted">—</span>;
  const kept = entries.filter(Boolean).length;
  return (
    <span className={`num text-label ${kept === entries.length ? "" : "text-muted"}`} aria-label={`${kept} of ${entries.length} rules followed`}>
      {kept}/{entries.length}
    </span>
  );
}

function MissingShots({ t }: { t: Trade }) {
  const missing = (["entry", "exit"] as const).filter((s) => !slotShot(t, s));
  if (!missing.length) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-pill border border-border-strong px-2 py-0.5 text-label text-muted" title={`Missing ${missing.join(" and ")} screenshot`}>
      <ImageOff aria-hidden className="size-3" />
      {missing.length === 2 ? "No shots" : `No ${missing[0]}`}
    </span>
  );
}

/** Desktop: a table. Phone: cards. Backtest rows add outcome, P&L and rules followed. */
export function TradeList({ trades, strategyId, mode, emptyTitle, emptyText, emptyAction, showOwner = false }: {
  trades: Trade[];
  strategyId: number;
  mode: "ideal" | "backtest" | "missed";
  emptyTitle: string;
  emptyText?: string;
  emptyAction?: React.ReactNode;
  showOwner?: boolean;
}) {
  const device = useDevice();
  const navigate = useNavigate();
  if (!trades.length) return <EmptyState illustration={<ChartEmpty />} title={emptyTitle} text={emptyText} action={emptyAction} />;
  const href = (t: Trade) => `/journal/strategies/${strategyId}/trades/${t.id}`;
  const backtest = mode === "backtest";

  if (device !== "desktop") {
    return (
      <ul className="flex flex-col gap-2" aria-label="Trades">
        {trades.map((t) => (
          <li key={t.id}>
            <Link to={href(t)} className="flex min-h-11 flex-col gap-2 rounded-panel border border-border bg-surface-2 p-3 hover:border-border-strong">
              <div className="flex items-center gap-2">
                <span className="font-mono text-body">{t.instrument}</span>
                <SideChip side={t.side} />
                {backtest ? <OutcomeChip outcome={t.outcome} /> : null}
                <span className={`num ml-auto text-body font-medium ${(t.r_multiple ?? 0) > 0 ? "text-win" : (t.r_multiple ?? 0) < 0 ? "text-loss" : ""}`}>{fmtR(t.r_multiple)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-label text-muted">
                <span className="num">{fmtUkDate(t.opened_at)} · {fmtUkTime(t.opened_at)}</span>
                <span>{t.session_label}</span>
                {t.entry_model ? <span>{t.entry_model}</span> : null}
                {backtest ? <span className="num">{fmtPnl(t.pnl)}</span> : null}
                <MissingShots t={t} />
                {!hasReason(t) ? <span>No reason yet</span> : null}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[880px] border-separate border-spacing-0 whitespace-nowrap text-body">
        <thead>
          <tr className="text-left text-label text-muted">
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Date</th>
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Time</th>
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Instrument</th>
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Side</th>
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Session</th>
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Model</th>
            <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">SL</th>
            <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">TP</th>
            <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">Held</th>
            <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">R</th>
            {backtest ? <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">P&amp;L</th> : null}
            {backtest ? <th scope="col" className="border-b border-border px-2 py-2 font-normal">Outcome</th> : null}
            {backtest ? <th scope="col" className="border-b border-border px-2 py-2 text-right font-normal">Rules</th> : null}
            <th scope="col" className="border-b border-border px-2 py-2 font-normal">Shots</th>
            {showOwner ? <th scope="col" className="border-b border-border px-2 py-2 font-normal">By</th> : null}
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} className="cursor-pointer hover:bg-surface-2" onClick={() => navigate(href(t))}>
              <td className="num border-b border-border px-2 py-0">
                <Link to={href(t)} onClick={(e) => e.stopPropagation()} className="flex min-h-11 items-center" aria-label={`Open trade on ${fmtUkDate(t.opened_at)} ${fmtUkTime(t.opened_at)} ${t.instrument}`}>
                  {fmtUkDate(t.opened_at)}
                </Link>
              </td>
              <td className="num border-b border-border px-2 py-2.5 text-muted">{fmtUkTime(t.opened_at)}</td>
              <td className="border-b border-border px-2 py-2.5 font-mono">{t.instrument}</td>
              <td className="border-b border-border px-2 py-2.5"><SideChip side={t.side} /></td>
              <td className="border-b border-border px-2 py-2.5 text-muted">{t.session_label}</td>
              <td className="border-b border-border px-2 py-2.5 text-muted">{t.entry_model ?? "—"}</td>
              <td className="num border-b border-border px-2 py-2.5 text-right">{t.sl_distance ?? "—"}</td>
              <td className="num border-b border-border px-2 py-2.5 text-right">{t.tp_distance ?? "—"}{t.tp_r ? <span className="text-muted"> · {t.tp_r.toFixed(1)}R</span> : null}</td>
              <td className="num border-b border-border px-2 py-2.5 text-right text-muted">{fmtDuration(t.duration_seconds)}</td>
              <td className={`num border-b border-border px-2 py-2.5 text-right font-medium ${(t.r_multiple ?? 0) > 0 ? "text-win" : (t.r_multiple ?? 0) < 0 ? "text-loss" : ""}`}>{fmtR(t.r_multiple)}</td>
              {backtest ? <td className={`num border-b border-border px-2 py-2.5 text-right ${(t.pnl ?? 0) > 0 ? "text-win" : (t.pnl ?? 0) < 0 ? "text-loss" : ""}`}>{fmtPnl(t.pnl)}</td> : null}
              {backtest ? <td className="border-b border-border px-2 py-2.5"><OutcomeChip outcome={t.outcome} /></td> : null}
              {backtest ? <td className="border-b border-border px-2 py-2.5 text-right"><RulesFollowed t={t} /></td> : null}
              <td className="border-b border-border px-2 py-2.5">
                <span className="flex items-center gap-1.5">
                  <MissingShots t={t} />
                  {t.tags.length ? <Chip><Tag aria-hidden className="size-3" /> <span className="num">{t.tags.length}</span></Chip> : null}
                </span>
              </td>
              {showOwner ? <td className="border-b border-border px-2 py-2.5"><OwnerChip name={t.owner.display_name} colourIndex={t.owner.colour_index} compact /></td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
