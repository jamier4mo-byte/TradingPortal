import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { displaySymbol, formatPrice, type Quote, signed } from "../../lib/markets.ts";
import { ukTime } from "../../lib/news.ts";
import { vtName } from "../../lib/vt.ts";
import { Odometer } from "./Odometer.tsx";
import { PriceSparkline } from "./PriceSparkline.tsx";

/** Live dot: pulses softly while live data is flowing; grey and still when paused or stale. */
export function LiveDot({ live, className = "" }: { live: boolean; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-label text-muted ${className}`}>
      <span aria-hidden className={`size-2 rounded-full ${live ? "pulse bg-live" : "bg-stale"}`} />
      <span>{live ? "Live" : "Paused"}</span>
    </span>
  );
}

export function DelayedLabel({ updatedAt, className = "" }: { updatedAt: string | null; className?: string }) {
  return <span className={`num text-label text-muted ${className}`}>{updatedAt ? `Delayed · updated ${ukTime(updatedAt)}` : "Delayed · not updated yet"}</span>;
}

/** Instrument, price, change, % change, day high/low, sparkline and "Delayed · updated HH:MM".
 * A changed price rolls its digits and flashes green or red for ~600ms (paired with ▲/▼). */
export function TickerCard({
  quote,
  points,
  paused = false,
  compact = false,
}: {
  quote: Quote;
  points: number[];
  paused?: boolean;
  compact?: boolean;
}) {
  const id = quote.code ?? quote.symbol;
  const label = displaySymbol(quote.code, quote.symbol);
  const [flash, setFlash] = useState<{ key: number; dir: "up" | "down" } | null>(null);
  const prev = useRef<number | null>(quote.price);
  useEffect(() => {
    const before = prev.current;
    prev.current = quote.price;
    if (before !== null && quote.price !== null && quote.price !== before) {
      setFlash({ key: Date.now(), dir: quote.price > before ? "up" : "down" });
    }
  }, [quote.price]);

  const usable = quote.status === "ok" || quote.status === "stale";
  const live = !paused && quote.status === "ok";
  const up = (quote.change ?? 0) > 0;
  const down = (quote.change ?? 0) < 0;

  return (
    <Link
      to={`/markets/${encodeURIComponent(id)}`}
      className="card group relative block min-w-0 overflow-hidden p-4 transition-[transform,border-color] duration-(--dur-quick) hover:-translate-y-0.5 hover:border-border-strong"
      style={{ viewTransitionName: vtName("ticker", id) }}
      aria-label={`${label} ${usable ? formatPrice(quote.price, quote.decimals) : quote.message ?? ""}`}
    >
      {flash ? (
        <span key={flash.key} aria-hidden className={`price-flash absolute inset-0 ${flash.dir === "up" ? "bg-win" : "bg-loss"}`} />
      ) : null}
      <div className="relative flex items-start gap-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-body font-semibold">{label}</p>
          <p className="truncate text-label text-muted">{quote.name}</p>
        </div>
        <LiveDot live={live} className="ml-auto shrink-0" />
      </div>

      {usable ? (
        <>
          <div className="relative mt-3 flex flex-wrap items-end justify-between gap-x-3 gap-y-2">
            <div className="min-w-0">
              <Odometer text={formatPrice(quote.price, quote.decimals)} className={`${compact ? "text-title" : "text-heading"} font-semibold leading-none`} />
              <p className="num mt-1 text-label text-text">
                <span aria-hidden>{up ? "▲ " : down ? "▼ " : ""}</span>
                {signed(quote.change, quote.decimals)} ({signed(quote.percent_change, 2, "%")})
              </p>
            </div>
            {compact ? null : <PriceSparkline values={points} label={`${label} today`} />}
          </div>
          {compact ? null : (
            <dl className="num relative mt-3 grid grid-cols-2 gap-2 text-label">
              <div>
                <dt className="text-muted">Day high</dt>
                <dd>{formatPrice(quote.high, quote.decimals)}</dd>
              </div>
              <div>
                <dt className="text-muted">Day low</dt>
                <dd>{formatPrice(quote.low, quote.decimals)}</dd>
              </div>
            </dl>
          )}
          <DelayedLabel updatedAt={quote.updated_at} className={`relative mt-3 block ${quote.status === "stale" ? "opacity-80" : ""}`} />
        </>
      ) : (
        <p className="relative mt-3 text-body text-muted">
          {quote.status === "no_key" ? "Add your Twelve Data key in Settings to see prices." : quote.message ?? "No price right now."}
        </p>
      )}
    </Link>
  );
}
