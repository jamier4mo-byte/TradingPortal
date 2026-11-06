import { StatTile } from "../../../components/ui/index.ts";
import { fmtDuration, fmtR, type Profile } from "../../../lib/journal.ts";

function Bars({ items, label }: { items: { label: string; count: number }[]; label: string }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  if (!items.length) return <p className="text-label text-muted">Nothing noted yet</p>;
  return (
    <ul className="flex flex-col gap-1.5" aria-label={label}>
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-label">
          <span className="flex items-center gap-2">
            <span className="truncate">{i.label}</span>
            <span className="h-1.5 flex-1 rounded-pill bg-surface-2">
              <span className="block h-full rounded-pill bg-accent" style={{ width: `${(i.count / max) * 100}%` }} />
            </span>
          </span>
          <span className="num text-muted">{i.count}</span>
        </li>
      ))}
    </ul>
  );
}

/** The strategy profile (2.2): what a typical winner looks like. */
export function StrategyProfile({ profile, unit = "pts" }: { profile: Profile; unit?: string }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-2 tablet:grid-cols-4">
        <StatTile label="Average stop" value={profile.avg_sl_distance ?? "—"} unit={unit} />
        <StatTile label="Average target" value={profile.avg_tp_distance ?? "—"} unit={unit} hint={profile.avg_tp_r ? `${profile.avg_tp_r.toFixed(1)}R` : undefined} />
        <StatTile label="Average R" value={fmtR(profile.avg_r)} tone={(profile.avg_r ?? 0) > 0 ? "win" : "neutral"} />
        <StatTile label="Typical hold" value={fmtDuration(profile.typical_duration_seconds)} />
      </div>
      <div className="grid gap-4 tablet:grid-cols-2 desktop:grid-cols-4">
        <section>
          <h3 className="mb-2 text-label text-muted">Entry times (UK)</h3>
          <Bars items={profile.entry_hours} label="Entry hours" />
        </section>
        <section>
          <h3 className="mb-2 text-label text-muted">Sessions</h3>
          <Bars items={profile.sessions} label="Sessions" />
        </section>
        <section>
          <h3 className="mb-2 text-label text-muted">Entry models</h3>
          <Bars items={profile.entry_models} label="Entry models" />
        </section>
        <section>
          <h3 className="mb-2 text-label text-muted">Days of the week</h3>
          <Bars items={profile.weekdays} label="Weekdays" />
        </section>
        <section>
          <h3 className="mb-2 text-label text-muted">Tags</h3>
          <Bars items={profile.tags} label="Tags" />
        </section>
        <section>
          <h3 className="mb-2 text-label text-muted">Confluences</h3>
          <Bars items={profile.confluences} label="Confluences" />
        </section>
      </div>
    </div>
  );
}
