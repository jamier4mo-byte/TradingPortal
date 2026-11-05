import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { useDevice } from "../../lib/useMediaQuery.ts";

/** Right-side panel on desktop and tablet; a bottom sheet on the phone. */
export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const phone = useDevice() === "phone";
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-bg/70 data-[state=open]:animate-[page-enter-fade_var(--dur-standard)]" />
        <Dialog.Content
          className={
            phone
              ? "safe-bottom fixed inset-x-0 bottom-0 z-50 flex max-h-[88dvh] flex-col rounded-t-card border border-border bg-surface-1 data-[state=open]:animate-[page-enter_var(--dur-standard)_var(--ease-in-enter)]"
              : "fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-surface-1 data-[state=open]:animate-[page-enter_var(--dur-standard)_var(--ease-in-enter)]"
          }
        >
          {phone ? <div aria-hidden className="mx-auto mt-2 h-1 w-10 rounded-pill bg-border-strong" /> : null}
          <header className="flex items-start gap-3 px-5 pt-4 pb-3">
            <div className="min-w-0">
              <Dialog.Title className="text-title font-semibold">{title}</Dialog.Title>
              {description ? <Dialog.Description className="text-body text-muted">{description}</Dialog.Description> : null}
            </div>
            <Dialog.Close asChild>
              <button type="button" className="btn btn-ghost -mr-2 ml-auto size-11 px-0" aria-label="Close">
                <X aria-hidden className="size-5" />
              </button>
            </Dialog.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">{children}</div>
          {footer ? <footer className="border-t border-border px-5 py-3">{footer}</footer> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
