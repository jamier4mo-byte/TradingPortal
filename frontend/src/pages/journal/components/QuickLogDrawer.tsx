import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { Drawer, Field, PillToggle, TextInput, useToast } from "../../../components/ui/index.ts";
import { api } from "../../../lib/api.ts";
import { type Side, type Strategy, type Trade, type TradeKind, useInstruments, useInvalidateJournal } from "../../../lib/journal.ts";
import { ScreenshotSlot } from "./ScreenshotSlot.tsx";
import { TagInput } from "./TagInput.tsx";

interface Remembered {
  instrument: string;
  entry_model: string;
  side: Side;
}

function remembered(strategyId: number): Remembered | null {
  try {
    const raw = localStorage.getItem(`tp.quicklog.${strategyId}`);
    return raw ? (JSON.parse(raw) as Remembered) : null;
  } catch {
    return null;
  }
}

/** Local datetime-local value → ISO in UTC; the browser's zone is the user's own. */
function localToIso(v: string): string {
  return new Date(v).toISOString();
}
function nowLocal(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Quick log (2.2): defaults from the strategy, recent values remembered, screenshots by paste or drag.
 *  Also logs backtest trades by hand and missed setups ("Saw it, didn't take it", U13). */
export function QuickLogDrawer({ open, onClose, strategy, kind: initialKind = "ideal", sessionId }: {
  open: boolean;
  onClose: () => void;
  strategy: Strategy;
  kind?: TradeKind;
  sessionId?: number | null;
}) {
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const instruments = useInstruments();
  const mem = remembered(strategy.id);
  const [kind, setKind] = useState<TradeKind>(initialKind);
  const [instrument, setInstrument] = useState(mem?.instrument ?? strategy.instruments[0] ?? "");
  const [side, setSide] = useState<Side>(mem?.side ?? "buy");
  const [opened, setOpened] = useState(nowLocal());
  const [closed, setClosed] = useState("");
  const [entry, setEntry] = useState("");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [exit, setExit] = useState("");
  const [pnl, setPnl] = useState("");
  const [model, setModel] = useState(mem?.entry_model ?? strategy.entry_models[0] ?? "");
  const [tags, setTags] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Trade | null>(null);

  const num = (v: string) => (v.trim() === "" ? null : Number(v));

  const save = useMutation({
    mutationFn: () =>
      api.post<Trade>(`/api/strategies/${strategy.id}/trades`, {
        kind,
        instrument: instrument.trim().toUpperCase(),
        side,
        opened_at: localToIso(opened),
        closed_at: closed ? localToIso(closed) : null,
        entry_price: num(entry),
        initial_sl: num(sl),
        max_tp: num(tp),
        exit_price: num(exit),
        pnl: num(pnl),
        entry_model: model.trim() || null,
        tags,
        notes: notes.trim() || null,
        session_id: sessionId ?? null,
      }),
    onSuccess: (t) => {
      try {
        localStorage.setItem(`tp.quicklog.${strategy.id}`, JSON.stringify({ instrument, entry_model: model, side } satisfies Remembered));
      } catch {
        /* private mode */
      }
      invalidate(strategy.id);
      setSaved(t);
      toast({ title: kind === "missed" ? "Missed setup logged" : "Trade logged", text: "Add the screenshots, or close to finish." });
    },
    onError: (err) => setError(err.message),
  });

  const reset = () => {
    setSaved(null);
    setEntry("");
    setSl("");
    setTp("");
    setExit("");
    setPnl("");
    setTags([]);
    setNotes("");
    setClosed("");
    setOpened(nowLocal());
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const title = kind === "missed" ? "Saw it, didn't take it" : kind === "backtest" ? "Log a backtest trade" : "Log an ideal trade";

  return (
    <Drawer open={open} onOpenChange={(o) => !o && close()} title={saved ? "Screenshots" : title} description={saved ? "Paste or drop the chart. Then log another or close." : `${strategy.name} · defaults filled in`}>
      {saved ? (
        <div className="flex flex-col gap-4">
          <div className={`grid gap-3 ${kind === "missed" ? "" : "grid-cols-2"}`}>
            <ScreenshotSlot trade={saved} slot="entry" shot={saved.screenshots.find((s) => s.slot === "entry")} label={kind === "missed" ? "The setup" : "Entry"} onChange={setSaved} autoFocus />
            {kind === "missed" ? null : <ScreenshotSlot trade={saved} slot="exit" shot={saved.screenshots.find((s) => s.slot === "exit")} label="Exit" onChange={setSaved} />}
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn btn-secondary flex-1" onClick={reset}>
              Log another
            </button>
            <button type="button" className="btn btn-primary flex-1" onClick={close}>
              Done
            </button>
          </div>
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <PillToggle
            value={kind}
            onChange={setKind}
            label="What to log"
            size="sm"
            options={[
              { value: "ideal", label: "Ideal" },
              { value: "backtest", label: "Backtest" },
              { value: "missed", label: "Missed" },
            ]}
          />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Instrument" error={error}>
              {(p) => (
                <>
                  <TextInput {...p} list="instrument-options" required value={instrument} onChange={(e) => setInstrument(e.target.value)} className="font-mono uppercase" autoCapitalize="characters" />
                  <datalist id="instrument-options">
                    {[...new Set([...strategy.instruments, ...(instruments.data ?? []).map((i) => i.symbol)])].map((s) => (
                      <option key={s} value={s} />
                    ))}
                  </datalist>
                </>
              )}
            </Field>
            <div className="flex flex-col gap-1.5">
              <span className="text-body font-medium">Direction</span>
              <PillToggle value={side} onChange={setSide} label="Direction" size="sm" options={[{ value: "buy", label: "Long" }, { value: "sell", label: "Short" }]} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Entered" help="Your local time">
              {(p) => <TextInput {...p} type="datetime-local" required value={opened} onChange={(e) => setOpened(e.target.value)} className="num" />}
            </Field>
            <Field label="Exited">
              {(p) => <TextInput {...p} type="datetime-local" value={closed} onChange={(e) => setClosed(e.target.value)} className="num" />}
            </Field>
          </div>
          {kind === "missed" ? null : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Entry">{(p) => <TextInput {...p} type="number" inputMode="decimal" step="any" value={entry} onChange={(e) => setEntry(e.target.value)} className="num" />}</Field>
                <Field label="Stop">{(p) => <TextInput {...p} type="number" inputMode="decimal" step="any" value={sl} onChange={(e) => setSl(e.target.value)} className="num" />}</Field>
                <Field label="Target">{(p) => <TextInput {...p} type="number" inputMode="decimal" step="any" value={tp} onChange={(e) => setTp(e.target.value)} className="num" />}</Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Exit price">{(p) => <TextInput {...p} type="number" inputMode="decimal" step="any" value={exit} onChange={(e) => setExit(e.target.value)} className="num" />}</Field>
                <Field label="P&L ($)">{(p) => <TextInput {...p} type="number" inputMode="decimal" step="any" value={pnl} onChange={(e) => setPnl(e.target.value)} className="num" />}</Field>
              </div>
            </>
          )}
          <Field label="Entry model">
            {(p) => (
              <>
                <TextInput {...p} list="model-options" value={model} onChange={(e) => setModel(e.target.value)} />
                <datalist id="model-options">
                  {strategy.entry_models.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <TagInput value={tags} onChange={setTags} />
          <Field label={kind === "missed" ? "Why didn't you take it?" : "Notes"}>
            {(p) => <textarea {...p} className="input min-h-20 py-2" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={8000} />}
          </Field>
          <button type="submit" className="btn btn-primary" disabled={save.isPending || !instrument.trim() || !opened}>
            {kind === "missed" ? "Log missed setup" : "Log trade"}
          </button>
        </form>
      )}
    </Drawer>
  );
}
