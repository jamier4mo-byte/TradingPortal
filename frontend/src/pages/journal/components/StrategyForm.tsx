import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { Drawer, Field, PillToggle, TextInput, useToast } from "../../../components/ui/index.ts";
import { api } from "../../../lib/api.ts";
import { type Rule, type Strategy, useInvalidateJournal } from "../../../lib/journal.ts";

const DEFAULT_RULES = [
  "HTF bias agrees with the trade direction",
  "Entry taken inside the killzone",
  "Stop placed beyond the invalidation level",
  "Target is a real draw on liquidity",
];

function listToText(v: string[]) {
  return v.join(", ");
}
function textToList(v: string) {
  return v.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
}

/** New strategy and Edit strategy share this drawer. There is no duplicate action anywhere. */
export function StrategyForm({ open, onClose, strategy, onSaved }: { open: boolean; onClose: () => void; strategy?: Strategy | null; onSaved?: (s: Strategy) => void }) {
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instruments, setInstruments] = useState("");
  const [timeframes, setTimeframes] = useState("");
  const [entryModels, setEntryModels] = useState("");
  const [tz, setTz] = useState<"Europe/London" | "UTC">("Europe/London");
  const [rules, setRules] = useState<string[]>(DEFAULT_RULES);
  const [error, setError] = useState<string | null>(null);
  const [seeded, setSeeded] = useState<number | "new" | null>(null);

  const current = open ? (strategy?.id ?? "new") : null;
  if (current !== null && current !== seeded) {
    setSeeded(current);
    setName(strategy?.name ?? "");
    setDescription(strategy?.description ?? "");
    setInstruments(listToText(strategy?.instruments ?? []));
    setTimeframes(listToText(strategy?.timeframes ?? []));
    setEntryModels(listToText(strategy?.entry_models ?? []));
    setTz(strategy?.csv_timezone ?? "Europe/London");
    setRules(strategy?.rules.map((r: Rule) => r.text) ?? DEFAULT_RULES);
    setError(null);
  }
  if (!open && seeded !== null) setSeeded(null);

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: name.trim(),
        description: description.trim(),
        instruments: textToList(instruments),
        timeframes: textToList(timeframes),
        entry_models: textToList(entryModels),
        csv_timezone: tz,
        rules: rules.filter((r) => r.trim()).map((text, i) => ({ key: strategy?.rules[i]?.key ?? `r${i + 1}`, text })),
      };
      return strategy ? api.patch<Strategy>(`/api/strategies/${strategy.id}`, body) : api.post<Strategy>("/api/strategies", body);
    },
    onSuccess: (s) => {
      invalidate(s.id);
      toast({ title: strategy ? "Strategy saved" : `“${s.name}” created` });
      onSaved?.(s);
      onClose();
    },
    onError: (err) => setError(err.message),
  });

  const ruleCount = rules.filter((r) => r.trim()).length;
  const rulesOk = ruleCount >= 4 && ruleCount <= 8;

  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()} title={strategy ? "Edit strategy" : "New strategy"} description="Name, instruments, timeframes, the idea and its entry models.">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (rulesOk) save.mutate();
        }}
      >
        <Field label="Name" error={error}>
          {(p) => <TextInput {...p} required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="NAS100 silver bullet" autoFocus />}
        </Field>
        <Field label="Instruments" help="Comma-separated. NAS100, XAUUSD, EURUSD…">
          {(p) => <TextInput {...p} value={instruments} onChange={(e) => setInstruments(e.target.value)} className="font-mono uppercase" />}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Timeframes" help="5m, 1m">
            {(p) => <TextInput {...p} value={timeframes} onChange={(e) => setTimeframes(e.target.value)} />}
          </Field>
          <Field label="Entry models" help="FVG, OTE, Breaker">
            {(p) => <TextInput {...p} value={entryModels} onChange={(e) => setEntryModels(e.target.value)} />}
          </Field>
        </div>
        <Field label="The idea" help="A short description of the setup.">
          {(p) => <textarea {...p} className="input min-h-24 py-2" maxLength={4000} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-body font-medium">FX Replay chart timezone</span>
          <PillToggle value={tz} onChange={setTz} label="CSV timezone" options={[{ value: "Europe/London", label: "UK (Europe/London)" }, { value: "UTC", label: "UTC" }]} size="sm" />
          <p className="text-label text-muted">Whatever the clock at the bottom of your FX Replay chart shows. Times are stored in UTC and shown in UK time.</p>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="text-body font-medium">
            Rulebook <span className="num text-label text-muted">({ruleCount} of 4–8)</span>
          </legend>
          {rules.map((r, i) => (
            <div key={i} className="flex gap-2">
              <input
                aria-label={`Rule ${i + 1}`}
                className="input"
                maxLength={200}
                value={r}
                onChange={(e) => setRules(rules.map((x, j) => (j === i ? e.target.value : x)))}
              />
              {rules.length > 4 ? (
                <button type="button" className="btn btn-ghost size-11 shrink-0 px-0" aria-label={`Remove rule ${i + 1}`} onClick={() => setRules(rules.filter((_, j) => j !== i))}>
                  ×
                </button>
              ) : null}
            </div>
          ))}
          {rules.length < 8 ? (
            <button type="button" className="btn btn-secondary self-start" onClick={() => setRules([...rules, ""])}>
              Add a rule
            </button>
          ) : null}
          {!rulesOk ? <p className="text-label text-loss">A rulebook has between 4 and 8 rules.</p> : null}
        </fieldset>
        <button type="submit" className="btn btn-primary" disabled={save.isPending || !name.trim() || !rulesOk}>
          {strategy ? "Save changes" : "Create strategy"}
        </button>
      </form>
    </Drawer>
  );
}
