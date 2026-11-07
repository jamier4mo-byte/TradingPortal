import { Check, CheckCircle2, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState, Field, OfflineState, SkeletonText, TextInput, useToast } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { Checkbox } from "../../components/ui/Checkbox.tsx";
import { ListEmpty } from "../../components/ui/Illustrations.tsx";
import { imageFiles, prepareImage } from "../../lib/images.ts";
import { fmtR, fmtUkDateTime, isCompleted, LABELLED_SLOTS, missingForCompletion, type Slot, SLOT_LABEL, slotShot, type Trade, type TradePatch, uploadScreenshot, useSession, useSessionTrades, useStrategy, useUpdateTrade } from "../../lib/journal.ts";
import { OutcomeChip, SideChip } from "./components/OutcomeChip.tsx";
import { CompleteDialog } from "./components/CompleteDialog.tsx";
import { ScreenshotSlot } from "./components/ScreenshotSlot.tsx";
import { TagInput } from "./components/TagInput.tsx";

/** Annotate mode (U4): a full-screen "Trade 3/10" stepper. Cmd+V fills HTF, Entry, then Outcome, then focuses
 *  the reason; Enter on the last field moves on. J/K step, Esc exits. Everything autosaves. */
export default function Annotate() {
  const sid = Number(useParams().sid);
  const session = useSession(sid);
  const trades = useSessionTrades(sid);
  const navigate = useNavigate();
  if (offlinePending(session) || offlinePending(trades)) {
    return (
      <div className="card">
        <OfflineState what="This session" />
      </div>
    );
  }
  if (session.isPending || trades.isPending) {
    return (
      <div aria-busy>
        <SkeletonText lines={6} className="max-w-md" />
      </div>
    );
  }
  if (session.isError || trades.isError) {
    return <ErrorState title="Session didn't load" text={(session.error ?? trades.error)?.message} onRetry={() => void Promise.all([session.refetch(), trades.refetch()])} />;
  }
  if (!trades.data.length) {
    return (
      <div className="card">
        <EmptyState
          illustration={<ListEmpty />}
          title="Nothing to annotate"
          text="This session has no trades."
          action={
            <button type="button" className="btn btn-secondary" onClick={() => navigate(`/journal/strategies/${session.data.strategy_id}`)}>
              Back to the strategy
            </button>
          }
        />
      </div>
    );
  }
  return <Stepper strategyId={session.data.strategy_id} trades={trades.data} canEdit={session.data.can_edit} />;
}

function isTyping(el: Element | null) {
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || (el as HTMLElement).isContentEditable);
}

function Stepper({ strategyId, trades, canEdit }: { strategyId: number; trades: Trade[]; canEdit: boolean }) {
  const strategy = useStrategy(strategyId);
  const navigate = useNavigate();
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("trade"));
  const startIndex = Math.max(0, trades.findIndex((t) => t.id === requested));
  const [index, setIndex] = useState(startIndex);
  const [local, setLocal] = useState<Record<number, Trade>>({});
  const [localTags, setLocalTags] = useState<Record<number, string[]>>({});
  const trade = local[trades[index].id] ?? trades[index];
  const tagNames = localTags[trade.id] ?? trade.tags.map((t) => t.name);
  const update = useUpdateTrade();
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const AUTOSAVE_MS = 600; // long enough to batch keystrokes, short enough to survive a quick Esc
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The unsaved edit and the trade it belongs to. Refs, so saving never depends on which render runs it.
  const pending = useRef<{ tradeId: number; body: TradePatch } | null>(null);
  // Saves go out one at a time, in order: a slow early save can never land after (and undo) a later one.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const updateRef = useRef(update);
  updateRef.current = update;
  const toastRef = useRef(toast);
  toastRef.current = toast;
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fields = strategy.data?.reasoning_template ?? [];
  const rules = strategy.data?.rules ?? [];

  /** Run a save after every save already queued. */
  const enqueue = useCallback(<T,>(job: () => Promise<T>): Promise<T> => {
    const next = queue.current.then(job, job);
    queue.current = next.catch(() => undefined);
    return next;
  }, []);

  const flush = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const item = pending.current;
    pending.current = null;
    if (!item || !Object.keys(item.body).length) return queue.current;
    setSaveState("saving");
    return enqueue(() => updateRef.current.mutateAsync({ id: item.tradeId, body: item.body })).then(
      () => setSaveState("saved"),
      (err: unknown) => toastRef.current({ title: "Couldn't save", text: err instanceof Error ? err.message : undefined, tone: "loss" }),
    );
  }, [enqueue]);

  const patch = (changes: TradePatch) => {
    const { tags, ...rest } = changes;
    if (tags) setLocalTags((l) => ({ ...l, [trade.id]: tags }));
    setLocal((l) => ({ ...l, [trade.id]: { ...trade, ...rest } }));
    // A different trade's leftovers are saved first (go() normally already did this).
    if (pending.current && pending.current.tradeId !== trade.id) void flush();
    pending.current = { tradeId: trade.id, body: { ...pending.current?.body, ...changes } };
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, AUTOSAVE_MS);
  };

  const go = useCallback(
    (next: number) => {
      flush();
      const clamped = Math.max(0, Math.min(trades.length - 1, next));
      setIndex(clamped);
      const p = new URLSearchParams(params);
      p.set("trade", String(trades[clamped].id));
      setParams(p, { replace: true });
      setSaveState("idle");
      (document.activeElement as HTMLElement | null)?.blur?.();
      scrollRef.current?.scrollTo({ top: 0 }); // the dialog scrolls, not the window
    },
    [flush, trades, params, setParams],
  );

  const exit = useCallback(() => {
    flush();
    navigate(`/journal/strategies/${strategyId}`);
  }, [flush, navigate, strategyId]);

  const onShot = (t: Trade) => setLocal((l) => ({ ...l, [t.id]: t }));

  // Global paste: HTF → Entry → Outcome → extra. After the outcome lands, the first reason field takes focus.
  useEffect(() => {
    const onPaste = async (e: ClipboardEvent) => {
      if (e.defaultPrevented || !canEdit) return;
      const [file] = imageFiles(e.clipboardData);
      if (!file) return;
      e.preventDefault();
      const current = local[trade.id] ?? trade;
      const slot: Slot | null = LABELLED_SLOTS.find((s) => !slotShot(current, s)) ?? (current.screenshots.filter((s) => s.slot === "extra").length < 3 ? "extra" : null);
      if (!slot) {
        toast({ title: "All six slots are full", text: "Remove one to paste another." });
        return;
      }
      try {
        const prepared = await prepareImage(file, file.name || "pasted.png");
        const updated = await uploadScreenshot(trade.id, prepared.full, slot, { thumb: prepared.thumb, capturedAt: prepared.capturedAt, originalFilename: prepared.name });
        onShot(updated);
        if (slot === "outcome") firstFieldRef.current?.focus();
      } catch (err) {
        toast({ title: "Paste failed", text: err instanceof Error ? err.message : undefined, tone: "loss" });
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [trade, local, canEdit, toast]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (e.shiftKey && canEdit && !isCompleted(local[trade.id] ?? trade)) {
          toggleCompleted(true);
          return;
        }
        go(index + 1);
        return;
      }
      if (isTyping(document.activeElement) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "j" || e.key === "J") go(index + 1);
      if (e.key === "k" || e.key === "K") go(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exit, go, index, canEdit, local, trade]);

  // Save whatever is left when the stepper closes (flush is stable, so this runs on unmount only).
  useEffect(() => () => void flush(), [flush]);

  const done = useMemo(() => trades.filter((t) => isCompleted(local[t.id] ?? t)).length, [trades, local]);
  const completed = isCompleted(trade);
  const [missing, setMissing] = useState<string[] | null>(null);
  const [advanceAfter, setAdvanceAfter] = useState(false);
  const markCompleted = useCallback(
    (value: boolean, thenNext = false) => {
      // Completed is Jamie's own call: it queues behind the last autosave, so the mark lands on the saved trade
      // and its response (which carries the reasoning) is never older than what was typed.
      void flush();
      const id = trade.id;
      enqueue(() => updateRef.current.mutateAsync({ id, body: { annotated: value } })).then(
        (t) => {
          onShot(t);
          if (thenNext) go(index + 1);
        },
        (err: unknown) => toast({ title: "Couldn't save", text: err instanceof Error ? err.message : undefined, tone: "loss" }),
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [flush, enqueue, trade.id, go, index, toast],
  );
  const toggleCompleted = (thenNext = false) => {
    if (completed) {
      markCompleted(false);
      return;
    }
    const gaps = missingForCompletion(trade);
    if (gaps.length) {
      // Warn, never restrict: the dialog lists what's missing and still lets the mark through.
      setMissing(gaps);
      setAdvanceAfter(thenNext);
      return;
    }
    markCompleted(true, thenNext);
  };
  const reasoning = trade.reasoning ?? {};
  const rulesFollowed = trade.rules_followed ?? {};

  // Radix gives the full-screen stepper its focus trap, aria-hidden siblings and a portal (the page wrapper's
  // view-transition-name makes a stacking context, so a plain fixed div would sit under the sidebar).
  return (
    <Dialog.Root open modal>
      <Dialog.Portal>
        <Dialog.Content
          aria-label={`Annotate trade ${index + 1} of ${trades.length}`}
          aria-describedby={undefined}
          onEscapeKeyDown={(e) => {
            e.preventDefault();
            exit();
          }}
          onPointerDownOutside={(e) => e.preventDefault()}
          className="fixed inset-0 z-40 flex flex-col bg-bg outline-none"
        >
      <header className="safe-top flex min-h-14 items-center gap-3 border-b border-border px-(--gutter-phone) tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
        <Dialog.Title asChild>
          <h1 className="num text-title font-semibold">
            Trade {index + 1}/{trades.length}
          </h1>
        </Dialog.Title>
        <span className="hidden items-center gap-2 tablet:flex">
          <span className="font-mono text-body">{trade.instrument}</span>
          <SideChip side={trade.side} />
          {trade.kind === "backtest" ? <OutcomeChip outcome={trade.outcome} /> : null}
          <span className="num text-body text-muted">{fmtUkDateTime(trade.opened_at)}</span>
          <span className={`num text-body font-medium ${(trade.r_multiple ?? 0) > 0 ? "text-win" : (trade.r_multiple ?? 0) < 0 ? "text-loss" : ""}`}>{fmtR(trade.r_multiple)}</span>
        </span>
        <span className="ml-auto flex items-center gap-3">
          <span className="text-label text-muted" aria-live="polite">
            {saveState === "saving" ? "Saving…" : saveState === "saved" ? <span className="inline-flex items-center gap-1"><Check aria-hidden className="size-3.5" /> Autosaved</span> : null}
          </span>
          <span className="num text-label text-muted">{done}/{trades.length} completed</span>
          <kbd className="hidden rounded-panel border border-border px-1.5 font-mono text-label text-muted laptop:inline">Esc</kbd>
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Exit annotate mode" onClick={exit}>
            <X aria-hidden className="size-5" />
          </button>
        </span>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-(--gutter-phone) py-4 tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
        <div className="mx-auto grid max-w-[1400px] gap-6 laptop:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
          <section aria-label="Screenshots" className="flex flex-col gap-4">
            <p className="flex flex-wrap items-center gap-2 text-body tablet:hidden">
              <span className="font-mono">{trade.instrument}</span>
              <SideChip side={trade.side} />
              <span className="num text-muted">{fmtUkDateTime(trade.opened_at)}</span>
              <span className="num font-medium">{fmtR(trade.r_multiple)}</span>
            </p>
            <div className="grid gap-4 tablet:grid-cols-3">
              {LABELLED_SLOTS.map((slot) => (
                <ScreenshotSlot
                  key={slot}
                  trade={trade}
                  slot={slot}
                  shot={slotShot(trade, slot)}
                  label={SLOT_LABEL[slot]}
                  size="lg"
                  onChange={onShot}
                  disabled={!canEdit}
                  onPasted={slot === "outcome" ? () => firstFieldRef.current?.focus() : undefined}
                />
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {trade.screenshots
                .filter((s) => s.slot === "extra")
                .map((s, i) => (
                  <ScreenshotSlot key={s.id} trade={trade} slot="extra" shot={s} label={`Extra ${i + 1}`} onChange={onShot} disabled={!canEdit} />
                ))}
              {trade.screenshots.filter((s) => s.slot === "extra").length < 3 && canEdit ? <ScreenshotSlot trade={trade} slot="extra" label="Extra" onChange={onShot} /> : null}
            </div>
            <p className="hidden text-label text-muted laptop:block">
              <kbd className="rounded-panel border border-border px-1 font-mono">⌘V</kbd> fills HTF, Entry, then Outcome, then the reason. <kbd className="rounded-panel border border-border px-1 font-mono">J</kbd>/<kbd className="rounded-panel border border-border px-1 font-mono">K</kbd> next and previous. <kbd className="rounded-panel border border-border px-1 font-mono">⌘↵</kbd> next trade, <kbd className="rounded-panel border border-border px-1 font-mono">⌘⇧↵</kbd> mark completed and move on.
            </p>
          </section>

          <section aria-label="Reasoning" className="flex flex-col gap-4">
            {fields.map((f, i) => (
              <Field key={f.key} label={f.label}>
                {(p) => (
                  <input
                    {...p}
                    className="input"
                    ref={i === 0 ? firstFieldRef : undefined}
                    value={reasoning[f.key] ?? ""}
                    disabled={!canEdit}
                    onChange={(e) => patch({ reasoning: { ...reasoning, [f.key]: e.target.value } })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) {
                        e.preventDefault();
                        const next = (e.currentTarget.form ?? document).querySelectorAll<HTMLInputElement>("input[data-reason]")[i + 1];
                        if (next) next.focus();
                        else go(index + 1);
                      }
                    }}
                    data-reason={f.key}
                  />
                )}
              </Field>
            ))}
            <fieldset className="flex flex-col gap-1">
              <legend className="mb-1 text-body font-medium">Rules followed</legend>
              {rules.map((r) => {
                const v = rulesFollowed[r.key];
                return (
                  <label key={r.key} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-panel px-2 hover:bg-surface-2">
                    <Checkbox checked={v === true} disabled={!canEdit} onChange={(checked) => patch({ rules_followed: { ...rulesFollowed, [r.key]: checked } })} />
                    <span className="text-body">{r.text}</span>
                  </label>
                );
              })}
              {rules.length ? (
                <button
                  type="button"
                  className="btn btn-ghost self-start"
                  disabled={!canEdit}
                  onClick={() => patch({ rules_followed: Object.fromEntries(rules.map((r) => [r.key, rulesFollowed[r.key] ?? false])) })}
                >
                  Mark unticked as broken
                </button>
              ) : null}
            </fieldset>
            <TagInput value={tagNames} onChange={(names) => patch({ tags: names })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="MAE (R)" help="Worst excursion, as R">
                {(p) => <TextInput {...p} type="number" step="0.1" inputMode="decimal" className="num" disabled={!canEdit} value={trade.mae_r ?? ""} onChange={(e) => patch({ mae_r: e.target.value === "" ? null : Number(e.target.value) })} />}
              </Field>
              <Field label="MFE (R)" help="Best excursion, as R">
                {(p) => <TextInput {...p} type="number" step="0.1" inputMode="decimal" className="num" disabled={!canEdit} value={trade.mfe_r ?? ""} onChange={(e) => patch({ mfe_r: e.target.value === "" ? null : Number(e.target.value) })} />}
              </Field>
            </div>
            <Field label="Notes">
              {(p) => <textarea {...p} className="input min-h-20 py-2" disabled={!canEdit} value={trade.notes} onChange={(e) => patch({ notes: e.target.value })} />}
            </Field>
          </section>
        </div>
      </div>

      <footer className="safe-bottom flex min-h-16 items-center gap-3 border-t border-border px-(--gutter-phone) tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
        <button type="button" className="btn btn-secondary" onClick={() => go(index - 1)} disabled={index === 0}>
          <ChevronLeft aria-hidden className="size-4" /> Previous <kbd className="hidden font-mono text-label text-muted laptop:inline">K</kbd>
        </button>
        <ol className="mx-auto hidden items-center gap-1 tablet:flex" aria-label="Trades in this session">
          {trades.map((t, i) => {
            const tt = local[t.id] ?? t;
            const complete = isCompleted(tt);
            return (
              <li key={t.id}>
                <button type="button" aria-label={`Trade ${i + 1}${complete ? ", completed" : ""}`} aria-current={i === index ? "step" : undefined} onClick={() => go(i)} className="grid size-11 place-items-center">
                  <span className={`block rounded-full ${i === index ? "size-3.5 border-2 border-accent bg-bg" : complete ? "size-2.5 bg-accent" : "size-2.5 bg-surface-2 ring-1 ring-border-input"}`} />
                </button>
              </li>
            );
          })}
        </ol>
        {canEdit ? (
          <button
            type="button"
            className={`btn ml-auto tablet:ml-0 ${completed ? "btn-ghost" : "btn-secondary"}`}
            onClick={() => toggleCompleted(false)}
            disabled={update.isPending}
            aria-pressed={completed}
          >
            <CheckCircle2 aria-hidden className="size-4" /> <span className="hidden tablet:inline">{completed ? "Completed" : "Mark completed"}</span>
            <span className="tablet:hidden">{completed ? "Done" : "Complete"}</span>
          </button>
        ) : null}
        {index === trades.length - 1 ? (
          <button type="button" className={`btn btn-primary ${canEdit ? "" : "ml-auto"} tablet:ml-0`} onClick={exit}>
            <Check aria-hidden className="size-4" /> Finish
          </button>
        ) : (
          <button type="button" className={`btn btn-primary ${canEdit ? "" : "ml-auto"} tablet:ml-0`} onClick={() => go(index + 1)}>
            Next <ChevronRight aria-hidden className="size-4" /> <kbd className="hidden font-mono text-label text-on-accent laptop:inline">J</kbd>
          </button>
        )}
      </footer>
      <CompleteDialog
        missing={missing}
        busy={update.isPending}
        onCancel={() => setMissing(null)}
        onConfirm={() => {
          setMissing(null);
          markCompleted(true, advanceAfter);
        }}
      />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
