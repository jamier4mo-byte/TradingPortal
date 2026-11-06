import { Link } from "react-router-dom";

import { Switch, ToggleChip } from "../../components/ui/Toggles.tsx";

import { CurrencyTag, Figures, ImpactChip } from "../../components/news/NewsBits.tsx";
import { CURRENCIES, dayLabel, type Impact, type NewsEvent } from "../../lib/news.ts";
import { vtName } from "../../lib/vt.ts";

const IMPACT_FILTERS: { value: Impact; label: string; dot: string }[] = [
  { value: "high", label: "High", dot: "bg-impact-high" },
  { value: "medium", label: "Med", dot: "bg-impact-medium" },
  { value: "low", label: "Low", dot: "bg-impact-low" },
];

export interface FilterState {
  currencies: string[];
  impacts: Impact[];
  mine: boolean;
}

export function FilterControls({ value, onChange }: { value: FilterState; onChange: (v: FilterState) => void }) {
  const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  return (
    <div className="flex flex-col gap-4">
      <fieldset>
        <legend className="mb-2 text-label text-muted">Impact</legend>
        <div className="flex flex-wrap gap-2">
          {IMPACT_FILTERS.map((i) => (
            <ToggleChip key={i.value} pressed={value.impacts.includes(i.value)} onClick={() => onChange({ ...value, impacts: toggle(value.impacts, i.value) })}>
              <span aria-hidden className={`size-2 rounded-full ${i.dot}`} />
              {i.label}
            </ToggleChip>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 text-label text-muted">Currency</legend>
        <div className="flex flex-wrap gap-2">
          {CURRENCIES.map((c) => (
            <ToggleChip key={c} pressed={value.currencies.includes(c)} onClick={() => onChange({ ...value, currencies: toggle(value.currencies, c) })}>
              <span className="font-mono">{c}</span>
            </ToggleChip>
          ))}
        </div>
      </fieldset>
      <Switch checked={value.mine} onChange={(mine) => onChange({ ...value, mine })} label="My instruments only" description="Events that move the instruments you follow" />
    </div>
  );
}

export function filterCount(f: FilterState): number {
  return f.currencies.length + f.impacts.length + (f.mine ? 1 : 0);
}

/** One event as a row (laptop and up) or a compact card (phone/tablet). Links to the detail with a
 * shared-element transition on the event name. */
export function EventRow({ event, compact }: { event: NewsEvent; compact: boolean }) {
  if (compact) {
    return (
      <li>
        <Link to={`/news/events/${event.id}`} className="block rounded-panel border border-border bg-surface-2 p-3 transition-colors duration-(--dur-quick) hover:border-border-strong">
          <div className="flex items-start gap-2">
            <CurrencyTag currency={event.currency} />
            <p className="min-w-0 flex-1 text-body font-medium" style={{ viewTransitionName: vtName("event", event.id) }}>
              {event.name}
            </p>
            <ImpactChip impact={event.impact} compact />
          </div>
          <Figures event={event} className="mt-2" />
        </Link>
      </li>
    );
  }
  return (
    <li>
      <Link
        to={`/news/events/${event.id}`}
        className="grid min-h-12 grid-cols-[4rem_3.5rem_minmax(0,1fr)_5.5rem_minmax(14rem,18rem)] items-center gap-3 rounded-panel px-3 py-2 transition-colors duration-(--dur-quick) hover:bg-surface-2"
      >
        <span className="num font-mono text-body">{event.all_day ? "All day" : event.uk_time}</span>
        <CurrencyTag currency={event.currency} />
        <span className="line-clamp-2 min-w-0 text-body" style={{ viewTransitionName: vtName("event", event.id) }}>
          {event.name}
        </span>
        <ImpactChip impact={event.impact} compact />
        <Figures event={event} />
      </Link>
    </li>
  );
}

/** Events grouped by UK date, then by time (the phone shows a list grouped by time). */
export function EventGroups({ events, compact, showDayHeadings }: { events: NewsEvent[]; compact: boolean; showDayHeadings: boolean }) {
  const byDay = new Map<string, NewsEvent[]>();
  for (const e of events) byDay.set(e.uk_date, [...(byDay.get(e.uk_date) ?? []), e]);
  return (
    <div className="flex flex-col gap-6">
      {[...byDay.entries()].map(([day, list]) => {
        const byTime = new Map<string, NewsEvent[]>();
        for (const e of list) {
          const key = e.all_day ? "All day" : e.uk_time;
          byTime.set(key, [...(byTime.get(key) ?? []), e]);
        }
        return (
          <section key={day} aria-label={dayLabel(day)}>
            {showDayHeadings ? <h3 className="mb-2 text-body font-semibold">{dayLabel(day)}</h3> : null}
            {compact ? (
              <div className="flex flex-col gap-4">
                {[...byTime.entries()].map(([time, group]) => (
                  <div key={time} className="grid grid-cols-[3.25rem_minmax(0,1fr)] gap-3">
                    <p className="num pt-3 font-mono text-body text-muted">{time}</p>
                    <ul className="flex flex-col gap-2">
                      {group.map((e) => (
                        <EventRow key={e.id} event={e} compact />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {list.map((e) => (
                  <EventRow key={e.id} event={e} compact={false} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

export { CURRENCIES, Switch, ToggleChip };
