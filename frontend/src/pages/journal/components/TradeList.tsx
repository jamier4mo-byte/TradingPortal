import { CheckCircle2, ImageOff, Tag } from "lucide-react";
import { useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Chip, EmptyState, OwnerChip } from "../../../components/ui/index.ts";
import { ChartEmpty } from "../../../components/ui/Illustrations.tsx";
import {
  fmtDuration,
  fmtPnl,
  fmtR,
  fmtUkDate,
  fmtUkTime,
  hasReason,
  isCompleted,
  LABELLED_SLOTS,
  SLOT_LABEL,
  slotShot,
  type Trade,
} from "../../../lib/journal.ts";
import { useDevice } from "../../../lib/useMediaQuery.ts";
import { vtName } from "../../../lib/vt.ts";
import { OutcomeChip, SideChip } from "./OutcomeChip.tsx";

function RulesFollowed({ t }: { t: Trade }) {
  const entries = Object.values(t.rules_followed ?? {});
  if (!entries.length) return <span className="text-label text-muted">—</span>;
  const kept = entries.filter(Boolean).length;
  return (
    <span
      className={`num text-label ${kept === entries.length ? "" : "text-muted"}`}
      aria-label={`${kept} of ${entries.length} rules followed`}
    >
      {kept}/{entries.length}
    </span>
  );
}

function MissingShots({ t }: { t: Trade }) {
  const missing = LABELLED_SLOTS.filter((s) => !slotShot(t, s));
  if (!missing.length) return null;
  const names = missing.map((s) => SLOT_LABEL[s]);
  return (
    <span
      className="inline-flex items-center gap-1 rounded-pill border border-border-strong px-2 py-0.5 text-label text-muted"
      title={`Missing ${names.join(", ")} screenshot`}
    >
      <ImageOff aria-hidden className="size-3" />
      {missing.length === LABELLED_SLOTS.length
        ? "No shots"
        : `No ${names.join(", ")}`}
    </span>
  );
}

function Completed({ t }: { t: Trade }) {
  if (!isCompleted(t)) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-pill border border-accent/60 px-2 py-0.5 text-label text-text">
      <CheckCircle2 aria-hidden className="size-3 text-accent" />
      Completed
    </span>
  );
}

/** Rows rendered before the list asks you to scroll (Devices → Speed on mobile: long lists load as you scroll). */
export const TRADE_PAGE = 40;

// The trade most recently opened from a list, so coming back morphs its heading into the right row. Only that
// row (and the row being clicked) carries a view-transition-name: one element per name, and no snapshot cost
// for the other rows.
let lastOpened: number | null = null;

/** "Showing 40 of 213" with a Show all button for keyboard users; the line is also the scroll sentinel. */
function ShowingLine({
  shown,
  total,
  onAll,
  sentinel,
}: {
  shown: number;
  total: number;
  onAll: () => void;
  sentinel: React.RefObject<HTMLDivElement | null>;
}) {
  if (total <= TRADE_PAGE) return null;
  return (
    <div
      ref={sentinel}
      className="mt-3 flex min-h-11 flex-wrap items-center justify-between gap-2 text-label text-muted"
      data-testid="trade-list-footer"
    >
      <p className="num" role="status">
        Showing {Math.min(shown, total)} of {total}
      </p>
      {shown < total ? (
        <button type="button" className="btn btn-ghost" onClick={onAll}>
          Show all
        </button>
      ) : null}
    </div>
  );
}

/** Desktop: a table. Phone: cards. Backtest rows add outcome, P&L and rules followed. The first 40 render
 * at once; 40 more are appended whenever the footer scrolls into view (`useInView`), or all on Show all. */
export function TradeList({
  trades,
  strategyId,
  mode,
  emptyTitle,
  emptyText,
  emptyAction,
  showOwner = false,
}: {
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
  const [shown, setShown] = useState(TRADE_PAGE);
  const [opening, setOpening] = useState<number | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const footerInView = useInView(sentinel, { margin: "0px 0px 200px 0px" });
  useEffect(() => {
    if (footerInView && shown < trades.length)
      setShown((n) => Math.min(trades.length, n + TRADE_PAGE));
  }, [footerInView, shown, trades.length]);
  if (!trades.length)
    return (
      <EmptyState
        illustration={<ChartEmpty />}
        title={emptyTitle}
        text={emptyText}
        action={emptyAction}
      />
    );
  const href = (t: Trade) => `/journal/strategies/${strategyId}/trades/${t.id}`;
  const backtest = mode === "backtest";
  const visible = trades.slice(0, shown);
  const open = (t: Trade) => {
    lastOpened = t.id;
    setOpening(t.id);
  };
  const nameOf = (t: Trade) =>
    t.id === opening || t.id === lastOpened ? vtName("trade", t.id) : undefined;
  const footer = (
    <ShowingLine
      shown={shown}
      total={trades.length}
      onAll={() => setShown(trades.length)}
      sentinel={sentinel}
    />
  );

  if (device !== "desktop") {
    return (
      <div>
        <ul className="flex flex-col gap-2" aria-label="Trades">
          {visible.map((t) => (
            <li key={t.id}>
              <Link
                to={href(t)}
                onClick={() => open(t)}
                className="flex min-h-11 flex-col gap-2 rounded-panel border border-border bg-surface-2 p-3 hover:border-border-strong"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="font-mono text-body"
                    style={{ viewTransitionName: nameOf(t) }}
                  >
                    {t.instrument}
                  </span>
                  <SideChip side={t.side} />
                  {backtest ? <OutcomeChip outcome={t.outcome} /> : null}
                  {/* Backtests lead with dollars, R beneath; ideal trades have no $ so R stays the figure. */}
                  <span
                    className={`num ml-auto text-body font-medium ${((backtest ? t.pnl : t.r_multiple) ?? 0) > 0 ? "text-win" : ((backtest ? t.pnl : t.r_multiple) ?? 0) < 0 ? "text-loss" : ""}`}
                  >
                    {backtest ? fmtPnl(t.pnl) : fmtR(t.r_multiple)}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-label text-muted">
                  <span className="num">
                    {fmtUkDate(t.opened_at)} · {fmtUkTime(t.opened_at)}
                  </span>
                  <span>{t.session_label}</span>
                  {t.entry_model ? <span>{t.entry_model}</span> : null}
                  {backtest ? (
                    <span className="num">{fmtR(t.r_multiple)}</span>
                  ) : null}
                  <Completed t={t} />
                  <MissingShots t={t} />
                  {!hasReason(t) ? <span>No reason yet</span> : null}
                </div>
              </Link>
            </li>
          ))}
        </ul>
        {footer}
      </div>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-separate border-spacing-0 whitespace-nowrap text-body">
          <thead>
            <tr className="text-left text-label text-muted">
              <th
                scope="col"
                className="sticky left-0 z-10 border-b border-border bg-surface-1 px-2 py-2 font-normal"
              >
                Date
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Time
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Instrument
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Side
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Session
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Model
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 text-right font-normal"
              >
                SL
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 text-right font-normal"
              >
                TP
              </th>
              <th
                scope="col"
                className="border-b border-border px-2 py-2 text-right font-normal"
              >
                Held
              </th>
              {backtest ? (
                <th
                  scope="col"
                  className="border-b border-border px-2 py-2 text-right font-normal"
                >
                  P&amp;L
                </th>
              ) : null}
              <th
                scope="col"
                className="border-b border-border px-2 py-2 text-right font-normal"
              >
                R
              </th>
              {backtest ? (
                <th
                  scope="col"
                  className="border-b border-border px-2 py-2 font-normal"
                >
                  Outcome
                </th>
              ) : null}
              {backtest ? (
                <th
                  scope="col"
                  className="border-b border-border px-2 py-2 text-right font-normal"
                >
                  Rules
                </th>
              ) : null}
              <th
                scope="col"
                className="border-b border-border px-2 py-2 font-normal"
              >
                Status
              </th>
              {showOwner ? (
                <th
                  scope="col"
                  className="border-b border-border px-2 py-2 font-normal"
                >
                  By
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {visible.map((t) => (
              <tr
                key={t.id}
                className="cursor-pointer hover:bg-surface-2"
                onClick={() => {
                  open(t);
                  navigate(href(t));
                }}
              >
                <td className="num sticky left-0 z-10 border-b border-border bg-surface-1 px-2 py-0">
                  <Link
                    to={href(t)}
                    onClick={(e) => {
                      e.stopPropagation();
                      open(t);
                    }}
                    className="flex min-h-11 items-center"
                    aria-label={`Open trade on ${fmtUkDate(t.opened_at)} ${fmtUkTime(t.opened_at)} ${t.instrument}`}
                  >
                    {fmtUkDate(t.opened_at)}
                  </Link>
                </td>
                <td className="num border-b border-border px-2 py-2.5 text-muted">
                  {fmtUkTime(t.opened_at)}
                </td>
                <td
                  className="border-b border-border px-2 py-2.5 font-mono"
                  style={{ viewTransitionName: nameOf(t) }}
                >
                  {t.instrument}
                </td>
                <td className="border-b border-border px-2 py-2.5">
                  <SideChip side={t.side} />
                </td>
                <td className="border-b border-border px-2 py-2.5 text-muted">
                  {t.session_label}
                </td>
                <td className="border-b border-border px-2 py-2.5 text-muted">
                  {t.entry_model ?? "—"}
                </td>
                <td className="num border-b border-border px-2 py-2.5 text-right">
                  {t.sl_distance ?? "—"}
                </td>
                <td className="num border-b border-border px-2 py-2.5 text-right">
                  {t.tp_distance ?? "—"}
                  {t.tp_r ? (
                    <span className="text-muted"> · {t.tp_r.toFixed(1)}R</span>
                  ) : null}
                </td>
                <td className="num border-b border-border px-2 py-2.5 text-right text-muted">
                  {fmtDuration(t.duration_seconds)}
                </td>
                {backtest ? (
                  <td
                    className={`num border-b border-border px-2 py-2.5 text-right font-medium ${(t.pnl ?? 0) > 0 ? "text-win" : (t.pnl ?? 0) < 0 ? "text-loss" : ""}`}
                  >
                    {fmtPnl(t.pnl)}
                  </td>
                ) : null}
                <td
                  className={`num border-b border-border px-2 py-2.5 text-right ${backtest ? "" : "font-medium "}${(t.r_multiple ?? 0) > 0 ? "text-win" : (t.r_multiple ?? 0) < 0 ? "text-loss" : ""}`}
                >
                  {fmtR(t.r_multiple)}
                </td>
                {backtest ? (
                  <td className="border-b border-border px-2 py-2.5">
                    <OutcomeChip outcome={t.outcome} />
                  </td>
                ) : null}
                {backtest ? (
                  <td className="border-b border-border px-2 py-2.5 text-right">
                    <RulesFollowed t={t} />
                  </td>
                ) : null}
                <td className="border-b border-border px-2 py-2.5">
                  <span className="flex items-center gap-1.5">
                    <Completed t={t} />
                    <MissingShots t={t} />
                    {t.tags.length ? (
                      <Chip>
                        <Tag aria-hidden className="size-3" />{" "}
                        <span className="num">{t.tags.length}</span>
                      </Chip>
                    ) : null}
                  </span>
                </td>
                {showOwner ? (
                  <td className="border-b border-border px-2 py-2.5">
                    <OwnerChip
                      name={t.owner.display_name}
                      colourIndex={t.owner.colour_index}
                      compact
                    />
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer}
    </div>
  );
}
