import { ImagePlus, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type DragEvent, useEffect, useRef, useState } from "react";

import { api } from "../../../lib/api.ts";
import { imageFiles, prepareImage } from "../../../lib/images.ts";
import { type Screenshot, type Slot, type Trade, uploadScreenshot } from "../../../lib/journal.ts";
import { dur, easeEnter, motionLevel } from "../../../lib/motion.ts";

export type SlotPhase = "idle" | "preparing" | "uploading" | "error";

/** One screenshot slot: paste (when focused), drop, click to pick (camera roll on the phone).
 *  The thumbnail fills as it uploads. Reused by the quick log, Annotate mode and the detail view. */
export function ScreenshotSlot({
  trade,
  slot,
  shot,
  label,
  onChange,
  disabled = false,
  size = "md",
  autoFocus = false,
  onPasted,
}: {
  trade: Trade | null;
  slot: Slot;
  shot?: Screenshot;
  label: string;
  onChange: (trade: Trade) => void;
  disabled?: boolean;
  size?: "md" | "lg";
  autoFocus?: boolean;
  /** Called after a paste lands in this slot (Annotate mode advances focus). */
  onPasted?: () => void;
}) {
  const [phase, setPhase] = useState<SlotPhase>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const level = motionLevel();

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);
  useEffect(() => {
    if (autoFocus) buttonRef.current?.focus();
  }, [autoFocus]);

  const accept = async (file: File | Blob, name?: string, fromPaste = false) => {
    if (!trade || disabled) return;
    setError(null);
    setPhase("preparing");
    const url = URL.createObjectURL(file);
    setPreview(url);
    try {
      const prepared = await prepareImage(file, name);
      setPhase("uploading");
      const updated = await uploadScreenshot(trade.id, prepared.full, slot, {
        thumb: prepared.thumb,
        capturedAt: prepared.capturedAt,
        originalFilename: prepared.name,
      });
      setPhase("idle");
      onChange(updated);
      if (fromPaste) onPasted?.();
    } catch (err) {
      setPhase("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const [file] = imageFiles(e.dataTransfer);
    if (file) void accept(file, file.name);
  };

  const remove = async () => {
    if (!shot || !trade) return;
    await api.delete(`/api/screenshots/${shot.id}`);
    const updated = await api.get<Trade>(`/api/trades/${trade.id}`);
    setPreview(null);
    onChange(updated);
  };

  const busy = phase === "preparing" || phase === "uploading";
  const src = busy || phase === "error" ? preview : shot ? shot.thumb_url : null;
  const sizeCls = size === "lg" ? "min-h-44 tablet:min-h-56" : "min-h-28";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-label text-muted">{label}</span>
        {shot && !busy && !disabled ? (
          <button type="button" onClick={remove} className="btn btn-ghost -my-2 size-11 px-0" aria-label={`Remove ${label} screenshot`}>
            <Trash2 aria-hidden className="size-4" />
          </button>
        ) : null}
      </div>
      <button
        ref={buttonRef}
        type="button"
        disabled={disabled || !trade}
        aria-label={shot ? `${label} screenshot. Press Enter to replace, or paste a new one.` : `Add ${label} screenshot: paste, drop or choose a file`}
        aria-busy={busy}
        data-slot={slot}
        onClick={() => inputRef.current?.click()}
        onPaste={(e) => {
          const [file] = imageFiles(e.clipboardData);
          if (file) {
            e.preventDefault();
            void accept(file, file.name || "pasted.png", true);
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`relative flex ${sizeCls} w-full items-center justify-center overflow-hidden rounded-panel border bg-surface-2 text-muted transition-colors duration-(--dur-quick) ${
          over ? "border-accent" : src ? "border-border" : "border-dashed border-input hover:border-muted"
        } disabled:cursor-not-allowed disabled:opacity-60`}
      >
        <AnimatePresence initial={false}>
          {src ? (
            <motion.img
              key={src}
              src={src}
              alt=""
              initial={level === "full" ? { opacity: 0, scale: 0.94 } : { opacity: 0 }}
              animate={{ opacity: busy ? 0.55 : 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: level === "off" ? 0 : dur.standard(), ease: easeEnter }}
              className="absolute inset-0 size-full object-cover"
            />
          ) : null}
        </AnimatePresence>
        {!src ? (
          <span className="flex flex-col items-center gap-1 px-3 text-center text-label">
            <ImagePlus aria-hidden className="size-5" strokeWidth={1.5} />
            <span className="hidden tablet:inline">Paste, drop or click</span>
            <span className="tablet:hidden">Tap to add</span>
          </span>
        ) : null}
        {busy ? (
          <span className="absolute inset-x-0 bottom-0 h-1 overflow-hidden bg-surface-2">
            <motion.span
              className="block h-full origin-left bg-accent"
              initial={{ scaleX: 0.15 }}
              animate={{ scaleX: phase === "preparing" ? 0.45 : 0.9 }}
              transition={{ duration: level === "full" ? dur.emphasis() : 0, ease: easeEnter }}
            />
          </span>
        ) : null}
        {phase === "error" ? (
          <span role="alert" className="absolute inset-x-2 bottom-2 flex items-center gap-1 rounded-panel bg-bg/90 px-2 py-1 text-label text-loss">
            <X aria-hidden className="size-3" /> {error}
          </span>
        ) : null}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void accept(file, file.name);
          e.target.value = "";
        }}
      />
    </div>
  );
}
