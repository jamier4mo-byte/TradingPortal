import { KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CreditsMeter, PausedBanner } from "../../components/market/CreditsMeter.tsx";
import { InstrumentSearch } from "../../components/market/InstrumentSearch.tsx";
import { TickerCard } from "../../components/market/TickerCard.tsx";
import { WatchlistRow } from "../../components/market/WatchlistRow.tsx";
import { ChartEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonCard, useToast } from "../../components/ui/index.ts";
import { type Quote, usePinMutations, usePins, useQuotes, useSparkline } from "../../lib/markets.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";

const SUGGESTED = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "GER40", "NAS100"];

/** Live market data (1.5): the pinned watchlist as ticker cards, search to pin, and today's credits.
 * Prompt 5 places the same components on the Hub. Prices come from our backend only. */
export default function Markets() {
  const device = useDevice();
  const pins = usePins();
  const quotes = useQuotes();
  const { pin, unpin } = usePinMutations();
  const { toast } = useToast();
  const pinned = pins.data?.pins.map((p) => p.code ?? p.symbol) ?? [];
  const full = pins.data ? pins.data.pins.length >= pins.data.max : false;
  const usage = quotes.data?.usage;

  const doPin = (symbol: string) =>
    pin.mutate(symbol, {
      onSuccess: () => toast({ title: `Pinned ${symbol}` }),
      onError: (err) => toast({ title: "Couldn't pin it", text: err.message, tone: "loss" }),
    });
  const doUnpin = (q: Quote) =>
    unpin.mutate(q.symbol, {
      onSuccess: () => toast({ title: `Unpinned ${q.code ?? q.symbol}`, undo: () => doPin(q.code ?? q.symbol) }),
    });

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-heading font-semibold">Markets</h1>
        <p className="text-body text-muted">Delayed prices from your Twelve Data key, refreshed every 15 minutes while this page is open.</p>
      </header>

      {usage?.paused ? <PausedBanner reason={usage.paused_reason ?? "Live data paused – daily limit reached"} /> : null}

      <div className="grid gap-4 laptop:grid-cols-12 laptop:gap-6">
        <div className="flex flex-col gap-4 laptop:col-span-8 laptop:gap-6 desktop:col-span-9">
          <Card title="Watchlist" subtitle={pins.data ? `${pins.data.pins.length} of ${pins.data.max} pinned` : undefined}>
            <InstrumentSearch
              onPick={(r) => (full ? toast({ title: "Watchlist is full", text: "Unpin one first: 8 is the limit, to keep within your daily credits.", tone: "loss" }) : doPin(r.code ?? r.symbol))}
              pinned={pinned}
              className="mb-4"
            />
            {pins.isPending || quotes.isPending ? (
              <div className="grid gap-4 tablet:grid-cols-2 desktop:grid-cols-3">
                <SkeletonCard className="h-44" />
                <SkeletonCard className="h-44" />
                <SkeletonCard className="h-44" />
              </div>
            ) : pins.isError || quotes.isError ? (
              <ErrorState text={(pins.error ?? quotes.error)?.message} onRetry={() => void Promise.all([pins.refetch(), quotes.refetch()])} />
            ) : quotes.data.quotes.length === 0 ? (
              <EmptyState
                illustration={<ChartEmpty />}
                title="Nothing pinned yet"
                text="Search above, or start with these:"
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTED.map((s) => (
                      <button key={s} type="button" className="btn btn-secondary" onClick={() => doPin(s)} disabled={pin.isPending}>
                        {s}
                      </button>
                    ))}
                  </div>
                }
              />
            ) : device === "phone" ? (
              <ul className="flex flex-col gap-2" aria-label="Pinned instruments">
                {quotes.data.quotes.map((q) => (
                  <QuoteRow key={q.symbol} quote={q} onUnpin={() => doUnpin(q)} busy={unpin.isPending} />
                ))}
              </ul>
            ) : (
              <ul className="grid gap-4 tablet:grid-cols-2 desktop:grid-cols-3" aria-label="Pinned instruments">
                {quotes.data.quotes.map((q) => (
                  <li key={q.symbol}>
                    <QuoteCard quote={q} paused={!!usage?.paused} />
                  </li>
                ))}
              </ul>
            )}
            {device !== "phone" && quotes.data?.quotes.length ? (
              <details className="mt-4">
                <summary className="inline-flex min-h-11 cursor-pointer items-center text-body text-muted hover:text-text">Manage pins</summary>
                <ul className="mt-2 flex flex-col gap-2">
                  {quotes.data.quotes.map((q) => (
                    <QuoteRow key={q.symbol} quote={q} onUnpin={() => doUnpin(q)} busy={unpin.isPending} />
                  ))}
                </ul>
              </details>
            ) : null}
          </Card>
        </div>
        <div className="flex flex-col gap-4 laptop:col-span-4 laptop:gap-6 desktop:col-span-3">
          <Card title="Twelve Data" subtitle="Your own key, 800 credits a day">
            {usage ? (
              usage.has_key || usage.provider === "fake" ? (
                <CreditsMeter usage={usage} />
              ) : (
                <EmptyState
                  title="No key yet"
                  text="Prices use your own free Twelve Data key, kept encrypted on the server."
                  action={
                    <Link to="/settings#keys" className="btn btn-primary">
                      <KeyRound aria-hidden className="size-4" />
                      Add your key
                    </Link>
                  }
                />
              )
            ) : (
              <SkeletonCard className="h-16" />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function QuoteCard({ quote, paused }: { quote: Quote; paused: boolean }) {
  const spark = useSparkline(quote.code ?? quote.symbol, quote.status === "ok" || quote.status === "stale");
  return <TickerCard quote={quote} points={spark.data?.points.map((p) => p.v) ?? []} paused={paused} />;
}

function QuoteRow({ quote, onUnpin, busy }: { quote: Quote; onUnpin: () => void; busy: boolean }) {
  const spark = useSparkline(quote.code ?? quote.symbol, quote.status === "ok" || quote.status === "stale");
  return <WatchlistRow quote={quote} points={spark.data?.points.map((p) => p.v) ?? []} onUnpin={onUnpin} busy={busy} />;
}
