import { Check, Repeat, Trash2, Undo2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { ConfirmDialog, Drawer, type DrawerOrigin, Field, OwnerChip, PillToggle, ReadOnlyBanner, Switch, TextInput, useToast } from "../../components/ui/index.ts";
import { ApiError, type PublicUser } from "../../lib/api.ts";
import {
  CATEGORIES,
  type Category,
  type Mode,
  type Occurrence,
  PRESET_RULES,
  presetFor,
  REPEAT_OPTIONS,
  type RepeatPreset,
  type TaskIn,
  ukDateOf,
  ukWall,
  ukWallToUtc,
  useCompleteTask,
  useCreateTask,
  useDeleteTask,
  useUpdateTask,
} from "../../lib/calendar.ts";
import { addDays } from "../../lib/news.ts";

/** Prefill for a new task from a tap on a day or slot (UK wall clock). */
export interface Prefill {
  date: string;
  time?: string; // "HH:mm"
  allDay?: boolean;
}

const SCOPES: { value: Mode; label: string }[] = [
  { value: "occurrence", label: "This occurrence" },
  { value: "series", label: "Whole series" },
];

interface FormState {
  title: string;
  allDay: boolean;
  date: string;
  start: string;
  end: string;
  endDate: string;
  category: Category;
  repeat: RepeatPreset;
  rrule: string;
  description: string;
}

function plusHour(time: string): string {
  const [h, m] = time.split(":").map(Number);
  return `${String(Math.min(h + 1, 23)).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** The repeat field always shows the series' rule (it is read-only in "This occurrence" scope). */
function fromOccurrence(o: Occurrence, seriesRule: string | null): FormState {
  const startWall = ukWall(o.start_at);
  const endWall = o.end_at ? ukWall(o.end_at) : null;
  const endDate = o.all_day && endWall ? addDays(endWall.slice(0, 10), -1) : "";
  const rule = seriesRule;
  return {
    title: o.title,
    allDay: o.all_day,
    date: startWall.slice(0, 10),
    start: o.all_day ? "09:00" : startWall.slice(11, 16),
    end: o.all_day ? "" : endWall ? endWall.slice(11, 16) : "",
    endDate: endDate && endDate !== startWall.slice(0, 10) ? endDate : "",
    category: o.category,
    repeat: presetFor(rule),
    rrule: rule ?? "",
    description: o.description ?? "",
  };
}

function fromPrefill(p: Prefill): FormState {
  const start = p.time ?? "09:00";
  return {
    title: "",
    allDay: p.allDay ?? false,
    date: p.date,
    start,
    end: plusHour(start),
    endDate: "",
    category: "backtesting",
    repeat: "none",
    rrule: "",
    description: "",
  };
}

function toBody(f: FormState): TaskIn {
  const rrule = f.repeat === "none" ? null : f.repeat === "custom" ? f.rrule.trim() || null : PRESET_RULES[f.repeat];
  if (f.allDay) {
    const endDate = f.endDate && f.endDate > f.date ? f.endDate : f.date;
    return {
      title: f.title.trim(),
      description: f.description.trim() || null,
      category: f.category,
      all_day: true,
      start_at: ukWallToUtc(`${f.date}T00:00`),
      end_at: ukWallToUtc(`${addDays(endDate, 1)}T00:00`),
      tz: "Europe/London",
      rrule,
    };
  }
  return {
    title: f.title.trim(),
    description: f.description.trim() || null,
    category: f.category,
    all_day: false,
    start_at: ukWallToUtc(`${f.date}T${f.start}`),
    end_at: f.end ? ukWallToUtc(`${f.date}T${f.end}`) : null,
    tz: "Europe/London",
    rrule,
  };
}

/** New-task and edit drawer. For a recurring task the scope control decides whether Save and Delete touch
 * this occurrence or the whole series. Other people's tasks open read-only (members), with Mark done
 * disabled: completing them is the owner's (or the admin's) call. */
export function TaskDrawer({
  open,
  onOpenChange,
  occurrence,
  prefill,
  seriesRule,
  me,
  online,
  origin,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  occurrence: Occurrence | null;
  prefill: Prefill | null;
  origin?: DrawerOrigin;
  /** The series' RRULE for the occurrence being edited (from GET /tasks/{id}); null while loading. */
  seriesRule: string | null;
  me: PublicUser | null;
  online: boolean;
}) {
  const { toast } = useToast();
  const create = useCreateTask();
  const update = useUpdateTask();
  const remove = useDeleteTask();
  const complete = useCompleteTask();
  const editing = occurrence !== null;
  const recurring = occurrence?.recurring ?? false;
  const canEdit = editing ? occurrence.can_edit : true;
  const [scope, setScope] = useState<Mode>("occurrence");
  const [form, setForm] = useState<FormState>(() => (occurrence ? fromOccurrence(occurrence, seriesRule) : fromPrefill(prefill ?? { date: ukDateOf(new Date().toISOString()) })));
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!open) return;
    setScope(recurring ? "occurrence" : "series");
    setError(null);
    setForm(occurrence ? fromOccurrence(occurrence, seriesRule) : fromPrefill(prefill ?? { date: ukDateOf(new Date().toISOString()) }));
  }, [open, occurrence, prefill, recurring, seriesRule]);

  // Per-occurrence edits can't change the rule: the repeat field is read-only in that scope.
  const changeScope = (next: Mode) => setScope(next);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));
  const busy = create.isPending || update.isPending || remove.isPending;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.title.trim()) return setError("Give the task a title.");
    if (!form.allDay && form.end && form.end <= form.start) return setError("The end must be after the start.");
    try {
      const body = toBody(form);
      if (!editing) {
        await create.mutateAsync(body);
        toast({ title: "Task added", text: body.title });
      } else if (recurring && scope === "occurrence") {
        const { rrule: _rule, tz: _tz, ...rest } = body;
        await update.mutateAsync({ id: occurrence.task_id, ...rest, mode: "occurrence", occurrence_date: occurrence.occurrence_date });
        toast({ title: "This occurrence updated" });
      } else {
        // Editing the whole series from one occurrence: keep the series anchored, so send the time change
        // as a move of this occurrence and the rest as plain fields.
        const { start_at, end_at, ...rest } = body;
        await update.mutateAsync({ id: occurrence.task_id, ...rest, start_at, end_at, mode: "series", occurrence_date: recurring ? occurrence.occurrence_date : undefined });
        toast({ title: recurring ? "Whole series updated" : "Task updated" });
      }
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That didn't save. Try again.");
    }
  };

  const onDelete = async () => {
    if (!occurrence) return;
    try {
      await remove.mutateAsync({ id: occurrence.task_id, mode: recurring ? scope : "series", occurrence_date: recurring ? occurrence.occurrence_date : undefined });
      toast({ title: recurring && scope === "occurrence" ? "Occurrence removed" : "Task deleted" });
      setConfirmDelete(false);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That didn't delete. Try again.");
    }
  };

  const toggleDone = () => {
    if (!occurrence) return;
    const next = !occurrence.done;
    const vars = { task_id: occurrence.task_id, occurrence_date: occurrence.occurrence_date };
    complete.mutate(
      { ...vars, done: next },
      {
        onError: (err) => toast({ title: "Couldn't save that", text: err instanceof ApiError ? err.message : undefined, tone: "loss" }),
      },
    );
    toast({ title: next ? "Marked done" : "Marked not done", text: occurrence.title, undo: () => complete.mutate({ ...vars, done: !next }) });
    onOpenChange(false);
  };

  const owner = editing ? occurrence.owner : me;
  const title = editing ? (canEdit ? "Edit task" : "Task") : "New task";
  const description = editing && recurring ? "Part of a repeating series" : undefined;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      origin={origin}
      footer={
        canEdit ? (
          <div className="flex flex-wrap items-center gap-2">
            {editing ? (
              <>
                <button type="button" className="btn btn-secondary" onClick={toggleDone} disabled={!online}>
                  {occurrence.done ? <Undo2 aria-hidden className="size-4" /> : <Check aria-hidden className="size-4" />}
                  {occurrence.done ? "Undo done" : "Mark done"}
                </button>
                <button type="button" className="btn btn-danger" onClick={() => setConfirmDelete(true)} disabled={busy || !online}>
                  <Trash2 aria-hidden className="size-4" />
                  Delete
                </button>
              </>
            ) : null}
            <button type="submit" form="task-form" className="btn btn-primary ml-auto" disabled={busy || !online}>
              {editing ? "Save" : "Add task"}
            </button>
          </div>
        ) : (
          <p className="text-body text-muted">Only {owner?.display_name ?? "the owner"} or the admin can change this task.</p>
        )
      }
    >
      <form id="task-form" className="flex flex-col gap-4" onSubmit={onSubmit} aria-label={title}>
        {editing && !canEdit ? <ReadOnlyBanner owner={occurrence.owner.display_name} what="task" /> : null}
        {!online ? (
          <p role="status" className="rounded-panel border border-border-strong bg-surface-2 px-3 py-2 text-body text-muted">
            You&rsquo;re offline. Changes will be possible when you&rsquo;re back online.
          </p>
        ) : null}
        {editing && recurring && canEdit ? (
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-body font-medium">
              <Repeat aria-hidden className="size-4 text-muted" />
              Apply changes to
            </span>
            <PillToggle<Mode> value={scope} onChange={changeScope} options={SCOPES} label="Apply changes to" size="sm" />
          </div>
        ) : null}

        <Field label="Title">
          {(p) => <TextInput {...p} value={form.title} onChange={(e) => set("title", e.target.value)} maxLength={120} required readOnly={!canEdit} autoFocus={!editing} />}
        </Field>

        <Switch checked={form.allDay} onChange={(v) => (canEdit ? set("allDay", v) : undefined)} label="All day" />

        <div className={`grid gap-3 ${form.allDay ? "grid-cols-2" : "grid-cols-2 tablet:grid-cols-[1.4fr_1fr_1fr]"}`}>
          <div className={form.allDay ? "" : "col-span-2 tablet:col-span-1"}>
            <Field label={form.allDay ? "From" : "Date"}>
              {(p) => <TextInput {...p} type="date" value={form.date} onChange={(e) => set("date", e.target.value)} required readOnly={!canEdit} className="num" />}
            </Field>
          </div>
          {form.allDay ? (
            <Field label="To (optional)">
              {(p) => <TextInput {...p} type="date" value={form.endDate} min={form.date} onChange={(e) => set("endDate", e.target.value)} readOnly={!canEdit} className="num" />}
            </Field>
          ) : (
            <>
              <Field label="Start">
                {(p) => <TextInput {...p} type="time" value={form.start} onChange={(e) => set("start", e.target.value)} required readOnly={!canEdit} className="num" />}
              </Field>
              <Field label="End">
                {(p) => <TextInput {...p} type="time" value={form.end} onChange={(e) => set("end", e.target.value)} readOnly={!canEdit} className="num" />}
              </Field>
            </>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 tablet:grid-cols-2">
          <Field label="Category">
            {(p) => (
              <select {...p} className="input" value={form.category} onChange={(e) => set("category", e.target.value as Category)} disabled={!canEdit}>
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Repeat" help={editing && recurring && scope === "occurrence" ? "To change the repeat, apply to the whole series." : undefined}>
            {(p) => (
              <select {...p} className="input" value={form.repeat} onChange={(e) => set("repeat", e.target.value as RepeatPreset)} disabled={!canEdit || (editing && recurring && scope === "occurrence")}>
                {REPEAT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
        {form.repeat === "custom" ? (
          <Field label="RRULE" help="RFC 5545, e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10">
            {(p) => <TextInput {...p} value={form.rrule} onChange={(e) => set("rrule", e.target.value)} placeholder="FREQ=WEEKLY;BYDAY=MO" className="font-mono" readOnly={!canEdit} />}
          </Field>
        ) : null}

        <Field label="Notes">
          {(p) => <textarea {...p} className="input min-h-24 py-2" value={form.description} onChange={(e) => set("description", e.target.value)} maxLength={4000} readOnly={!canEdit} />}
        </Field>

        <div className="flex flex-wrap items-center gap-3 text-label text-muted">
          <span>Owner</span>
          {owner ? <OwnerChip name={owner.display_name} colourIndex={owner.colour_index} deactivated={owner.status === "deactivated"} /> : null}
          {editing && occurrence.done ? (
            <span className="inline-flex items-center gap-1">
              <Check aria-hidden className="size-3.5" /> Done{occurrence.completed_by ? ` by ${occurrence.completed_by.display_name}` : ""}
            </span>
          ) : null}
        </div>

        {error ? (
          <p role="alert" className="text-body text-loss">
            {error}
          </p>
        ) : null}
      </form>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={recurring && scope === "occurrence" ? "Remove this occurrence?" : recurring ? "Delete the whole series?" : "Delete this task?"}
        text={
          recurring && scope === "occurrence"
            ? "Only this one goes. The rest of the series stays as it is."
            : recurring
              ? "Every occurrence of this task is removed."
              : "The task is removed from everyone's calendar."
        }
        confirmLabel={recurring && scope === "occurrence" ? "Remove occurrence" : "Delete"}
        danger
        busy={remove.isPending}
        onConfirm={onDelete}
      />
    </Drawer>
  );
}
