import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Pin, PinOff } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { PausedBanner } from "../../components/market/CreditsMeter.tsx";
import { IntradayChart } from "../../components/market/IntradayChart.tsx";
import { DelayedLabel, LiveDot, PriceFigure } from "../../components/market/TickerCard.tsx";
import { CurrencyTag, ImpactChip } from "../../components/news/NewsBits.tsx";
import { ChartEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonCard, SkeletonText, useToast } from "../../components/ui/index.ts";
import { api } from "../../lib/api.ts";
import { displaySymbol, formatPrice, signed, usePinMutations, usePins, useQuote, useSparkline, useUsage } from "../../lib/markets.ts";
import { addDays, dayLabel, ukISODate, useEvents } from "../../lib/news.ts";
import { vtName } from "../../lib/vt.ts";

/** Instrument view: the ticker card grown into a page (shared-element transition), with the day's range,
 * an intraday line and the news that moves it this week. */
export default function InstrumentView() {
  const { symbol = "" } = useParams();
  const q = useQuote(symbol);
  const spark = useSparkline(symbol, q.data ? q.data.status === "ok" || q.data.status === "stale" : false);
  const usage = useUsage();
  const pins = usePins();
  const { pin, unpin } = usePinMutations();
  const { toast } = useToast();
  const navigate = useNavigate();

  const quote = q.data;
  const code = quote?.code ?? symbol;
  const isPinned = pins.data?.pins.some((p) => (p.code ?? p.symbol) === code || p.symbol === quote?.symbol) ?? false;
  const usable = quote && (quote.status === "ok" || quote.status === "stale");
  const label = quote ? displaySymbol(quote.code, quote.symbol) : symbol;

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <div>
        <button type="button" className="btn btn-ghost -ml-3" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/markets"))}>
          <ArrowLeft aria-hidden className="size-4" />
          Markets
        </button>
      </div>
      {usage.data?.paused ? <PausedBanner reason={usage.data.paused_reason ?? "Live data paused – daily limit reached"} /> : null}

      {q.isPending ? (
        <SkeletonCard className="h-56" />
      ) : q.isError ? (
        <ErrorState title="This instrument didn't load" text={q.error.message} onRetry={() => q.refetch()} />
      ) : (
        <section className="card relative overflow-hidden p-4 tablet:p-6" style={{ viewTransitionName: vtName("ticker", code) }} aria-labelledby="instrument-title">
          <div className="relative flex flex-wrap items-start gap-3">
            <div className="min-w-0">
              <h1 id="instrument-title" className="font-mono text-heading font-semibold">
                {label}
              </h1>
              <p className="text-body text-muted">{quote!.name}</p>
            </div>
            <LiveDot live={quote!.status === "ok" && !usage.data?.paused} className="ml-auto" />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={pin.isPending || unpin.isPending}
              onClick={() =>
                isPinned
                  ? unpin.mutate(quote!.symbol, { onSuccess: () => toast({ title: `Unpinned ${label}` }) })
                  : pin.mutate(code, {
                      onSuccess: () => toast({ title: `Pinned ${label}` }),
                      onError: (err) => toast({ title: "Couldn't pin it", text: err.message, tone: "loss" }),
                    })
              }
            >
              {isPinned ? <PinOff aria-hidden className="size-4" /> : <Pin aria-hidden className="size-4" />}
              {isPinned ? "Unpin" : "Pin"}
            </button>
          </div>
          {usable ? (
            <div className="relative mt-4 grid gap-6 laptop:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] laptop:items-end">
              <div>
                <PriceFigure price={quote!.price} decimals={quote!.decimals} className="text-hero font-semibold" />
                <p className="num mt-2 text-body">
                  <span aria-hidden>{(quote!.change ?? 0) > 0 ? "▲ " : (quote!.change ?? 0) < 0 ? "▼ " : ""}</span>
                  {signed(quote!.change, quote!.decimals)} ({signed(quote!.percent_change, 2, "%")}) today
                </p>
                <DelayedLabel updatedAt={quote!.updated_at} className="mt-2 block" />
              </div>
              <div className="min-w-0">
                {spark.isPending ? (
                  <SkeletonText lines={3} />
                ) : (
                  <IntradayChart points={spark.data?.points ?? []} decimals={quote!.decimals} label={`${label} intraday`} />
                )}
              </div>
            </div>
          ) : (
            <div className="relative mt-4">
              <EmptyState
                illustration={<ChartEmpty />}
                title={quote!.status === "unavailable" ? "Not available on your Twelve Data plan" : quote!.status === "no_key" ? "No Twelve Data key yet" : "No price right now"}
                text={
                  quote!.status === "unavailable"
                    ? "The free Basic plan covers forex and crypto. Gold and stock indices need a paid plan; the portal never shows a made-up price."
                    : quote!.status === "no_key"
                      ? "Add your free key in Settings and prices appear here."
                      : quote!.message ?? undefined
                }
                action={
                  quote!.status === "no_key" ? (
                    <Link to="/settings#keys" className="btn btn-primary">
                      Add your key
                    </Link>
                  ) : undefined
                }
              />
            </div>
          )}
        </section>
      )}

      {usable ? (
        <div className="grid gap-4 laptop:grid-cols-12 laptop:gap-6">
          <Card title="Today" subtitle="From the latest delayed quote" className="laptop:col-span-5">
            <dl className="num grid grid-cols-2 gap-3 text-body">
              {[
                ["Open", formatPrice(quote!.open, quote!.decimals)],
                ["Previous close", formatPrice(quote!.previous_close, quote!.decimals)],
                ["Day high", formatPrice(quote!.high, quote!.decimals)],
                ["Day low", formatPrice(quote!.low, quote!.decimals)],
                ["Change", signed(quote!.change, quote!.decimals)],
                ["Market", quote!.is_market_open === null ? "—" : quote!.is_market_open ? "Open" : "Closed"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-panel border border-border bg-surface-2 p-3">
                  <dt className="text-label text-muted">{k}</dt>
                  <dd className="mt-1">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <InstrumentNews code={code} className="laptop:col-span-7" />
        </div>
      ) : quote ? (
        <InstrumentNews code={code} />
      ) : null}
    </div>
  );
}

function InstrumentNews({ code, className = "" }: { code: string; className?: string }) {
  const map = useQuery({ queryKey: ["news", "instrument-map"], queryFn: () => api.get<{ currency: string; instrument: string }[]>("/api/news/instrument-map") });
  const currencies = (map.data ?? []).filter((m) => m.instrument.toUpperCase() === code.toUpperCase()).map((m) => m.currency);
  const today = ukISODate(new Date());
  const events = useEvents({ from: today, to: addDays(today, 6), currencies, impacts: ["high", "medium"], mine: false });
  const list = currencies.length ? (events.data?.events ?? []) : [];
  return (
    <Card title="News that moves it" subtitle="High and medium impact, next 7 days" className={className}>
      {map.isError || events.isError ? (
        <ErrorState title="News didn't load" text={(map.error ?? events.error)?.message} onRetry={() => void Promise.all([map.refetch(), events.refetch()])} />
      ) : map.isPending || (currencies.length > 0 && events.isPending) ? (
        <SkeletonText lines={4} />
      ) : currencies.length === 0 ? (
        <p className="text-body text-muted">No event currencies are mapped to this instrument.</p>
      ) : list.length === 0 ? (
        <p className="text-body text-muted">Nothing high or medium impact for {currencies.join(", ")} this week.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {list.slice(0, 12).map((e) => (
            <li key={e.id}>
              <Link to={`/news/events/${e.id}`} className="flex min-h-12 items-center gap-3 py-2 hover:underline hover:decoration-border-strong hover:underline-offset-4">
                <span className="num w-24 shrink-0 text-label text-muted">
                  {dayLabel(e.uk_date, "short")} {e.uk_time}
                </span>
                <CurrencyTag currency={e.currency} />
                <span className="min-w-0 flex-1 truncate text-body">{e.name}</span>
                <ImpactChip impact={e.impact} compact />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
