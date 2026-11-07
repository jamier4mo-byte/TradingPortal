import { useState } from "react";

import Card from "../../components/Card.tsx";
import type { OwnerSplit } from "../../lib/analytics.ts";
import { OwnersCard } from "../journal/analytics/BacktestViews.tsx";
import { ChartEmpty, KeyEmpty, ListEmpty, PeopleEmpty } from "../../components/ui/Illustrations.tsx";
import { Copy } from "lucide-react";

import { Chip, ConfirmDialog, Drawer, EmptyState, ErrorState, OfflineBanner, OwnerChip, PillToggle, ReadOnlyBanner, RingGauge, Skeleton, SkeletonCard, SkeletonText, StatTile, useToast, ViewScopeToggle } from "../../components/ui/index.ts";
import { Checkbox } from "../../components/ui/Checkbox.tsx";
import { MorphIcon } from "../../components/ui/MorphIcon.tsx";

/** Hidden gallery of every shared component, in every state. Used by e2e and the design reviewer. */
export default function Components() {
  const { toast } = useToast();
  const [pill, setPill] = useState<"ideal" | "backtest" | "compare">("ideal");
  const [drawer, setDrawer] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [ticked, setTicked] = useState(true);
  const [copied, setCopied] = useState(false);

  return (
    <div className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12 laptop:gap-6">
      <Card title="Skeleton" subtitle="Loading state: shape of the content, faint shimmer" className="col-span-full laptop:col-span-6">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-40" />
          <SkeletonText />
          <SkeletonCard />
        </div>
      </Card>
      <Card title="Banners" subtitle="Read-only and offline" className="col-span-full laptop:col-span-6">
        <div className="flex flex-col gap-3">
          <ReadOnlyBanner owner="Sam" what="strategy" />
          <OfflineBanner />
        </div>
      </Card>

      <Card title="Empty states" subtitle="A line illustration and one next step" className="col-span-full laptop:col-span-6">
        <div className="grid gap-2 tablet:grid-cols-2">
          <EmptyState title="No ideal trades yet" text="Log your first winner." action={<button type="button" className="btn btn-primary">Log a trade</button>} />
          <EmptyState illustration={<ListEmpty />} title="No tasks this week" text="Add one to the calendar." />
          <EmptyState illustration={<PeopleEmpty />} title="Just you so far" text="Invite a mate." />
          <EmptyState illustration={<KeyEmpty />} title="No API key" text="Paste your Twelve Data key." />
        </div>
      </Card>
      <Card title="Error state" subtitle="What went wrong and how to fix it" className="col-span-full laptop:col-span-6">
        <ErrorState title="Prices didn't load" text="Twelve Data didn't answer. The last known prices are shown." onRetry={() => toast({ title: "Retrying" })} />
      </Card>

      <Card title="Toast" subtitle="Quiet, from the corner, with undo" className="col-span-full tablet:col-span-4">
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => toast({ title: "Task marked done", undo: () => toast({ title: "Undone" }) })}>
            With undo
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => toast({ title: "8 trades imported", tone: "win" })}>
            Positive
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => toast({ title: "Save failed", text: "You're offline.", tone: "loss" })}>
            Problem
          </button>
        </div>
      </Card>
      <Card title="Dialogs" subtitle="Confirm and drawer / bottom sheet" className="col-span-full tablet:col-span-4">
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => setConfirm(true)}>
            Confirm dialog
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setDrawer(true)}>
            Drawer
          </button>
        </div>
        <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Delete this trade?" text="It moves to Trash for 30 days." confirmLabel="Delete" danger onConfirm={() => setConfirm(false)} />
        <Drawer open={drawer} onOpenChange={setDrawer} title="New ideal trade" description="Right side on desktop, bottom sheet on the phone.">
          <SkeletonText lines={5} />
        </Drawer>
      </Card>
      <Card title="Toggles" subtitle="Sliding indicator and the view scope in the URL" className="col-span-full tablet:col-span-8 laptop:col-span-4">
        <div className="flex flex-col gap-3">
          <PillToggle
            label="Data source"
            value={pill}
            onChange={setPill}
            options={[
              { value: "ideal", label: "Ideal" },
              { value: "backtest", label: "Backtest" },
              { value: "compare", label: "Compare" },
            ]}
          />
          <ViewScopeToggle />
        </div>
      </Card>

      <Card title="Checkbox and morphing icon" subtitle="Ticks draw themselves in; copy icons become a tick" className="col-span-full laptop:col-span-6">
        <div className="flex flex-wrap items-center gap-6">
          <label className="flex min-h-11 cursor-pointer items-center gap-3">
            <Checkbox checked={ticked} onChange={setTicked} />
            <span className="text-body">Rule followed</span>
          </label>
          <label className="flex min-h-11 items-center gap-3">
            <Checkbox checked disabled onChange={() => undefined} />
            <span className="text-body text-muted">Read-only</span>
          </label>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1500);
            }}
          >
            <MorphIcon done={copied} Icon={Copy} /> {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </Card>

      <Card title="Chips and owners" subtitle="Colour is never the only signal" className="col-span-full laptop:col-span-6">
        <div className="flex flex-wrap gap-2">
          <Chip dot dotClass="bg-impact-high">High</Chip>
          <Chip dot dotClass="bg-impact-medium">Med</Chip>
          <Chip dot dotClass="bg-impact-low">Low</Chip>
          <Chip dot dotClass="bg-live">Live</Chip>
          <Chip dot dotClass="bg-stale">Stale</Chip>
          <Chip onRemove={() => toast({ title: "Removed FVG" })}>FVG</Chip>
          <Chip>London killzone</Chip>
        </div>
        <div className="mt-4 flex flex-wrap gap-4">
          {["Jamie", "Sam", "Alex", "Rob", "Chris", "Dan", "Lee", "Tom"].map((n, i) => (
            <OwnerChip key={n} name={n} colourIndex={i} deactivated={i === 3} />
          ))}
        </div>
      </Card>
      <Card title="Stat tiles and gauges" subtitle="Tabular figures everywhere" className="col-span-full laptop:col-span-6">
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <StatTile label="Win rate" value="62.5" unit="%" />
          <StatTile label="Total R" value="+18.4" unit="R" tone="win" />
          <StatTile label="Max drawdown" value="−6.2" unit="R" tone="loss" />
          <StatTile label="Breakeven" value="3" tone="breakeven" hint="±$10" />
        </div>
        <div className="mt-4 flex flex-wrap gap-6">
          <RingGauge value={62.5} label="Win rate" />
          <RingGauge value={4} max={6} label="Coverage" display="4/6" tone="win" />
          <RingGauge value={14} max={15} label="Countdown" display="14m" tone="impact-high" size={72} />
        </div>
      </Card>
      <div className="col-span-full">
        <OwnersCard owners={SAMPLE_OWNERS} />
      </div>
      <Card title="Illustrations" subtitle="Inline SVG, 1.5px strokes" className="col-span-full">
        <div className="grid grid-cols-2 gap-4 text-muted tablet:grid-cols-4">
          <ChartEmpty />
          <ListEmpty />
          <PeopleEmpty />
          <KeyEmpty />
        </div>
      </Card>
    </div>
  );
}

/** Four owners: more than three, so the owner split switches to small multiples (F12). */
const SAMPLE_OWNERS: OwnerSplit[] = ["Jamie", "Sam", "Alex", "Priya"].map((name, i) => {
  let total = 0;
  const equity = Array.from({ length: 24 }, (_, k) => (total = Math.round((total + (((k * (i + 3)) % 5) - 1.6) * 0.8) * 100) / 100));
  return {
    owner: { id: i + 1, display_name: name, colour_index: i, status: "active" },
    kpis: { trades: 24, win_rate: 0.4 + i * 0.05, total_r: equity[equity.length - 1], avg_r: null, profit_factor: null, max_dd_r: null, net_pnl: null },
    equity,
  };
});
