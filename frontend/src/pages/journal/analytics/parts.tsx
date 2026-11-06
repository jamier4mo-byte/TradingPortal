import { AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, Lightbulb, Minus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../../components/Card.tsx";
import { CountUp } from "../../../components/ui/CountUp.tsx";
import { Chip } from "../../../components/ui/index.ts";
import { fmtMetric, type Insight, type Kpis, type MetricMeta, type Reconcile, toneOf, type TradeLine } from "../../../lib/analytics.ts";
import { fmtPnl, fmtR, fmtUkDateTime } from "../../../lib/journal.ts";

const TONE_TEXT = { win: "text-win", loss: "text-loss", breakeven: "text-breakeven", neutral: "" } as const;

/** Signed metrics (R, $) get the reserved colour *and* an arrow; colour is never the only signal. */
export function KpiTile({ meta, value, signed = false, className = "" }: { meta: MetricMeta | undefined; value: number | null | undefined; signed?: boolean; className?: string }) {
  const [open, setOpen] = useState(false);
  if (!meta) return null;
  const tone = signed ? toneOf(value) : "neutral";
  const Icon = tone === "win" ? ArrowUpRight : tone === "loss" ? ArrowDownRight : null;
  return (
    <div className={`flex min-w-0 flex-col rounded-panel border border-border bg-surface-2 p-3 ${className}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-label text-muted">{meta.label}</p>
        <button
          type="button"
          aria-expanded={open}
          aria-label={`How ${meta.label.toLowerCase()} is worked out`}
          onClick={() => setOpen((v) => !v)}
          className="-mt-3 -mr-3 grid size-11 shrink-0 place-items-center rounded-pill text-subtle hover:text-text"
        >
          <span aria-hidden className="grid size-4 place-items-center rounded-full border border-current text-[11px] leading-none font-semibold">
            i
          </span>
        </button>
      </div>
      <p className={`num mt-0.5 flex items-center gap-1 text-heading leading-none font-semibold ${TONE_TEXT[tone]}`}>
        {Icon ? <Icon aria-hidden className="size-5 shrink-0" strokeWidth={2} /> : null}
        <CountUp value={value} format={(v) => fmtMetric(meta.unit, v)} />
      </p>
      {open ? <p className="mt-2 text-label text-muted">{meta.formula}</p> : null}
    </div>
  );
}

const STRIP_COLS: Record<number, string> = { 3: "tablet:grid-cols-3", 4: "tablet:grid-cols-4", 5: "tablet:grid-cols-3 laptop:grid-cols-5" };

export function KpiStrip({ ids, kpis, meta, signed = [], phoneHidden = [] }: { ids: string[]; kpis: Kpis; meta: Record<string, MetricMeta>; signed?: string[]; phoneHidden?: string[] }) {
  return (
    <div className={`grid grid-cols-2 gap-2 ${STRIP_COLS[Math.min(Math.max(ids.length, 3), 5)]}`}>
      {ids.map((id) => (
        <KpiTile key={id} meta={meta[id]} value={kpis[id]} signed={signed.includes(id)} className={phoneHidden.includes(id) ? "hidden tablet:flex" : ""} />
      ))}
    </div>
  );
}

/** Every metric in the registry with its value and formula: nothing hides behind a tooltip. */
export function AllMetrics({ kpis, registry }: { kpis: Kpis; registry: MetricMeta[] }) {
  const rows = registry.filter((m) => m.id in kpis);
  return (
    <dl className="grid gap-x-6 tablet:grid-cols-2">
      {rows.map((m) => (
        <div key={m.id} className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 gap-y-0.5 border-t border-border py-2.5">
          <dt className="text-body">{m.label}</dt>
          <dd className="num text-body font-medium">{fmtMetric(m.unit, kpis[m.id])}</dd>
          <dd className="col-span-2 text-label text-muted">{m.formula}</dd>
        </div>
      ))}
    </dl>
  );
}

export function InsightsCard({ insights, title = "Auto-insights", subtitle = "Top differences from this strategy's baseline. Slices need 8 trades; under 20 is an early signal." }: { insights: Insight[]; title?: string; subtitle?: string }) {
  return (
    <Card title={title} subtitle={subtitle}>
      {insights.length ? (
        <ul className="flex flex-col gap-2">
          {insights.map((i) => (
            <li key={`${i.dimension}-${i.key}`} className="flex items-start gap-3 rounded-panel border border-border bg-surface-2 px-3 py-2.5">
              <Lightbulb aria-hidden className="mt-0.5 size-4 shrink-0 text-subtle" strokeWidth={1.75} />
              <span className="num min-w-0 flex-1 text-body">{i.text.replace(" · early signal", "")}</span>
              {i.early ? <Chip className="shrink-0">Early signal</Chip> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body text-muted">Nothing stands out yet. Insights appear once a slice (a weekday, session, entry model…) has at least 8 trades and differs by 15% or more.</p>
      )}
    </Card>
  );
}

/** "Reconciled with FX Replay ✓" per imported session, or exactly what's off. */
export function ReconcileLine({ items }: { items: Reconcile[] }) {
  if (!items.length) return null;
  const allOk = items.every((r) => r.ok);
  const app = items.reduce((a, r) => ({ trades: a.trades + r.app.trades, pnl: a.pnl + r.app.pnl }), { trades: 0, pnl: 0 });
  return (
    <details className="group rounded-panel border border-border bg-surface-1 px-3 text-body" data-testid="reconcile">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2">
        {allOk ? <CheckCircle2 aria-hidden className="size-4 shrink-0 text-muted" strokeWidth={1.75} /> : <AlertTriangle aria-hidden className="size-4 shrink-0 text-text" strokeWidth={1.75} />}
        <span className="num min-w-0 flex-1">
          {allOk ? (
            <>
              Reconciled with FX Replay <span aria-hidden>✓</span>
              <span className="sr-only">(matches)</span>
              <span className="text-muted"> · {app.trades} trades · {fmtPnl(app.pnl)} across {items.length} {items.length === 1 ? "import" : "imports"}</span>
            </>
          ) : (
            <>
              <b>Doesn&rsquo;t match FX Replay</b>
              <span className="text-muted"> · {items.filter((r) => !r.ok).length} of {items.length} imports differ</span>
            </>
          )}
        </span>
        <span className="text-label text-muted group-open:hidden">Details</span>
      </summary>
      <ul className="flex flex-col gap-2 pb-3">
        {items.map((r) => (
          <li key={r.session_id} className="num rounded-panel border border-border bg-surface-2 px-3 py-2 text-label">
            <p className="text-body">
              {r.ok ? "✓" : "✗"} {r.filename ?? "Import"} <span className="text-muted">({r.kind})</span>
            </p>
            <p className="text-muted">
              CSV {r.csv ? `${r.csv.trades} rows · Σ rPnL ${fmtPnl(r.csv.rpnl_sum)}` : "totals not stored"} · kept {r.kept.trades} · {fmtPnl(r.kept.rpnl_sum)} · in the app {r.app.trades} · {fmtPnl(r.app.pnl)}
              {!r.ok ? ` · off by ${r.diff_trades} trades, ${fmtPnl(r.diff_pnl)}` : ""}
            </p>
            {r.notes.map((n) => (
              <p key={n} className="text-muted">
                {n}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function OutcomeMark({ outcome }: { outcome: TradeLine["outcome"] }) {
  if (outcome === "win") return <ArrowUpRight aria-label="Win" className="size-4 text-win" strokeWidth={2} />;
  if (outcome === "loss") return <ArrowDownRight aria-label="Loss" className="size-4 text-loss" strokeWidth={2} />;
  return <Minus aria-label="Breakeven" className="size-4 text-breakeven" strokeWidth={2} />;
}

/** The filtered trades, newest first: links to each trade's detail. */
export function TradeMiniList({ trades, total, limit = 40 }: { trades: TradeLine[]; total: number; limit?: number }) {
  const [shown, setShown] = useState(limit);
  if (!trades.length) return <p className="text-body text-muted">No trades in this filter.</p>;
  return (
    <div className="flex flex-col">
      <ul className="flex flex-col">
        {trades.slice(0, shown).map((t) => (
          <li key={t.id} className="border-t border-border first:border-t-0">
            <Link to={`/journal/strategies/${t.strategy_id}/trades/${t.id}`} className="flex min-h-11 items-center gap-2 rounded-panel px-1.5 py-1.5 hover:bg-surface-2">
              <OutcomeMark outcome={t.outcome} />
              <span className="min-w-0 flex-1">
                <span className="num block truncate text-body">{fmtUkDateTime(t.opened_at)}</span>
                <span className="block truncate text-label text-muted">
                  {t.side === "buy" ? "Long" : "Short"} {t.instrument} · {t.entry_model ?? "—"} · {t.session_label || "—"}
                </span>
              </span>
              <span className={`num text-body font-medium ${TONE_TEXT[t.outcome ?? "neutral"]}`}>{fmtR(t.r)}</span>
            </Link>
          </li>
        ))}
      </ul>
      {total > shown ? (
        <button type="button" className="btn btn-ghost mt-2" onClick={() => setShown((s) => s + limit)}>
          Show more <span className="num text-muted">({Math.min(trades.length, total) - shown} more)</span>
        </button>
      ) : null}
    </div>
  );
}
