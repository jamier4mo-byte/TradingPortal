import * as Dialog from "@radix-ui/react-dialog";
import { BookOpen, CalendarDays, Home, LineChart, Newspaper, Search, Settings, Shield, Tags } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth.tsx";
import { motionLevel } from "../lib/motion.ts";
import { useReturnFocus } from "./ui/returnFocus.ts";

interface Command {
  label: string;
  to: string;
  icon: typeof Home;
  keywords?: string;
  adminOnly?: boolean;
}

const COMMANDS: Command[] = [
  { label: "Hub", to: "/", icon: Home, keywords: "home dashboard" },
  { label: "Replay Journal", to: "/journal", icon: BookOpen, keywords: "strategies trades backtest" },
  { label: "Journal · Trash", to: "/journal/trash", icon: BookOpen, keywords: "deleted restore" },
  { label: "Journal · Log a trade", to: "/journal?quicklog=1", icon: BookOpen, keywords: "quick log new ideal trade" },
  { label: "News Room", to: "/news", icon: Newspaper, keywords: "calendar events economic" },
  { label: "News · Week ahead", to: "/news/week", icon: Newspaper, keywords: "sunday plan high impact" },
  { label: "News · Alerts", to: "/settings/alerts", icon: Newspaper, keywords: "push notifications reminders" },
  { label: "Markets", to: "/markets", icon: LineChart, keywords: "prices watchlist ticker twelve data quotes" },
  { label: "Calendar", to: "/calendar", icon: CalendarDays, keywords: "tasks week" },
  { label: "Calendar · New task", to: "/calendar?new=1", icon: CalendarDays, keywords: "add task backtest session review" },
  { label: "Tags", to: "/tags", icon: Tags, keywords: "vocabulary synonyms" },
  { label: "Settings", to: "/settings", icon: Settings, keywords: "profile password passkeys keys motion" },
  { label: "Admin · Users", to: "/admin/users", icon: Shield, keywords: "invite roles", adminOnly: true },
  { label: "Admin · Tags", to: "/admin/tags", icon: Shield, keywords: "merge approve", adminOnly: true },
];

/** Cmd+K: jump to any screen. Strategies, trades and instruments join the list in later prompts. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [q, setQ] = useState("");
  const [index, setIndex] = useState(0);
  const navigate = useNavigate();
  const { user } = useAuth();

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return COMMANDS.filter((c) => !c.adminOnly || user?.role === "admin").filter(
      (c) => !needle || `${c.label} ${c.keywords ?? ""}`.toLowerCase().includes(needle),
    );
  }, [q, user?.role]);

  useEffect(() => {
    setIndex(0);
  }, [q]);
  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  const go = (to: string) => {
    onOpenChange(false);
    navigate(to);
  };
  // Fade-and-scale open (.96 → 1) and fade close (Micro-interactions → Command palette). Off: nothing.
  const animated = motionLevel() !== "off";
  const returnFocus = useReturnFocus(open);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={`fixed inset-0 z-40 bg-bg/70 ${animated ? "data-[state=open]:anim-fade-in data-[state=closed]:anim-fade-out" : ""}`} />
        <Dialog.Content
          {...returnFocus}
          aria-describedby={undefined}
          className={`card fixed left-1/2 top-[12dvh] z-50 w-[calc(100%-32px)] max-w-lg -translate-x-1/2 overflow-hidden p-0 ${
            animated ? "data-[state=open]:anim-palette-in data-[state=closed]:anim-palette-out" : ""
          }`}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex((i) => Math.min(results.length - 1, i + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex((i) => Math.max(0, i - 1));
            } else if (e.key === "Enter" && results[index]) {
              e.preventDefault();
              go(results[index].to);
            }
          }}
        >
          <Dialog.Title className="sr-only">Jump to</Dialog.Title>
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search aria-hidden className="size-4 text-muted" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Jump to a screen"
              aria-label="Jump to a screen"
              className="min-h-12 flex-1 rounded-panel bg-transparent text-body placeholder:text-muted focus-visible:-outline-offset-4"
            />
            <kbd className="hidden rounded border border-border px-1.5 font-mono text-label text-muted tablet:inline">esc</kbd>
          </div>
          <ul role="listbox" aria-label="Screens" className="max-h-[50dvh] overflow-y-auto p-2">
            {results.length === 0 ? (
              <li className="px-3 py-6 text-center text-body text-muted">Nothing matches &ldquo;{q}&rdquo;</li>
            ) : (
              results.map((c, i) => (
                <li key={c.to} role="option" aria-selected={i === index}>
                  <button
                    type="button"
                    onMouseEnter={() => setIndex(i)}
                    onClick={() => go(c.to)}
                    className={`flex min-h-11 w-full items-center gap-3 rounded-panel px-3 text-left text-body ${
                      i === index ? "bg-accent-soft text-text" : "text-muted"
                    }`}
                  >
                    <c.icon aria-hidden className="size-4" strokeWidth={1.75} />
                    {c.label}
                  </button>
                </li>
              ))
            )}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
