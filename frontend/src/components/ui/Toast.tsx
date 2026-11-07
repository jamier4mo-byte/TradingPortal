import * as RadixToast from "@radix-ui/react-toast";
import { X } from "lucide-react";
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";

import { motionLevel } from "../../lib/motion.ts";

interface ToastItem {
  id: number;
  title: string;
  text?: string;
  tone?: "neutral" | "win" | "loss";
  undo?: () => void;
}

interface ToastApi {
  toast: (t: Omit<ToastItem, "id">) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}

/** Quiet toasts from the bottom corner (above the tab bar on the phone), with undo where it makes sense.
 * Full: slide up 16px over --dur-standard, fade out over --dur-quick. Reduced: fades. Off: no animation classes. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const animated = motionLevel() !== "off";
  const toast = useCallback((t: Omit<ToastItem, "id">) => {
    setItems((list) => [...list.slice(-2), { ...t, id: Date.now() + Math.random() }]);
  }, []);
  const api = useMemo(() => ({ toast }), [toast]);
  const dismiss = (id: number) => setItems((list) => list.filter((i) => i.id !== id));

  return (
    <ToastContext.Provider value={api}>
      <RadixToast.Provider swipeDirection="down">
        {children}
        {items.map((item) => (
          <RadixToast.Root
            key={item.id}
            duration={item.undo ? 8000 : 5000}
            onOpenChange={(open) => !open && dismiss(item.id)}
            className={`card flex items-start gap-3 p-3 shadow-none ${animated ? "data-[state=open]:anim-toast-in data-[state=closed]:anim-toast-out" : ""}`}
          >
            <span
              aria-hidden
              className={`mt-2 size-2 shrink-0 rounded-full ${
                item.tone === "win" ? "bg-win" : item.tone === "loss" ? "bg-loss" : "bg-accent"
              }`}
            />
            <div className="min-w-0 flex-1 py-1">
              <RadixToast.Title className="text-body font-medium">{item.title}</RadixToast.Title>
              {item.text ? <RadixToast.Description className="text-body text-muted">{item.text}</RadixToast.Description> : null}
            </div>
            {item.undo ? (
              <RadixToast.Action asChild altText="Undo">
                <button type="button" className="btn btn-ghost -my-1 px-3 text-accent" onClick={item.undo}>
                  Undo
                </button>
              </RadixToast.Action>
            ) : null}
            <RadixToast.Close asChild>
              <button type="button" className="btn btn-ghost -my-1 -mr-1 size-11 px-0" aria-label="Dismiss">
                <X aria-hidden className="size-4" />
              </button>
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="safe-bottom fixed left-4 right-24 bottom-20 z-50 flex flex-col gap-2 outline-none tablet:inset-x-auto tablet:right-6 tablet:bottom-6 tablet:w-[360px]" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}
