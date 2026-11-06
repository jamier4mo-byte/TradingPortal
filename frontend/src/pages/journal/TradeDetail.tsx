import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ClipboardList, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { Chip, ConfirmDialog, ErrorState, OwnerChip, ReadOnlyBanner, SkeletonCard, useToast } from "../../components/ui/index.ts";
import { api } from "../../lib/api.ts";
import { fmtDuration, fmtPnl, fmtPrice, fmtR, fmtUkDateTime, isCompleted, LABELLED_SLOTS, missingForCompletion, SLOT_LABEL, type Trade, useInvalidateJournal, useStrategy, useTrade, useUpdateTrade } from "../../lib/journal.ts";
import { useState } from "react";
import { CompleteDialog } from "./components/CompleteDialog.tsx";
import { Gallery } from "./components/Gallery.tsx";
import { OutcomeChip, SideChip } from "./components/OutcomeChip.tsx";
import { ScreenshotSlot } from "./components/ScreenshotSlot.tsx";

/** Trade detail: gallery first, then the facts, reasoning, rules and tags. */
export default function TradeDetail() {
  const { id, tradeId } = useParams();
  const trade = useTrade(Number(tradeId));
  const strategy = useStrategy(Number(id));
  if (trade.isPending) return <SkeletonCard />;
  if (trade.isError) return <ErrorState title="Trade didn't load" text={trade.error.message} onRetry={() => trade.refetch()} />;
  return <Detail trade={trade.data} templateFields={strategy.data?.reasoning_template ?? []} rules={strategy.data?.rules ?? []} />;
}

function Detail({ trade: t, templateFields, rules }: { trade: Trade; templateFields: { key: string; label: string }[]; rules: { key: string; text: string }[] }) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const [deleting, setDeleting] = useState(false);
  const [current, setCurrent] = useState(t);
  if (current.id !== t.id || current.updated_at < t.updated_at) setCurrent(t);
  const update = useUpdateTrade();
  const [missing, setMissing] = useState<string[] | null>(null);
  const markCompleted = (value: boolean) => update.mutate({ id: current.id, body: { annotated: value } }, { onSuccess: setCurrent });
  const toggleCompleted = () => {
    if (isCompleted(current)) return markCompleted(false);
    const gaps = missingForCompletion(current);
    if (gaps.length) return setMissing(gaps); // warn, never restrict
    markCompleted(true);
  };
  const del = useMutation({
    mutationFn: () => api.delete(`/api/trades/${t.id}`),
    onSuccess: () => {
      invalidate(t.strategy_id);
      toast({
        title: "Trade moved to Trash",
        undo: async () => {
          await api.post(`/api/trades/${t.id}/restore`);
          invalidate(t.strategy_id);
          toast({ title: "Trade restored" });
        },
      });
      navigate(`/journal/strategies/${t.strategy_id}${t.kind === "backtest" ? "?tab=backtest" : ""}`);
    },
  });
  const reasonEntries = templateFields.length ? templateFields.map((f) => ({ ...f, value: current.reasoning?.[f.key] ?? "" })) : Object.entries(current.reasoning ?? {}).map(([key, value]) => ({ key, label: key, value }));
  const hasAnyReason = reasonEntries.some((r) => String(r.value).trim()) || current.notes.trim();

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-3">
        <Link to={`/journal/strategies/${t.strategy_id}${t.kind === "backtest" ? "?tab=backtest" : ""}`} className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text">
          <ArrowLeft aria-hidden className="size-4" /> Back to the strategy
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-heading font-semibold">{current.instrument}</h1>
          <SideChip side={current.side} />
          {current.kind === "backtest" ? <OutcomeChip outcome={current.outcome} /> : <Chip>{current.kind === "missed" ? "Missed setup" : "Ideal trade"}</Chip>}
          {isCompleted(current) ? (
            <Chip dot dotClass="bg-accent">
              Completed
            </Chip>
          ) : null}
          <span className="num text-body text-muted">{fmtUkDateTime(current.opened_at)} UK</span>
          <OwnerChip name={current.owner.display_name} colourIndex={current.owner.colour_index} compact />
          {current.can_edit ? (
            <div className="ml-auto flex items-center gap-2">
              <button type="button" className={`btn ${isCompleted(current) ? "btn-ghost" : "btn-secondary"}`} onClick={toggleCompleted} disabled={update.isPending} aria-pressed={isCompleted(current)}>
                <CheckCircle2 aria-hidden className="size-4" /> {isCompleted(current) ? "Completed" : "Mark completed"}
              </button>
              {current.session_id ? (
                <Link to={`/journal/sessions/${current.session_id}/annotate?trade=${current.id}`} className="btn btn-secondary">
                  <ClipboardList aria-hidden className="size-4" /> Annotate
                </Link>
              ) : null}
              <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Delete trade" onClick={() => setDeleting(true)}>
                <Trash2 aria-hidden className="size-4" />
              </button>
            </div>
          ) : null}
        </div>
        {!current.can_edit ? <ReadOnlyBanner owner={current.owner.display_name} what="trade" /> : null}
      </header>

      <Card title="Screenshots" subtitle="Swipe between them; tap to zoom">
        <Gallery shots={current.screenshots} />
        {current.can_edit ? (
          <div className="mt-4 grid grid-cols-2 gap-3 tablet:grid-cols-4">
            {current.kind === "missed" ? (
              <ScreenshotSlot trade={current} slot="entry" shot={current.screenshots.find((s) => s.slot === "entry")} label="The setup" onChange={setCurrent} />
            ) : (
              LABELLED_SLOTS.map((slot) => (
                <ScreenshotSlot key={slot} trade={current} slot={slot} shot={current.screenshots.find((s) => s.slot === slot)} label={SLOT_LABEL[slot]} onChange={setCurrent} />
              ))
            )}
            {current.screenshots.filter((s) => s.slot === "extra").length < 3 ? <ScreenshotSlot trade={current} slot="extra" label="Extra" onChange={setCurrent} /> : null}
          </div>
        ) : null}
      </Card>

      <div className="grid gap-4 laptop:grid-cols-2 laptop:gap-6">
        <Card title="The trade" subtitle={`${current.session_label} session`}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-body tablet:grid-cols-3">
            <Fact label="Entry" value={fmtPrice(current.entry_price)} />
            <Fact label="Stop" value={fmtPrice(current.initial_sl)} hint={current.sl_distance !== null ? `${current.sl_distance}` : undefined} />
            <Fact label="Target" value={fmtPrice(current.max_tp)} hint={current.tp_r ? `${current.tp_distance} · ${current.tp_r.toFixed(1)}R` : undefined} />
            <Fact label="Exit" value={fmtPrice(current.exit_price)} />
            <Fact label="R" value={fmtR(current.r_multiple)} tone={(current.r_multiple ?? 0) > 0 ? "win" : (current.r_multiple ?? 0) < 0 ? "loss" : undefined} />
            {current.kind === "backtest" ? <Fact label="P&L" value={fmtPnl(current.pnl)} tone={(current.pnl ?? 0) > 0 ? "win" : (current.pnl ?? 0) < 0 ? "loss" : undefined} /> : null}
            <Fact label="Held" value={fmtDuration(current.duration_seconds)} />
            <Fact label="Closed" value={fmtUkDateTime(current.closed_at)} />
            <Fact label="Entry model" value={current.entry_model ?? "—"} />
            {current.mae_r !== null || current.mfe_r !== null ? <Fact label="MAE / MFE" value={`${fmtR(current.mae_r, false)} / ${fmtR(current.mfe_r, false)}`} /> : null}
            {current.fx_id ? <Fact label="FX Replay id" value={current.fx_id} mono /> : null}
          </dl>
          {current.tags.length ? (
            <div className="mt-4 flex flex-wrap gap-1.5" aria-label="Tags">
              {current.tags.map((tag) => (
                <Chip key={tag.id} dot dotClass="bg-accent">
                  {tag.name}
                </Chip>
              ))}
            </div>
          ) : null}
        </Card>
        <Card title="Reasoning" subtitle={hasAnyReason ? "From Annotate mode" : "Not written yet"}>
          {hasAnyReason ? (
            <dl className="flex flex-col gap-3 text-body">
              {reasonEntries
                .filter((r) => String(r.value).trim())
                .map((r) => (
                  <div key={r.key}>
                    <dt className="text-label text-muted">{r.label}</dt>
                    <dd className="whitespace-pre-wrap">{r.value}</dd>
                  </div>
                ))}
              {current.notes.trim() ? (
                <div>
                  <dt className="text-label text-muted">Notes</dt>
                  <dd className="whitespace-pre-wrap">{current.notes}</dd>
                </div>
              ) : null}
            </dl>
          ) : (
            <p className="text-body text-muted">{current.can_edit && current.session_id ? "Open Annotate mode to fill the template." : "No reasoning recorded."}</p>
          )}
          {rules.length && Object.keys(current.rules_followed ?? {}).length ? (
            <ul className="mt-4 flex flex-col gap-1.5" aria-label="Rules followed">
              {rules.map((r) => {
                const ok = current.rules_followed?.[r.key];
                return (
                  <li key={r.key} className={`flex items-start gap-2 text-body ${ok === undefined ? "text-muted" : ""}`}>
                    <span aria-hidden className="num w-4 shrink-0">{ok === false ? "✕" : ok ? "✓" : "–"}</span>
                    <span>
                      <span className="sr-only">{ok === false ? "Broken: " : ok ? "Followed: " : "Not checked: "}</span>
                      {r.text}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </Card>
      </div>

      <CompleteDialog
        missing={missing}
        busy={update.isPending}
        onCancel={() => setMissing(null)}
        onConfirm={() => {
          setMissing(null);
          markCompleted(true);
        }}
      />
      <ConfirmDialog open={deleting} onOpenChange={setDeleting} title="Move this trade to Trash?" text="It can be restored for 30 days." confirmLabel="Move to Trash" danger busy={del.isPending} onConfirm={() => del.mutate()} />
    </div>
  );
}

function Fact({ label, value, hint, tone, mono }: { label: string; value: string; hint?: string; tone?: "win" | "loss"; mono?: boolean }) {
  return (
    <div>
      <dt className="text-label text-muted">{label}</dt>
      <dd className={`num ${mono ? "font-mono" : ""} ${tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : ""}`}>
        {value}
        {hint ? <span className="ml-1 text-label text-muted">{hint}</span> : null}
      </dd>
    </div>
  );
}
