import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { motionLevel } from "../../lib/motion.ts";
import { useReturnFocus } from "./returnFocus.ts";

/** Confirms a change that's hard to undo. Says exactly what will happen. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  text,
  confirmLabel = "Confirm",
  danger = false,
  onConfirm,
  busy = false,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  text?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  busy?: boolean;
  children?: ReactNode;
}) {
  // Fade-and-scale in (.96 → 1), fade out; the keyframes carry the centring transform. Off: no animation.
  const animated = motionLevel() !== "off";
  const returnFocus = useReturnFocus(open);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={`fixed inset-0 z-40 bg-bg/70 ${animated ? "data-[state=open]:anim-fade-in data-[state=closed]:anim-fade-out" : ""}`} />
        <Dialog.Content
          {...returnFocus}
          className={`card fixed left-1/2 top-1/2 z-50 w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 p-5 ${
            animated ? "data-[state=open]:anim-dialog-in data-[state=closed]:anim-dialog-out" : ""
          }`}
        >
          <Dialog.Title className="text-title font-semibold">{title}</Dialog.Title>
          {text ? <Dialog.Description className="mt-2 text-body text-muted">{text}</Dialog.Description> : null}
          {children}
          <div className="mt-5 flex flex-col-reverse gap-2 tablet:flex-row tablet:justify-end">
            <Dialog.Close asChild>
              <button type="button" className="btn btn-secondary">
                Cancel
              </button>
            </Dialog.Close>
            <button type="button" className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm} disabled={busy}>
              {confirmLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
