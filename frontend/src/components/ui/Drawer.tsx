import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { type ReactNode, useCallback } from "react";

import { motionLevel } from "../../lib/motion.ts";
import { useDevice } from "../../lib/useMediaQuery.ts";

/** Viewport coordinates of the thing that opened a drawer (its centre), so the panel can grow out of it. */
export interface DrawerOrigin {
  x: number;
  y: number;
}

export function originOf(
  el: Element | null | undefined,
): DrawerOrigin | undefined {
  if (!el) return undefined;
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

/** Right-side panel on desktop and tablet; a bottom sheet on the phone. The overlay dims and the panel
 * slides in over --dur-standard and leaves the way it came over --dur-quick (Radix keeps it mounted while
 * the data-[state=closed] animation runs). With `origin`, the panel starts from the tapped row instead (a
 * calendar task opening its detail). Reduced: fades. Off: no animation classes at all. */
export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  origin,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  origin?: DrawerOrigin;
}) {
  const phone = useDevice() === "phone";
  const animated = motionLevel() !== "off";
  const fromOrigin = motionLevel() === "full" && origin !== undefined;

  // Runs when the panel mounts (Radix mounts Content on open), before its first paint: measure where the
  // panel sits and point the enter keyframe at the origin. Custom properties only; the keyframe reads them.
  const contentRef = useCallback(
    (el: HTMLDivElement | null) => {
      if (!el) return;
      if (!fromOrigin || !origin) {
        el.style.removeProperty("--origin-dx");
        el.style.removeProperty("--origin-dy");
        el.style.removeProperty("--origin-scale");
        return;
      }
      const r = el.getBoundingClientRect();
      const dx = origin.x - (r.left + r.width / 2);
      const dy = origin.y - (r.top + r.height / 2);
      el.style.setProperty("--origin-dx", `${Math.round(dx * 0.35)}px`);
      el.style.setProperty("--origin-dy", `${Math.round(dy * 0.35)}px`);
      el.style.setProperty("--origin-scale", "0.96");
    },
    [fromOrigin, origin],
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={`fixed inset-0 z-40 bg-bg/70 ${animated ? "data-[state=open]:anim-fade-in data-[state=closed]:anim-fade-out" : ""}`}
        />
        <Dialog.Content
          ref={contentRef}
          className={
            phone
              ? `safe-bottom fixed inset-x-0 bottom-0 z-50 flex max-h-[88dvh] flex-col rounded-t-card border border-border bg-surface-1 ${
                  animated
                    ? "data-[state=open]:anim-sheet-in data-[state=closed]:anim-panel-out"
                    : ""
                }`
              : `fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-surface-1 ${
                  animated
                    ? "data-[state=open]:anim-drawer-in data-[state=closed]:anim-panel-out"
                    : ""
                }`
          }
        >
          {phone ? (
            <div
              aria-hidden
              className="mx-auto mt-2 h-1 w-10 rounded-pill bg-border-strong"
            />
          ) : null}
          <header className="flex items-start gap-3 px-5 pt-4 pb-3">
            <div className="min-w-0">
              <Dialog.Title className="text-title font-semibold">
                {title}
              </Dialog.Title>
              {description ? (
                <Dialog.Description className="text-body text-muted">
                  {description}
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="btn btn-ghost -mr-2 ml-auto size-11 px-0"
                aria-label="Close"
              >
                <X aria-hidden className="size-5" />
              </button>
            </Dialog.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
            {children}
          </div>
          {footer ? (
            <footer className="border-t border-border px-5 py-3">
              {footer}
            </footer>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
