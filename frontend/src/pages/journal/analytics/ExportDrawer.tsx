import { Check, Copy, FileDown, FileSpreadsheet, Printer } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { Drawer, useToast } from "../../../components/ui/index.ts";
import { type AnalyticsQuery, exportUrl } from "../../../lib/analytics.ts";
import { api } from "../../../lib/api.ts";
import { motionLevel } from "../../../lib/motion.ts";

const CONTENTS = [
  ["README_prompt.md", "A ready-to-paste brief telling Claude what's in the bundle and what to look for"],
  ["strategy.md", "The idea, rulebook, reasoning template, ideal profile and KPIs with formulas"],
  ["trades.jsonl", "One line per trade: every field, your reasoning, tags, rules and outcome"],
  ["images/", "HTF, Entry and Outcome screenshots, resized for Claude (long edge ≤ 1,568 px)"],
  ["manifest.json", "Counts, the filters used and a SHA-256 for every file"],
] as const;

/** The icon morphs into a tick when it's done (Micro-interactions → Copy and export). */
export function MorphIcon({ done, Icon }: { done: boolean; Icon: typeof Copy }) {
  const animate = motionLevel() === "full";
  return (
    <span className="relative grid size-4 place-items-center" aria-hidden>
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={done ? "done" : "idle"}
          initial={animate ? { scale: 0.5, opacity: 0 } : { opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={animate ? { scale: 0.5, opacity: 0 } : { opacity: 0 }}
          transition={{ duration: animate ? 0.15 : 0 }}
          className="grid place-items-center"
        >
          {done ? <Check className="size-4" strokeWidth={2.5} /> : <Icon className="size-4" />}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function useCopyForAi(query: AnalyticsQuery) {
  const { toast } = useToast();
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const copy = async () => {
    setState("busy");
    try {
      // Safari only allows clipboard writes inside the gesture, so hand it a promise of the text.
      const text = api.post<{ text: string; trades: number }>("/api/analytics/copy", query);
      if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ "text/plain": text.then((t) => new Blob([t.text], { type: "text/plain" })) })]);
      } else {
        await navigator.clipboard.writeText((await text).text);
      }
      const { trades } = await text;
      setState("done");
      toast({ title: "Copied for AI", text: `strategy.md and ${trades} trades are on the clipboard. Paste into Claude.` });
      window.setTimeout(() => setState("idle"), 2000);
    } catch (err) {
      setState("idle");
      toast({ title: "Couldn't copy", text: err instanceof Error ? err.message : "The browser blocked the clipboard.", tone: "loss" });
    }
  };
  return { copy, state };
}

export function ExportDrawer({ open, onOpenChange, query, filtersText, tradeCount }: { open: boolean; onOpenChange: (open: boolean) => void; query: AnalyticsQuery; filtersText: string; tradeCount: number }) {
  const [images, setImages] = useState(true);
  const { copy, state } = useCopyForAi(query);
  const [downloaded, setDownloaded] = useState<"ai" | "csv" | null>(null);
  const mark = (kind: "ai" | "csv") => {
    setDownloaded(kind);
    window.setTimeout(() => setDownloaded(null), 2000);
  };
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="Export" description={`${tradeCount} trades · ${filtersText}`}>
      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-3">
          <h3 className="text-body font-semibold">Export for AI</h3>
          <p className="text-body text-muted">A zip you drop into Claude. It uses the filters you have on now.</p>
          <ul className="flex flex-col gap-1.5">
            {CONTENTS.map(([name, text]) => (
              <li key={name} className="rounded-panel border border-border bg-surface-2 px-3 py-2">
                <p className="font-mono text-label text-text">{name}</p>
                <p className="text-label text-muted">{text}</p>
              </li>
            ))}
          </ul>
          <label className="flex min-h-11 items-center gap-3 text-body">
            <input type="checkbox" className="size-5 accent-accent" checked={images} onChange={(e) => setImages(e.target.checked)} />
            Include screenshots
          </label>
          <a href={exportUrl("ai", query, images)} download className="btn btn-primary" onClick={() => mark("ai")}>
            <MorphIcon done={downloaded === "ai"} Icon={FileDown} /> Download zip for AI
          </a>
          <button type="button" className="btn btn-secondary" onClick={() => void copy()} disabled={state === "busy"}>
            <MorphIcon done={state === "done"} Icon={Copy} /> {state === "done" ? "Copied" : "Copy for AI"}
          </button>
          <p className="text-label text-muted">Copy for AI puts strategy.md plus a compact KPI and trade summary on the clipboard, without screenshots.</p>
        </section>
        <section className="flex flex-col gap-3 border-t border-border pt-5">
          <h3 className="text-body font-semibold">Other formats</h3>
          <a href={exportUrl("csv", query)} download className="btn btn-secondary" onClick={() => mark("csv")}>
            <MorphIcon done={downloaded === "csv"} Icon={FileSpreadsheet} /> Download CSV
          </a>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              onOpenChange(false);
              window.setTimeout(() => window.print(), 300);
            }}
          >
            <Printer aria-hidden className="size-4" /> Save as PDF
          </button>
          <p className="text-label text-muted">Save as PDF opens the print dialog with a clean, light layout of this Analytics view; choose “Save as PDF”.</p>
        </section>
      </div>
    </Drawer>
  );
}
