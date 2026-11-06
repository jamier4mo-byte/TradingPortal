import { Check, FileSpreadsheet, Upload } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Drawer, PillToggle, useToast } from "../../../components/ui/index.ts";
import { api } from "../../../lib/api.ts";
import { fmtPnl, fmtR, fmtUkDate, type ImportPreview, type ImportResult, type Strategy, useInvalidateJournal } from "../../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../../lib/motion.ts";
import { OutcomeChip } from "./OutcomeChip.tsx";

type Destination = "ideal" | "backtest";
type Step = "pick" | "preview" | "running" | "done";
const STAGES = ["Reading file", "Matching trades", "Calculating stats", "Done"] as const;

/** Upload → preview → confirm → Session created (F3), with the stage progress from the Motion doc. */
export function ImportDrawer({ open, onClose, strategy, destination: initial = "ideal", onImported }: {
  open: boolean;
  onClose: () => void;
  strategy: Strategy;
  destination?: Destination;
  onImported?: (r: ImportResult) => void;
}) {
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("pick");
  const [file, setFile] = useState<File | null>(null);
  const [tz, setTz] = useState<"Europe/London" | "UTC">(strategy.csv_timezone);
  const [destination, setDestination] = useState<Destination>(initial);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const level = motionLevel();

  useEffect(() => {
    if (open) setDestination(initial);
  }, [open, initial]);

  const reset = () => {
    setStep("pick");
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setStage(0);
  };

  const close = () => {
    reset();
    onClose();
  };

  const runPreview = async (f: File, zone = tz) => {
    setError(null);
    setFile(f);
    const form = new FormData();
    form.append("file", f, f.name);
    form.append("timezone", zone);
    try {
      const p = await api.upload<ImportPreview>(`/api/strategies/${strategy.id}/imports/preview`, form);
      setPreview(p);
      setStep("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't read that file");
    }
  };

  const confirm = async () => {
    if (!file) return;
    setStep("running");
    setStage(0);
    const tick = (n: number) => new Promise<void>((r) => setTimeout(() => (setStage(n), r()), level === "off" ? 0 : 350));
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("destination", destination);
    form.append("timezone", tz);
    try {
      await tick(1);
      const r = await api.upload<ImportResult>(`/api/strategies/${strategy.id}/imports`, form);
      await tick(2);
      await tick(3);
      setResult(r);
      setStep("done");
      invalidate(strategy.id);
      onImported?.(r);
      const n = r.report.imported;
      toast({
        title: `${n} ${n === 1 ? "trade" : "trades"} imported`,
        text: r.report.duplicates.length ? `${r.report.duplicates.length} duplicates skipped.` : undefined,
        undo: async () => {
          await api.delete(`/api/journal/sessions/${r.session.id}`);
          invalidate(strategy.id);
          toast({
            title: "Import undone",
            text: `${n} trades moved to Trash.`,
            undo: async () => {
              await api.post(`/api/journal/sessions/${r.session.id}/restore`);
              invalidate(strategy.id);
              toast({ title: "Import restored" });
            },
          });
        },
      });
    } catch (err) {
      setStep("preview");
      setError(err instanceof Error ? err.message : "Import failed");
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void runPreview(f);
  };

  const would = preview ? preview.would_import[destination] : 0;

  return (
    <Drawer open={open} onOpenChange={(o) => !o && close()} title="Import from FX Replay" description={step === "pick" ? "Analytics → Export in FX Replay gives you the CSV." : file?.name}>
      {step === "pick" ? (
        <div className="flex flex-col gap-4">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
            className={`flex min-h-40 flex-col items-center justify-center gap-2 rounded-panel border border-dashed bg-surface-2 px-4 text-center text-body text-muted ${over ? "border-accent" : "border-border-strong hover:border-muted"}`}
          >
            <FileSpreadsheet aria-hidden className="size-6" strokeWidth={1.5} />
            <span>
              <span className="text-text">Choose the CSV</span>
              <span className="hidden tablet:inline"> or drop it here</span>
            </span>
            <span className="text-label">22 columns, starting id, dateStart, dateEnd, pair</span>
          </button>
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" tabIndex={-1} aria-label="CSV file" onChange={(e) => e.target.files?.[0] && void runPreview(e.target.files[0])} />
          <div className="flex flex-col gap-1.5">
            <span className="text-body font-medium">Chart timezone in the file</span>
            <PillToggle value={tz} onChange={setTz} label="CSV timezone" size="sm" options={[{ value: "Europe/London", label: "UK" }, { value: "UTC", label: "UTC" }]} />
          </div>
          {error ? <p role="alert" className="text-body text-loss">{error}</p> : null}
        </div>
      ) : null}

      {step === "preview" && preview ? (
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-2 tablet:grid-cols-3">
            <Stat label="Rows parsed" value={`${preview.rows_parsed} of ${preview.rows_total}`} />
            <Stat label="Dates" value={preview.range_start ? `${fmtUkDate(preview.range_start)} – ${fmtUkDate(preview.range_end)}` : "—"} />
            <Stat label="Timezone" value={preview.timezone === "UTC" ? "UTC" : "UK"} />
            <Stat label="Winners" value={String(preview.winners)} tone="win" />
            <Stat label="Losers" value={String(preview.losers)} tone="loss" />
            <Stat label="Breakeven" value={`${preview.breakevens} (±${preview.breakeven_threshold})`} tone="breakeven" />
          </dl>
          {preview.duplicates[destination] ? (
            <p className="rounded-panel border border-border bg-surface-2 px-3 py-2 text-body">
              <span className="num font-medium">{preview.duplicates[destination]}</span> {preview.duplicates[destination] === 1 ? "trade is" : "trades are"} already in this strategy{"'"}s {destination === "ideal" ? "ideal catalogue" : "backtest"} and will be skipped.
            </p>
          ) : null}
          {preview.problems.length ? (
            <details className="rounded-panel border border-impact-medium/40 px-3 py-2 text-body">
              <summary className="cursor-pointer">
                <span className="num">{preview.problems.length}</span> {preview.problems.length === 1 ? "row" : "rows"} can't be read and will be skipped
              </summary>
              <ul className="mt-2 flex flex-col gap-1 font-mono text-label text-muted">
                {preview.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </details>
          ) : null}
          <div className="flex flex-col gap-1.5">
            <span className="text-body font-medium">Import into</span>
            <PillToggle
              value={destination}
              onChange={setDestination}
              label="Destination"
              options={[
                { value: "ideal", label: `Ideal · ${preview.would_import.ideal} winners` },
                { value: "backtest", label: `Backtest · ${preview.would_import.backtest} trades` },
              ]}
            />
            <p className="text-label text-muted">{destination === "ideal" ? "Winners only. Losers and breakevens stay out of the catalogue." : "Every trade: wins, losses and breakevens."}</p>
          </div>
          <div className="max-h-64 overflow-auto rounded-panel border border-border">
            <table className="w-full border-separate border-spacing-0 text-label">
              <thead className="sticky top-0 bg-surface-1 text-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-normal">Opened (UK)</th>
                  <th className="px-2 py-1.5 text-left font-normal">Side</th>
                  <th className="px-2 py-1.5 text-right font-normal">P&amp;L</th>
                  <th className="px-2 py-1.5 text-right font-normal">R</th>
                  <th className="px-2 py-1.5 text-left font-normal">Outcome</th>
                  <th className="px-2 py-1.5 text-left font-normal">Imports?</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r) => {
                  const dup = r.duplicate[destination];
                  const imports = !dup && (destination === "backtest" || r.outcome === "win");
                  return (
                    <tr key={r.fx_id} className={imports ? "" : "text-muted"}>
                      <td className="num border-t border-border px-2 py-1.5">{r.opened_uk}</td>
                      <td className="border-t border-border px-2 py-1.5">{r.side === "buy" ? "Long" : "Short"}</td>
                      <td className="num border-t border-border px-2 py-1.5 text-right">{fmtPnl(r.pnl)}</td>
                      <td className="num border-t border-border px-2 py-1.5 text-right">{fmtR(r.r_multiple)}</td>
                      <td className="border-t border-border px-2 py-1.5"><OutcomeChip outcome={r.outcome} /></td>
                      <td className="border-t border-border px-2 py-1.5">{dup ? "Duplicate" : imports ? "Yes" : "No"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {error ? <p role="alert" className="text-body text-loss">{error}</p> : null}
          <div className="flex gap-2">
            <button type="button" className="btn btn-secondary" onClick={reset}>
              Pick another file
            </button>
            <button type="button" className="btn btn-primary flex-1" onClick={confirm} disabled={would === 0}>
              <Upload aria-hidden className="size-4" />
              Import {would} {would === 1 ? "trade" : "trades"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "running" || step === "done" ? (
        <div className="flex flex-col gap-4" aria-live="polite">
          <ol className="flex flex-col gap-2">
            {STAGES.map((label, i) => {
              const done = stage > i || step === "done";
              const active = stage === i && step !== "done";
              return (
                <li key={label} className={`flex min-h-11 items-center gap-3 rounded-panel border px-3 ${active ? "border-accent" : "border-border"} ${done || active ? "" : "text-muted"}`}>
                  <span className={`grid size-6 place-items-center rounded-full border ${done ? "border-accent bg-accent text-on-accent" : active ? "border-accent" : "border-border"}`}>
                    {done ? <Check aria-hidden className="size-3.5" strokeWidth={3} /> : <span className="num text-label">{i + 1}</span>}
                  </span>
                  {label}
                </li>
              );
            })}
          </ol>
          <div className="h-1 overflow-hidden rounded-pill bg-surface-2">
            <motion.div className="h-full bg-accent" initial={{ width: 0 }} animate={{ width: `${((step === "done" ? 4 : stage) / 4) * 100}%` }} transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }} />
          </div>
          <AnimatePresence>
            {step === "done" && result ? (
              <motion.div initial={level === "full" ? { opacity: 0, y: 8 } : { opacity: 0 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }} className="flex flex-col gap-3">
                <p className="text-title font-semibold">
                  <span className="num">{result.report.imported}</span> {result.report.imported === 1 ? "trade" : "trades"} imported
                </p>
                <p className="text-body text-muted">
                  {result.report.duplicates.length ? `${result.report.duplicates.length} duplicates skipped. ` : ""}
                  {result.report.skipped_not_winners ? `${result.report.skipped_not_winners} non-winners left out of the ideal catalogue. ` : ""}
                  {result.report.unresolved_tags.length ? `Unknown tags kept as text: ${result.report.unresolved_tags.join(", ")}.` : ""}
                </p>
                {result.report.imported > 0 ? (
                  <div className="flex flex-col gap-2">
                    <button type="button" className="btn btn-primary" onClick={() => navigate(`/journal/sessions/${result.session.id}/match`)}>
                      Add the screenshots
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => navigate(`/journal/sessions/${result.session.id}/annotate`)}>
                      Annotate trades
                    </button>
                    <button type="button" className="btn btn-ghost" onClick={close}>
                      Later
                    </button>
                  </div>
                ) : (
                  <button type="button" className="btn btn-secondary" onClick={close}>
                    Close
                  </button>
                )}
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      ) : null}
    </Drawer>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "win" | "loss" | "breakeven" }) {
  const cls = tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : tone === "breakeven" ? "text-breakeven" : "";
  return (
    <div className="rounded-panel border border-border bg-surface-2 px-3 py-2">
      <dt className="text-label text-muted">{label}</dt>
      <dd className={`num text-body font-medium ${cls}`}>{value}</dd>
    </div>
  );
}
