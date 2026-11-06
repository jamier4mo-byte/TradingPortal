import { KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CreditsMeter, PausedBanner } from "../../components/market/CreditsMeter.tsx";
import { InstrumentSearch } from "../../components/market/InstrumentSearch.tsx";
import { TickerCard } from "../../components/market/TickerCard.tsx";
import { WatchlistRow } from "../../components/market/WatchlistRow.tsx";
import { ChartEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, RefreshFailed, Skeleton, useToast } from "../../components/ui/index.ts";
import { type Quote, usePinMutations, usePins, useQuotes, useSparkline } from "../../lib/markets.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";

const SUGGESTED = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "GER40", "NAS100"];

/** Live market panel (1.5, F13) on the Hub: the pinned watchlist, search to pin, and today's credits. Same
 * hooks and components as /markets; prices refresh every 15 minutes (30 on the phone) while the tab is
 * visible and pause when hidden. Lazy: mounted only when it scrolls near the viewport. Phone: a row of
 * compact ticker cards you swipe through. */
export default function MarketPanel() {
  const device = useDevice();
  const pins = usePins();
  const quotes = useQuotes();
  const { pin, unpin } = usePinMutations();
  const { toast } = useToast();
  const pinned = pins.data?.pins.map((p) => p.code ?? p.symbol) ?? [];
  const full = pins.data ? pins.data.pins.length >= pins.data.max : false;
  const usage = quotes.data?.usage;
  const retry = () => void Promise.all([pins.refetch(), quotes.refetch()]);
  const offline = (pins.isPending || quotes.isPending) && (pins.fetchStatus === "paused" || quotes.fetchStatus === "paused");

  const doPin = (symbol: string) =>
    pin.mutate(symbol, {
      onSuccess: () => toast({ title: `Pinned ${symbol}` }),
      onError: (err) => toast({ title: "Couldn't pin it", text: err.message, tone: "loss" }),
    });
  const doUnpin = (q: Quote) =>
    unpin.mutate(q.symbol, { onSuccess: () => toast({ title: `Unpinned ${q.code ?? q.symbol}`, undo: () => doPin(q.code ?? q.symbol) }) });

  return (
    <Card
      title="Live market data"
      subtitle={pins.data ? `${pins.data.pins.length} of ${pins.data.max} pinned · delayed prices` : "Delayed prices from your Twelve Data key"}
      className="h-full"
      controls={
        <Link to="/markets" className="btn btn-ghost">
          Open Markets
        </Link>
      }
    >
      <div className="flex flex-col gap-4">
        {usage?.paused ? <PausedBanner reason={usage.paused_reason ?? "Live data paused – daily limit reached"} /> : null}
        {(quotes.isError && quotes.data) || (pins.isError && pins.data) ? <RefreshFailed updatedAt={quotes.dataUpdatedAt} onRetry={retry} /> : null}

        {offline ? (
          <EmptyState illustration={<ChartEmpty />} title="You're offline" text="Prices load when you're back online." />
        ) : pins.isPending || quotes.isPending ? (
          <div className="flex gap-3 overflow-hidden">
            <Skeleton className="h-28 flex-1" />
            <Skeleton className="h-28 flex-1" />
            <Skeleton className="hidden h-28 flex-1 tablet:block" />
          </div>
        ) : !pins.data || !quotes.data ? (
          <ErrorState text={(pins.error ?? quotes.error)?.message} onRetry={retry} />
        ) : quotes.data.quotes.length === 0 && usage && !usage.has_key && usage.provider !== "fake" ? (
          <EmptyState
            illustration={<ChartEmpty />}
            title="No Twelve Data key yet"
            text="Prices use your own free key, kept encrypted on the server."
            action={
              <Link to="/settings#keys" className="btn btn-primary">
                <KeyRound aria-hidden className="size-4" />
                Add your Twelve Data key
              </Link>
            }
          />
        ) : quotes.data.quotes.length === 0 ? (
          <EmptyState
            illustration={<ChartEmpty />}
            title="Nothing pinned yet"
            text="Search below, or start with these:"
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
          <ul className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1" aria-label="Pinned instruments">
            {quotes.data.quotes.map((q) => (
              <li key={q.symbol} className="w-[72vw] max-w-72 shrink-0 snap-center">
                <CompactTicker quote={q} paused={!!usage?.paused} />
              </li>
            ))}
          </ul>
        ) : (
          <ul className="flex flex-col gap-2" aria-label="Pinned instruments">
            {quotes.data.quotes.map((q) => (
              <QuoteRow key={q.symbol} quote={q} onUnpin={() => doUnpin(q)} busy={unpin.isPending} paused={!!usage?.paused} />
            ))}
          </ul>
        )}

        <InstrumentSearch
          onPick={(r) => (full ? toast({ title: "Watchlist is full", text: "Unpin one first: 8 is the limit, to keep within your daily credits.", tone: "loss" }) : doPin(r.code ?? r.symbol))}
          pinned={pinned}
        />

        {usage && (usage.has_key || usage.provider === "fake") ? <CreditsMeter usage={usage} /> : null}
      </div>
    </Card>
  );
}

function CompactTicker({ quote, paused }: { quote: Quote; paused: boolean }) {
  const spark = useSparkline(quote.code ?? quote.symbol, quote.status === "ok" || quote.status === "stale");
  return <TickerCard quote={quote} points={spark.data?.points.map((p) => p.v) ?? []} paused={paused} compact />;
}

function QuoteRow({ quote, onUnpin, busy, paused }: { quote: Quote; onUnpin: () => void; busy: boolean; paused: boolean }) {
  const spark = useSparkline(quote.code ?? quote.symbol, quote.status === "ok" || quote.status === "stale");
  return <WatchlistRow quote={quote} points={spark.data?.points.map((p) => p.v) ?? []} onUnpin={onUnpin} busy={busy} paused={paused} />;
}
