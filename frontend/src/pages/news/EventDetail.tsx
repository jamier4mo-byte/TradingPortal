import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { CountdownRing } from "../../components/news/CountdownRing.tsx";
import { CurrencyTag, Figures, ImpactChip, SurpriseBadge } from "../../components/news/NewsBits.tsx";
import { ListEmpty, PulseEmpty } from "../../components/ui/Illustrations.tsx";
import { EmptyState, ErrorState, SkeletonCard } from "../../components/ui/index.ts";
import { displaySymbol } from "../../lib/markets.ts";
import { dayLabel, type EventDetail as Detail, type HorizonReaction, useEventDetail } from "../../lib/news.ts";
import { useNow } from "../../lib/useNow.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";
import { vtName } from "../../lib/vt.ts";

const HORIZONS = ["5", "15", "60"] as const;

function shortDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "numeric", month: "short", year: "2-digit" }).format(new Date(iso));
}

/** Event detail (3.3): what it is, the release history with surprises, and how our instruments moved
 * 5, 15 and 60 minutes after past releases. Full screen on the phone. */
export default function EventDetailPage() {
  const { id } = useParams();
  const eventId = Number(id);
  const q = useEventDetail(eventId);

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <div>
        <Link to="/news" className="btn btn-ghost -ml-3">
          <ArrowLeft aria-hidden className="size-4" />
          News Room
        </Link>
      </div>
      {q.isPending ? (
        <>
          <SkeletonCard className="h-36" />
          <div className="grid gap-4 laptop:grid-cols-2">
            <SkeletonCard className="h-56" />
            <SkeletonCard className="h-56" />
          </div>
        </>
      ) : q.isError ? (
        <ErrorState
          title={q.error.message.includes("Not Found") || q.error.message.includes("not found") ? "That event isn't in the calendar" : "The event didn't load"}
          text={q.error.message}
          onRetry={() => q.refetch()}
        />
      ) : (
        <DetailBody d={q.data} />
      )}
    </div>
  );
}

function DetailBody({ d }: { d: Detail }) {
  const e = d.event;
  const phone = useDevice() === "phone";
  const now = useNow(1000);
  const secs = (new Date(e.at).getTime() - now.getTime()) / 1000;
  return (
    <>
      <section className="card flex flex-col gap-4 p-4 tablet:flex-row tablet:items-center tablet:p-6" aria-labelledby="event-title">
        <div className="min-w-0 flex-1">
          <p className="num text-label text-muted">
            {dayLabel(e.uk_date)} · {e.all_day ? "All day" : `${e.uk_time} UK`}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <CurrencyTag currency={e.currency} />
            <h1 id="event-title" className="text-heading font-semibold" style={{ viewTransitionName: vtName("event", e.id) }}>
              {e.name}
            </h1>
            <ImpactChip impact={e.impact} />
          </div>
          {e.title !== e.name ? <p className="mt-1 text-label text-muted">Listed as &ldquo;{e.title}&rdquo;</p> : null}
          <Figures event={e} words className="mt-4 max-w-xl" />
          {e.instruments.length ? <p className="mt-3 text-body text-muted">Moves {e.instruments.map((i) => displaySymbol(i, i)).join(", ")}</p> : null}
        </div>
        {secs > 0 && secs < 7 * 86400 ? <CountdownRing secondsLeft={secs} label={`${e.currency} ${e.name}`} /> : null}
      </section>

      {d.summary ? (
        <p className="rounded-panel border border-border bg-surface-1 px-4 py-3 text-body" role="note">
          {d.summary}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 laptop:gap-6 desktop:grid-cols-12">
        <Card title="What it is" className="desktop:col-span-5">
          {d.type?.explanation ? (
            <div className="flex flex-col gap-3 text-body">
              <p>{d.type.explanation}</p>
              {d.type.why_it_matters ? (
                <div>
                  <h3 className="text-label font-semibold text-muted">Why it matters</h3>
                  <p className="mt-1">{d.type.why_it_matters}</p>
                </div>
              ) : null}
              {d.type.higher_is_better !== null ? (
                <p className="text-label text-muted">
                  For the {e.currency}, a {d.type.higher_is_better ? "higher" : "lower"} figure than forecast usually reads as better.
                </p>
              ) : null}
            </div>
          ) : (
            <EmptyState illustration={<ListEmpty />} title="No explanation yet" text="This event isn't in the portal's guide yet. The figures and history below still apply." />
          )}
        </Card>

        <Card title="Release history" subtitle="Actual, forecast, previous and surprise" className="desktop:col-span-7">
          {d.history.length === 0 ? (
            <EmptyState illustration={<ListEmpty />} title="No past releases stored" text={d.empty.history ?? "History builds up as each release is stored."} />
          ) : phone ? (
            <ul className="flex flex-col divide-y divide-border" aria-label={`Past releases of ${e.name}`}>
              {d.history.map((h) => (
                <li key={h.event_id}>
                  <Link to={`/news/events/${h.event_id}`} className="block py-2">
                    <span className="num block text-label text-muted">{shortDate(h.at)}</span>
                    <span className="num mt-1 grid grid-cols-3 gap-2 text-body">
                      <span>
                        <span className="block text-label text-muted">Actual</span>
                        {h.actual ?? "—"}
                      </span>
                      <span>
                        <span className="block text-label text-muted">Forecast</span>
                        {h.forecast ?? "—"}
                      </span>
                      <span>
                        <span className="block text-label text-muted">Previous</span>
                        {h.previous ?? "—"}
                      </span>
                    </span>
                    {h.surprise ? (
                      <span className="mt-1 block">
                        <SurpriseBadge surprise={h.surprise} withWords />
                      </span>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="relative -mx-4 overflow-x-auto px-4 tablet:mx-0 tablet:px-0" role="region" tabIndex={0} aria-label="Release history table, scrolls sideways">
              <table className="w-full min-w-[30rem] text-body">
                <caption className="sr-only">Past releases of {e.name}</caption>
                <thead>
                  <tr className="border-b border-border text-left text-label text-muted">
                    <th scope="col" className="sticky left-0 bg-surface-1 py-2 pr-3 font-normal">Date</th>
                    <th scope="col" className="py-2 pr-3 text-right font-normal">Actual</th>
                    <th scope="col" className="py-2 pr-3 text-right font-normal">Forecast</th>
                    <th scope="col" className="py-2 pr-3 text-right font-normal">Previous</th>
                    <th scope="col" className="py-2 font-normal">Surprise</th>
                  </tr>
                </thead>
                <tbody>
                  {d.history.map((h) => (
                    <tr key={h.event_id} className="border-b border-border last:border-0">
                      <th scope="row" className="num sticky left-0 bg-surface-1 py-2 pr-3 text-left font-normal">
                        <Link to={`/news/events/${h.event_id}`} className="inline-flex min-h-11 items-center hover:underline">
                          {shortDate(h.at)}
                        </Link>
                      </th>
                      <td className="num py-2 pr-3 text-right">{h.actual ?? "—"}</td>
                      <td className="num py-2 pr-3 text-right">{h.forecast ?? "—"}</td>
                      <td className="num py-2 pr-3 text-right">{h.previous ?? "—"}</td>
                      <td className="py-2">{h.surprise ? <SurpriseBadge surprise={h.surprise} /> : <span className="text-muted">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Price reaction" subtitle="Range in the 5, 15 and 60 minutes after each release" className="desktop:col-span-12">
          {d.reactions.length === 0 ? (
            <EmptyState illustration={<PulseEmpty />} title="No price reactions yet" text={d.empty.reactions ?? "Reactions are worked out once per release from Twelve Data price history."} />
          ) : (
            <Reactions d={d} />
          )}
        </Card>
      </div>
    </>
  );
}

function Cell({ h, unit }: { h: HorizonReaction | undefined; unit: string }) {
  if (!h || h.status !== "ok" || h.range === null) {
    return <span className="text-muted">{h?.status === "unavailable" ? "Not on plan" : "—"}</span>;
  }
  const arrow = h.direction === "up" ? "▲" : h.direction === "down" ? "▼" : "＝";
  return (
    <span className="num">
      {Math.round(h.range).toLocaleString("en-GB")} <span className="text-muted">{unit}</span>{" "}
      <span className="text-muted" aria-hidden>
        {arrow}
      </span>
      <span className="sr-only">{h.direction === "up" ? "up" : h.direction === "down" ? "down" : "flat"}</span>
    </span>
  );
}

function Reactions({ d }: { d: Detail }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="relative -mx-4 overflow-x-auto px-4 tablet:mx-0 tablet:px-0" role="region" tabIndex={0} aria-label="Average price reaction table, scrolls sideways">
        <table className="w-full min-w-[28rem] text-body">
          <caption className="sr-only">Average range after releases, by instrument</caption>
          <thead>
            <tr className="border-b border-border text-left text-label text-muted">
              <th scope="col" className="sticky left-0 bg-surface-1 py-2 pr-3 font-normal">Instrument</th>
              {HORIZONS.map((h) => (
                <th key={h} scope="col" className="py-2 pr-3 text-right font-normal">
                  Avg range {h} min
                </th>
              ))}
              <th scope="col" className="py-2 text-right font-normal">Releases</th>
            </tr>
          </thead>
          <tbody>
            {d.reactions.map((r) => (
              <tr key={r.instrument} className="border-b border-border last:border-0">
                <th scope="row" className="sticky left-0 bg-surface-1 py-2 pr-3 text-left font-mono font-normal">
                  {displaySymbol(r.instrument, r.instrument)}
                </th>
                {HORIZONS.map((h) => (
                  <td key={h} className="num py-2 pr-3 text-right">
                    {r.average_range[h] === null || r.average_range[h] === undefined ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <>
                        {Math.round(r.average_range[h] as number).toLocaleString("en-GB")} <span className="text-muted">{r.unit}</span>
                      </>
                    )}
                  </td>
                ))}
                <td className="num py-2 text-right">{r.releases}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="group">
        <summary className="inline-flex min-h-11 cursor-pointer items-center text-body text-muted hover:text-text">Each release</summary>
        <div className="relative -mx-4 mt-2 overflow-x-auto px-4 tablet:mx-0 tablet:px-0" role="region" tabIndex={0} aria-label="Each release table, scrolls sideways">
          <table className="w-full min-w-[34rem] text-body">
            <caption className="sr-only">Range and direction after each release</caption>
            <thead>
              <tr className="border-b border-border text-left text-label text-muted">
                <th scope="col" className="py-2 pr-3 font-normal">Release</th>
                <th scope="col" className="py-2 pr-3 font-normal">Instrument</th>
                {HORIZONS.map((h) => (
                  <th key={h} scope="col" className="py-2 pr-3 text-right font-normal">
                    {h} min
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.reactions.flatMap((r) =>
                r.rows.map((row) => (
                  <tr key={`${r.instrument}-${row.event_id}`} className="border-b border-border last:border-0">
                    <td className="num py-2 pr-3">{shortDate(row.at)}</td>
                    <td className="py-2 pr-3 font-mono">{displaySymbol(r.instrument, r.instrument)}</td>
                    {HORIZONS.map((h) => (
                      <td key={h} className="py-2 pr-3 text-right">
                        <Cell h={row.horizons[h]} unit={r.unit} />
                      </td>
                    ))}
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>
      <p className="text-label text-muted">▲ price finished higher, ▼ lower, ＝ flat. Ranges are high minus low over the window.</p>
    </div>
  );
}
