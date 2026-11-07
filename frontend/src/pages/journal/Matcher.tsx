import { ArrowLeft, Check, ImagePlus } from "lucide-react";
import { motion } from "motion/react";
import { type DragEvent, Fragment, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Card from "../../components/Card.tsx";
import { ErrorState, OfflineState, SkeletonText, useToast } from "../../components/ui/index.ts";
import { offlinePending } from "../../lib/offline.ts";
import { api } from "../../lib/api.ts";
import { imageFiles, type PreparedImage, prepareImage } from "../../lib/images.ts";
import { fmtR, fmtUkDateTime, fmtUkTime, LABELLED_SLOTS, type LabelledSlot, type Match, SLOT_LABEL, slotShot, type Trade, uploadScreenshot, useInvalidateJournal, useSession, useSessionTrades } from "../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../lib/motion.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";

type Confidence = Match["confidence"];
interface Item {
  key: string;
  name: string;
  preview: string;
  prepared?: PreparedImage;
  tradeId: number | null;
  slot: LabelledSlot | null;
  confidence: Confidence;
  reason: string;
  state: "preparing" | "ready" | "uploading" | "done" | "error";
  error?: string;
}

const CONF_LABEL: Record<Confidence, string> = { high: "Sure", medium: "Likely", low: "Guess", none: "Unmatched" };

/** Bulk matcher (U3): drop every screenshot at once; pair by filename, then capture time, then order.
 *  A trades × (HTF, Entry, Outcome) grid with confidence badges and an Unmatched tray. Drag or tap to fix. */
export default function Matcher() {
  const sid = Number(useParams().sid);
  const session = useSession(sid);
  const trades = useSessionTrades(sid);
  if (offlinePending(session) || offlinePending(trades)) {
    return (
      <div className="card">
        <OfflineState what="This session" />
      </div>
    );
  }
  if (session.isPending || trades.isPending) return <SkeletonText lines={6} className="max-w-md" />;
  if (session.isError || trades.isError) {
    return <ErrorState title="Session didn't load" text={(session.error ?? trades.error)?.message} onRetry={() => void Promise.all([session.refetch(), trades.refetch()])} />;
  }
  return <MatcherScreen sessionId={sid} strategyId={session.data.strategy_id} trades={trades.data} canEdit={session.data.can_edit} timezone={session.data.csv_timezone} />;
}

function MatcherScreen({ sessionId, strategyId, trades, canEdit, timezone }: { sessionId: number; strategyId: number; trades: Trade[]; canEdit: boolean; timezone: string }) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const invalidate = useInvalidateJournal();
  const device = useDevice();
  const level = motionLevel();
  const [items, setItems] = useState<Item[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => () => items.forEach((i) => URL.revokeObjectURL(i.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps

  const addFiles = async (files: File[]) => {
    if (!files.length || !canEdit) return;
    const fresh: Item[] = files.map((f, i) => ({
      key: `${Date.now()}-${i}-${f.name}`,
      name: f.name,
      preview: URL.createObjectURL(f),
      tradeId: null,
      slot: null,
      confidence: "none",
      reason: "Reading…",
      state: "preparing",
    }));
    setItems((cur) => [...cur, ...fresh]);
    const prepared = await Promise.all(
      files.map(async (f, i) => {
        try {
          const p = await prepareImage(f, f.name);
          setItems((cur) => cur.map((it) => (it.key === fresh[i].key ? { ...it, prepared: p, state: "ready" } : it)));
          return { key: fresh[i].key, p };
        } catch (err) {
          setItems((cur) => cur.map((it) => (it.key === fresh[i].key ? { ...it, state: "error", error: err instanceof Error ? err.message : "Couldn't read" } : it)));
          return null;
        }
      }),
    );
    const ok = prepared.filter((x): x is { key: string; p: PreparedImage } => !!x);
    // Already-assigned items hold their slots; the server only sees what's still free.
    const current = itemsRef.current;
    const taken = new Set(current.filter((i) => i.tradeId && i.slot && !ok.some((o) => o.key === i.key)).map((i) => `${i.tradeId}:${i.slot}`));
    const matches = await api.post<Match[]>(`/api/journal/sessions/${sessionId}/match`, {
      files: ok.map((o) => ({ name: `${o.key}::${o.p.name}`, captured_at: o.p.capturedAt?.toISOString() ?? null, time_source: o.p.timeSource })),
    });
    setItems((cur) =>
      cur.map((it) => {
        const m = matches.find((x) => x.file.startsWith(`${it.key}::`));
        if (!m) return it;
        const slot = m.slot && (LABELLED_SLOTS as readonly string[]).includes(m.slot) ? (m.slot as LabelledSlot) : null;
        const clash = m.trade_id && slot && taken.has(`${m.trade_id}:${slot}`);
        return clash ? { ...it, tradeId: null, slot: null, confidence: "none", reason: "slot already filled" } : { ...it, tradeId: m.trade_id, slot, confidence: m.confidence, reason: m.reason };
      }),
    );
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(null);
    void addFiles(imageFiles(e.dataTransfer));
  };

  /** Put `key` into (tradeId, slot); whatever was there swaps into the moved item's old place. */
  const place = (key: string, tradeId: number | null, slot: LabelledSlot | null) => {
    setItems((cur) => {
      const moving = cur.find((i) => i.key === key);
      if (!moving) return cur;
      const occupant = tradeId && slot ? cur.find((i) => i.tradeId === tradeId && i.slot === slot && i.key !== key) : undefined;
      return cur.map((i) => {
        if (i.key === key) return { ...i, tradeId, slot, confidence: tradeId ? "high" : "none", reason: tradeId ? "placed by you" : "in the tray" };
        if (occupant && i.key === occupant.key) return { ...i, tradeId: moving.tradeId, slot: moving.slot, confidence: moving.tradeId ? "high" : "none", reason: moving.tradeId ? "swapped" : "in the tray" };
        return i;
      });
    });
    setPicked(null);
  };

  const saveAll = async () => {
    const todo = items.filter((i) => i.tradeId && i.slot && i.prepared && i.state === "ready");
    if (!todo.length) return;
    setSaving(true);
    let okCount = 0;
    const queue = [...todo];
    const worker = async () => {
      for (let it = queue.shift(); it; it = queue.shift()) {
        const item = it;
        setItems((cur) => cur.map((i) => (i.key === item.key ? { ...i, state: "uploading" } : i)));
        try {
          await uploadScreenshot(item.tradeId!, item.prepared!.full, item.slot!, { thumb: item.prepared!.thumb, capturedAt: item.prepared!.capturedAt, originalFilename: item.name });
          okCount++;
          setItems((cur) => cur.map((i) => (i.key === item.key ? { ...i, state: "done" } : i)));
        } catch (err) {
          setItems((cur) => cur.map((i) => (i.key === item.key ? { ...i, state: "error", error: err instanceof Error ? err.message : "Upload failed" } : i)));
        }
      }
    };
    await Promise.all([worker(), worker()]);
    setSaving(false);
    invalidate(strategyId);
    toast({ title: `${okCount} ${okCount === 1 ? "screenshot" : "screenshots"} added`, text: okCount === todo.length ? "Next: the reasons." : `${todo.length - okCount} failed. Try them again.` });
    if (okCount === todo.length) navigate(`/journal/sessions/${sessionId}/annotate`);
  };

  const tray = items.filter((i) => !i.tradeId);
  const assigned = items.filter((i) => i.tradeId && i.slot && i.state !== "done").length;
  const auto = items.filter((i) => i.tradeId && i.confidence !== "none").length;
  const readyCount = items.filter((i) => i.tradeId && i.state === "ready").length;

  const cell = (t: Trade, slot: LabelledSlot) => {
    const item = items.find((i) => i.tradeId === t.id && i.slot === slot);
    const existing = slotShot(t, slot);
    const id = `${t.id}:${slot}`;
    const isOver = over === id;
    return (
      <button
        type="button"
        key={id}
        disabled={!canEdit}
        aria-label={`${SLOT_LABEL[slot]} for trade ${trades.indexOf(t) + 1}${item ? `: ${item.name}, ${CONF_LABEL[item.confidence]}` : existing ? ": already has a screenshot" : ": empty"}`}
        aria-pressed={picked === item?.key}
        onClick={() => {
          if (picked) place(picked, t.id, slot);
          else if (item) setPicked(item.key);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(id);
        }}
        onDragLeave={() => setOver(null)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(null);
          const key = e.dataTransfer.getData("text/plain");
          if (key) place(key, t.id, slot);
          else void addFiles(imageFiles(e.dataTransfer)).then(() => place(itemsRef.current[itemsRef.current.length - 1]?.key, t.id, slot));
        }}
        draggable={!!item}
        onDragStart={(e) => item && e.dataTransfer.setData("text/plain", item.key)}
        className={`relative flex aspect-video min-h-11 w-full items-center justify-center overflow-hidden rounded-panel border bg-surface-2 text-label text-muted transition-colors duration-(--dur-quick) ${
          isOver || picked === item?.key ? "border-accent" : picked && !item ? "border-dashed border-accent/60" : item ? "border-border" : "border-dashed border-input"
        }`}
      >
        {item ? (
          <>
            <img src={item.preview} alt="" className={`absolute inset-0 size-full object-cover ${item.state === "done" ? "" : item.state === "uploading" ? "opacity-60" : ""}`} />
            <span className={`absolute left-1.5 top-1.5 rounded-pill border px-1.5 py-0.5 text-label ${item.confidence === "high" ? "border-accent bg-bg text-accent" : item.confidence === "medium" ? "border-accent/50 bg-bg text-text" : "border-border-strong bg-bg text-muted"}`}>
              {CONF_LABEL[item.confidence]}
            </span>
            {item.state === "done" ? (
              <span className="absolute right-1.5 bottom-1.5 grid size-6 place-items-center rounded-full bg-accent text-on-accent">
                <Check aria-hidden className="size-3.5" strokeWidth={3} />
              </span>
            ) : null}
            {item.state === "uploading" ? <span className="absolute inset-x-0 bottom-0 h-1 bg-accent" /> : null}
          </>
        ) : existing ? (
          <>
            <img src={existing.thumb_url} alt="" className="absolute inset-0 size-full object-cover opacity-50" />
            <span className="relative rounded-pill border border-border bg-bg px-1.5 py-0.5">Already added</span>
          </>
        ) : (
          <span>{SLOT_LABEL[slot]}</span>
        )}
      </button>
    );
  };

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-2">
        <Link to={`/journal/strategies/${strategyId}`} className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text">
          <ArrowLeft aria-hidden className="size-4" /> Back to the strategy
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-heading font-semibold">Match screenshots</h1>
          <span className="num text-body text-muted">
            {trades.length} trades · {trades.length * LABELLED_SLOTS.length} slots
          </span>
          {items.length ? (
            <span className="num text-body text-muted" aria-live="polite">
              · {auto} of {items.length} matched automatically
            </span>
          ) : null}
          {canEdit ? (
            <button type="button" className="btn btn-primary ml-auto" onClick={saveAll} disabled={saving || readyCount === 0}>
              <Check aria-hidden className="size-4" /> Save all{assigned ? ` (${assigned})` : ""}
            </button>
          ) : null}
        </div>
      </header>

      {canEdit ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setOver("zone");
          }}
          onDragLeave={() => setOver(null)}
          onDrop={onDrop}
          className={`flex min-h-24 flex-col items-center justify-center gap-1 rounded-card border border-dashed bg-surface-1 px-4 text-center text-body text-muted ${over === "zone" ? "border-accent" : "border-input hover:border-muted"}`}
        >
          <ImagePlus aria-hidden className="size-5" strokeWidth={1.5} />
          <span>
            <span className="text-text">{device === "phone" ? "Choose from Photos" : "Drop all the screenshots here"}</span>
            {device === "phone" ? "" : " or click to choose"}
          </span>
          <span className="text-label">Named like T03_htf, T03_entry or 3o, or by the time they were taken ({timezone === "UTC" ? "UTC" : "UK"} chart time).</span>
        </button>
      ) : null}
      <input ref={inputRef} type="file" accept="image/*" multiple className="hidden" tabIndex={-1} aria-label="Screenshots" onChange={(e) => void addFiles(Array.from(e.target.files ?? [])).then(() => (e.target.value = ""))} />

      {device !== "desktop" ? (
        <Card title="Trades" subtitle={picked ? "Now tap where it belongs" : "Tap a thumbnail to pick it up, then tap its slot."}>
        <ul className="flex flex-col gap-2" aria-label="Trades">
          {trades.map((t, i) => (
            <li key={t.id} className="rounded-panel border border-border bg-surface-2 p-3">
              <p className="num flex items-center gap-2 text-body">
                <span className="text-muted">{i + 1}.</span> <span className="font-mono">{t.instrument}</span> {fmtUkTime(t.opened_at)} <span className="ml-auto">{fmtR(t.r_multiple)}</span>
              </p>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {LABELLED_SLOTS.map((slot) => cell(t, slot))}
              </div>
            </li>
          ))}
        </ul>
        </Card>
      ) : (
        <Card title="Trades" subtitle={picked ? "Now tap where it belongs" : "Tap a thumbnail to pick it up, then tap its slot. Or drag."}>
          <div className="grid max-w-[1300px] grid-cols-[minmax(0,1fr)_180px_180px_180px] gap-x-4 gap-y-2 desktop:grid-cols-[minmax(0,1fr)_220px_220px_220px]">
            <span className="text-label text-muted">Trade</span>
            {LABELLED_SLOTS.map((slot) => (
              <span key={slot} className="text-label text-muted">
                {SLOT_LABEL[slot]}
              </span>
            ))}
            {trades.map((t, i) => (
              <Fragment key={t.id}>
                <div className="flex min-h-11 flex-col justify-center">
                  <p className="num text-body">
                    <span className="text-muted">{i + 1}.</span> <span className="font-mono">{t.instrument}</span> {t.side === "buy" ? "long" : "short"} <span className={`ml-2 font-medium ${(t.r_multiple ?? 0) > 0 ? "text-win" : (t.r_multiple ?? 0) < 0 ? "text-loss" : ""}`}>{fmtR(t.r_multiple)}</span>
                  </p>
                  <p className="num text-label text-muted">
                    {fmtUkDateTime(t.opened_at)} → {fmtUkTime(t.closed_at)}
                  </p>
                </div>
                {LABELLED_SLOTS.map((slot) => cell(t, slot))}
              </Fragment>
            ))}
          </div>
        </Card>
      )}

      <Card title="Unmatched" subtitle={tray.length ? "Tap one, then tap the slot it belongs in" : "Everything found a slot"}>
        {tray.length ? (
          <ul className="flex flex-wrap gap-2" aria-label="Unmatched screenshots">
            {tray.map((i) => (
              <motion.li
                key={i.key}
                initial={level === "full" ? { opacity: 0, scale: 0.9 } : false}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }}
              >
                <button
                  type="button"
                  aria-label={`${i.name}: ${i.reason}`}
                  aria-pressed={picked === i.key}
                  onClick={() => setPicked(picked === i.key ? null : i.key)}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/plain", i.key)}
                  className={`relative block h-24 w-40 overflow-hidden rounded-panel border bg-surface-2 ${picked === i.key ? "border-accent" : "border-border"}`}
                >
                  <img src={i.preview} alt="" className="size-full object-cover" />
                  <span className="absolute inset-x-0 bottom-0 truncate bg-bg px-1.5 py-0.5 text-left text-label">{i.name}</span>
                  {i.state === "error" ? <span className="absolute inset-x-0 top-0 bg-bg px-1.5 text-label text-loss">{i.error}</span> : null}
                </button>
              </motion.li>
            ))}
          </ul>
        ) : (
          <p className="text-body text-muted">{items.length ? "Every screenshot has a slot." : "Drop the images above to start."}</p>
        )}
        {picked ? (
          <button type="button" className="btn btn-ghost mt-3" onClick={() => place(picked, null, null)}>
            Move the picked one here
          </button>
        ) : null}
      </Card>
    </div>
  );
}
