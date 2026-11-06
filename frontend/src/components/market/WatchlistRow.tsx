import { PinOff } from "lucide-react";
import { type PointerEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { displaySymbol, formatPrice, type Quote, signed } from "../../lib/markets.ts";
import { ukTime } from "../../lib/news.ts";
import { PriceSparkline } from "./PriceSparkline.tsx";

const REVEAL = 96; // px the row slides to show Remove

/** One pinned instrument as a row. On touch screens, swipe left to reveal Remove; the unpin button is
 * always there too (gestures are shortcuts, never the only way). */
export function WatchlistRow({ quote, points, onUnpin, busy = false, paused = false }: { quote: Quote; points: number[]; onUnpin: () => void; busy?: boolean; paused?: boolean }) {
  const id = quote.code ?? quote.symbol;
  const label = displaySymbol(quote.code, quote.symbol);
  const [dx, setDx] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<{ x: number; y: number; base: number; horizontal: boolean | null } | null>(null);
  const usable = quote.status === "ok" || quote.status === "stale";
  const up = (quote.change ?? 0) > 0;
  const down = (quote.change ?? 0) < 0;

  const onDown = (e: PointerEvent) => {
    if (e.pointerType !== "touch") return;
    start.current = { x: e.clientX, y: e.clientY, base: dx, horizontal: null };
  };
  const onMove = (e: PointerEvent) => {
    const s = start.current;
    if (!s) return;
    const mx = e.clientX - s.x;
    const my = e.clientY - s.y;
    if (s.horizontal === null && Math.hypot(mx, my) > 8) s.horizontal = Math.abs(mx) > Math.abs(my);
    if (s.horizontal) {
      setDragging(true);
      setDx(Math.max(-REVEAL, Math.min(0, s.base + mx)));
    }
  };
  const onUp = () => {
    if (!start.current) return;
    start.current = null;
    setDragging(false);
    setDx((v) => (v < -REVEAL / 2 ? -REVEAL : 0));
  };

  return (
    <li className="relative overflow-hidden rounded-panel border border-border bg-surface-2">
      <div className={`absolute inset-y-0 right-0 flex items-center pr-2 ${dx === 0 && !dragging ? "invisible" : ""}`} aria-hidden={dx === 0}>
        <button type="button" className="btn btn-danger" tabIndex={dx === 0 ? -1 : 0} onClick={onUnpin} disabled={busy}>
          Remove
        </button>
      </div>
      <div
        className={`relative flex min-h-14 touch-pan-y items-center gap-3 bg-surface-2 pr-1 pl-3 ${dragging ? "" : "transition-transform duration-(--dur-standard) ease-(--ease-in-enter)"}`}
        style={{ transform: `translateX(${dx}px)` }}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
      >
        <Link to={`/markets/${encodeURIComponent(id)}`} className="flex min-h-11 min-w-0 flex-1 items-center gap-3">
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-body font-semibold">{label}</span>
            <span className={`num block truncate text-label text-muted ${quote.status === "stale" || paused ? "opacity-80" : ""}`}>
              {usable ? (
                <>
                  <span aria-hidden className={`mr-1.5 inline-block size-1.5 rounded-full align-middle ${quote.status === "ok" && !paused ? "bg-live" : "bg-stale"}`} />
                  {quote.status === "ok" && !paused ? "" : "Paused · "}
                  {quote.updated_at ? `Delayed · ${ukTime(quote.updated_at)}` : quote.name}
                </>
              ) : (
                quote.message ?? "No price"
              )}
            </span>
          </span>
          <PriceSparkline values={points} width={72} height={28} label={`${label} today`} className="hidden tablet:block" />
          {usable ? (
            <span className="num shrink-0 text-right">
              <span className="block text-body">{formatPrice(quote.price, quote.decimals)}</span>
              <span className="block text-label text-muted">
                <span aria-hidden>{up ? "▲ " : down ? "▼ " : ""}</span>
                {signed(quote.percent_change, 2, "%")}
              </span>
            </span>
          ) : null}
        </Link>
        <button type="button" className="btn btn-ghost size-11 shrink-0 px-0" aria-label={`Unpin ${label}`} onClick={onUnpin} disabled={busy}>
          <PinOff aria-hidden className="size-4" />
        </button>
      </div>
    </li>
  );
}
