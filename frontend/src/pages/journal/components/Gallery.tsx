import { ChevronLeft, ChevronRight, X, ZoomIn } from "lucide-react";
import { type PointerEvent, useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import type { Screenshot } from "../../../lib/journal.ts";

import { SLOT_LABEL } from "../../../lib/journal.ts";

/** Swipeable thumbnails (scroll-snap); tap opens the full-resolution viewer with pinch and wheel zoom.
 *  Thumbnails load first; the full image only when opened. */
export function Gallery({ shots }: { shots: Screenshot[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!shots.length) {
    return <div className="grid min-h-40 place-items-center rounded-panel border border-dashed border-border-strong text-body text-muted">No screenshots yet</div>;
  }
  return (
    <>
      <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 [scrollbar-width:thin]" aria-label="Screenshots">
        {shots.map((s, i) => (
          <li key={s.id} className="w-[86%] shrink-0 snap-center tablet:w-[60%] laptop:w-[48%]">
            <button type="button" onClick={() => setOpen(i)} className="group relative block w-full overflow-hidden rounded-panel border border-border bg-surface-2 focus-visible:border-accent" aria-label={`Open ${SLOT_LABEL[s.slot]} screenshot at full size`}>
              <img
                src={s.thumb_url}
                alt=""
                width={s.width}
                height={s.height}
                className="aspect-video w-full object-cover"
                loading={i < 2 ? "eager" : "lazy"}
                decoding="async"
              />
              <span className="absolute left-2 top-2 rounded-pill border border-border bg-bg px-2 py-0.5 text-label">{SLOT_LABEL[s.slot]}</span>
              <span className="absolute right-2 bottom-2 grid size-8 place-items-center rounded-full bg-bg/80 text-muted group-hover:text-text">
                <ZoomIn aria-hidden className="size-4" />
              </span>
            </button>
          </li>
        ))}
      </ul>
      {open !== null ? <Viewer shots={shots} index={open} onIndex={setOpen} onClose={() => setOpen(null)} /> : null}
    </>
  );
}

function Viewer({ shots, index, onIndex, onClose }: { shots: Screenshot[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const shot = shots[index];
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; scale: number } | null>(null);
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const swipeStart = useRef<number | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  }, [index]);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") onIndex(Math.min(shots.length - 1, index + 1));
      if (e.key === "ArrowLeft") onIndex(Math.max(0, index - 1));
      if (e.key === "+" || e.key === "=") setScale((s) => Math.min(6, s * 1.25));
      if (e.key === "-") setScale((s) => Math.max(1, s / 1.25));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, shots.length, onClose, onIndex]);

  const down = (e: PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), scale };
    } else if (scale > 1) {
      drag.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
    } else {
      swipeStart.current = e.clientX;
    }
  };
  const move = (e: PointerEvent) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      setScale(Math.min(6, Math.max(1, (pinch.current.scale * dist) / pinch.current.dist)));
    } else if (drag.current) {
      setOffset({ x: drag.current.ox + (e.clientX - drag.current.x), y: drag.current.oy + (e.clientY - drag.current.y) });
    }
  };
  const up = (e: PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (drag.current) drag.current = null;
    if (swipeStart.current !== null && scale === 1) {
      const dx = e.clientX - swipeStart.current;
      if (dx < -60) onIndex(Math.min(shots.length - 1, index + 1));
      if (dx > 60) onIndex(Math.max(0, index - 1));
    }
    swipeStart.current = null;
    if (scale <= 1.02) setOffset({ x: 0, y: 0 });
  };

  return (
    <Dialog.Root open modal onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Content aria-label={`${SLOT_LABEL[shot.slot]} screenshot ${index + 1} of ${shots.length}`} aria-describedby={undefined} className="fixed inset-0 z-50 flex flex-col bg-bg outline-none">
      <div className="safe-top flex min-h-14 items-center gap-2 border-b border-border px-(--gutter-phone) tablet:px-(--gutter-tablet) desktop:px-(--gutter-desktop)">
        <Dialog.Title asChild>
          <span className="text-body">
            {SLOT_LABEL[shot.slot]} <span className="num text-muted">{index + 1}/{shots.length}</span>
          </span>
        </Dialog.Title>
        <span className="num ml-2 text-label text-muted">{Math.round(scale * 100)}%</span>
        <div className="ml-auto flex items-center gap-1">
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Zoom out" onClick={() => setScale((s) => Math.max(1, s / 1.25))}>
            −
          </button>
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Zoom in" onClick={() => setScale((s) => Math.min(6, s * 1.25))}>
            +
          </button>
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Previous screenshot" onClick={() => onIndex(Math.max(0, index - 1))} disabled={index === 0}>
            <ChevronLeft aria-hidden className="size-5" />
          </button>
          <button type="button" className="btn btn-ghost size-11 px-0" aria-label="Next screenshot" onClick={() => onIndex(Math.min(shots.length - 1, index + 1))} disabled={index === shots.length - 1}>
            <ChevronRight aria-hidden className="size-5" />
          </button>
          <button ref={closeRef} type="button" className="btn btn-ghost size-11 px-0" aria-label="Close viewer" onClick={onClose}>
            <X aria-hidden className="size-5" />
          </button>
        </div>
      </div>
      <div
        className="relative flex-1 touch-none select-none overflow-hidden"
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        onWheel={(e) => setScale((s) => Math.min(6, Math.max(1, s * (e.deltaY < 0 ? 1.1 : 0.9))))}
        onDoubleClick={() => setScale((s) => (s > 1 ? 1 : 2.5))}
      >
        <img
          src={shot.full_url}
          srcSet={`${shot.thumb_url} 400w, ${shot.full_url} ${Math.max(shot.width, 401)}w`}
          sizes={scale > 1 ? `${Math.round(scale * 100)}vw` : "100vw"}
          width={shot.width}
          height={shot.height}
          alt={`${SLOT_LABEL[shot.slot]} chart`}
          draggable={false}
          decoding="async"
          className="absolute inset-0 m-auto max-h-full max-w-full object-contain"
          style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`, transition: pinch.current || drag.current ? "none" : "transform var(--dur-quick) var(--ease-in-enter)" }}
        />
      </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
