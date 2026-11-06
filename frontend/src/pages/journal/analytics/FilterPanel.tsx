import { ArrowDownRight, ArrowUpRight, Check, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { ownerBg } from "../../../components/ui/index.ts";
import { activeFilterCount, type AnalyticsResult, type Filters, type Source, WEEKDAYS } from "../../../lib/analytics.ts";

function toggle<T>(list: T[], v: T): T[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

function ChipToggle({ on, onClick, children, label }: { on: boolean; onClick: () => void; children: ReactNode; label?: string }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={label}
      onClick={onClick}
      className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-pill border px-3 text-body transition-colors duration-(--dur-quick) ${
        on ? "border-accent bg-accent-soft text-text" : "border-border bg-surface-2 text-muted hover:text-text"
      }`}
    >
      {on ? <Check aria-hidden className="size-3.5" strokeWidth={2.5} /> : null}
      {children}
    </button>
  );
}

function Group({ title, children, note }: { title: string; children: ReactNode; note?: ReactNode }) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="mb-2 text-label font-medium text-muted">{title}</legend>
      <div className="flex flex-wrap gap-1.5">{children}</div>
      {note ? <p className="text-label text-muted">{note}</p> : null}
    </fieldset>
  );
}

function shiftMonths(iso: string, months: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

/** Every 2.4 filter. Changes apply at once and land in the URL, so a view can be bookmarked or shared. */
export function FilterPanel({ filters, onChange, onClear, options, source, newsStatus, showOwners }: { filters: Filters; onChange: (f: Filters) => void; onClear: () => void; options: AnalyticsResult["options"] | undefined; source: Source; newsStatus: "ok" | "no_data" | undefined; showOwners: boolean }) {
  const f = filters;
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const max = options?.date_max ?? null;
  const presets: { label: string; from?: string }[] = [{ label: "All" }];
  if (max) presets.push({ label: "Last 3 months", from: shiftMonths(max, 3) }, { label: "Last 6 months", from: shiftMonths(max, 6) }, { label: "Last 12 months", from: shiftMonths(max, 12) });
  const presetOn = (p: { from?: string }) => (p.from ? f.date_from === p.from && !f.date_to : !f.date_from && !f.date_to);

  return (
    <div className="flex flex-col gap-5" data-testid="filters">
      <div className="flex items-center justify-between gap-2">
        <p className="num text-label text-muted">{activeFilterCount(f) ? `${activeFilterCount(f)} active` : "No filters"}</p>
        <button type="button" className="btn btn-ghost -mr-2" onClick={onClear} disabled={!activeFilterCount(f)}>
          Clear all
        </button>
      </div>

      <Group title="Date range (UK date of the open)">
        {presets.map((p) => (
          <ChipToggle key={p.label} on={presetOn(p)} onClick={() => set({ date_from: p.from, date_to: undefined })}>
            {p.label}
          </ChipToggle>
        ))}
        <div className="grid w-full grid-cols-2 gap-2 pt-1">
          <label className="flex flex-col gap-1 text-label text-muted">
            From
            <input type="date" className="input num min-h-11" value={f.date_from ?? ""} min={options?.date_min ?? undefined} max={max ?? undefined} onChange={(e) => set({ date_from: e.target.value || undefined })} />
          </label>
          <label className="flex flex-col gap-1 text-label text-muted">
            To
            <input type="date" className="input num min-h-11" value={f.date_to ?? ""} min={options?.date_min ?? undefined} max={max ?? undefined} onChange={(e) => set({ date_to: e.target.value || undefined })} />
          </label>
        </div>
      </Group>

      {options && options.instruments.length > 1 ? (
        <Group title="Instrument">
          {options.instruments.map((i) => (
            <ChipToggle key={i} on={f.instruments.includes(i)} onClick={() => set({ instruments: toggle(f.instruments, i) })}>
              <span className="font-mono">{i}</span>
            </ChipToggle>
          ))}
        </Group>
      ) : null}

      <Group title="Session (UK)">
        {(options?.sessions.length ? options.sessions : ["Asia", "London", "New York"]).map((s) => (
          <ChipToggle key={s} on={f.sessions.includes(s)} onClick={() => set({ sessions: toggle(f.sessions, s) })}>
            {s}
          </ChipToggle>
        ))}
      </Group>

      <Group title="Entry time window (UK)" note="A window that ends before it starts wraps midnight.">
        <div className="grid w-full grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-label text-muted">
            From
            <input type="time" className="input num min-h-11" value={f.time_from ?? ""} onChange={(e) => set({ time_from: e.target.value || undefined })} />
          </label>
          <label className="flex flex-col gap-1 text-label text-muted">
            To
            <input type="time" className="input num min-h-11" value={f.time_to ?? ""} onChange={(e) => set({ time_to: e.target.value || undefined })} />
          </label>
        </div>
      </Group>

      <Group title="Day of week">
        {WEEKDAYS.slice(0, 5).map((d, i) => (
          <ChipToggle key={d} on={f.weekdays.includes(i)} onClick={() => set({ weekdays: toggle(f.weekdays, i) })}>
            {d}
          </ChipToggle>
        ))}
      </Group>

      {options?.entry_models.length ? (
        <Group title="Entry model">
          {options.entry_models.map((m) => (
            <ChipToggle key={m} on={f.entry_models.includes(m)} onClick={() => set({ entry_models: toggle(f.entry_models, m) })}>
              {m}
            </ChipToggle>
          ))}
        </Group>
      ) : null}

      <Group title="Direction">
        <ChipToggle on={f.directions.includes("buy")} onClick={() => set({ directions: toggle(f.directions, "buy" as const) })}>
          Long
        </ChipToggle>
        <ChipToggle on={f.directions.includes("sell")} onClick={() => set({ directions: toggle(f.directions, "sell" as const) })}>
          Short
        </ChipToggle>
      </Group>

      {options?.tags.length ? (
        <Group title="Tags" note="Synonyms count: FVG also finds “fair value gap”.">
          {options.tags.slice(0, 24).map((t) => (
            <ChipToggle key={t} on={f.tags.includes(t)} onClick={() => set({ tags: toggle(f.tags, t) })}>
              {t}
            </ChipToggle>
          ))}
        </Group>
      ) : null}

      {source !== "ideal" ? (
        <Group title="Outcome (backtest)">
          <ChipToggle on={f.outcomes.includes("win")} onClick={() => set({ outcomes: toggle(f.outcomes, "win" as const) })}>
            <ArrowUpRight aria-hidden className="size-4 text-win" /> Wins
          </ChipToggle>
          <ChipToggle on={f.outcomes.includes("loss")} onClick={() => set({ outcomes: toggle(f.outcomes, "loss" as const) })}>
            <ArrowDownRight aria-hidden className="size-4 text-loss" /> Losses
          </ChipToggle>
          <ChipToggle on={f.outcomes.includes("breakeven")} onClick={() => set({ outcomes: toggle(f.outcomes, "breakeven" as const) })}>
            <Minus aria-hidden className="size-4 text-breakeven" /> Breakevens
          </ChipToggle>
        </Group>
      ) : null}

      {showOwners && options && options.owners.length > 1 ? (
        <Group title="Logged by">
          {options.owners.map((o) => (
            <ChipToggle key={o.id} on={f.owners.includes(o.id)} onClick={() => set({ owners: toggle(f.owners, o.id) })}>
              <span aria-hidden className={`size-2 rounded-full ${ownerBg(o.colour_index)}`} /> {o.display_name}
            </ChipToggle>
          ))}
        </Group>
      ) : null}

      {source !== "ideal" ? (
        <Group title="Rulebook">
          <ChipToggle on={f.rules === "all_kept"} onClick={() => set({ rules: f.rules === "all_kept" ? undefined : "all_kept" })}>
            All rules kept
          </ChipToggle>
          <ChipToggle on={f.rules === "any_broken"} onClick={() => set({ rules: f.rules === "any_broken" ? undefined : "any_broken" })}>
            Any rule broken
          </ChipToggle>
        </Group>
      ) : null}

      <Group title="News" note={newsStatus === "no_data" ? "No news data yet: the News Room fills this in later, so this filter doesn't change anything." : undefined}>
        <ChipToggle on={f.news === "inside"} onClick={() => set({ news: f.news === "inside" ? undefined : "inside" })}>
          Inside a news window
        </ChipToggle>
        <ChipToggle on={f.news === "outside"} onClick={() => set({ news: f.news === "outside" ? undefined : "outside" })}>
          Outside
        </ChipToggle>
      </Group>
    </div>
  );
}
