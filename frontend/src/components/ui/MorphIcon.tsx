import { Check, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import { dur, motionLevel } from "../../lib/motion.ts";

/** An action icon that morphs into a tick when the action is done (Micro-interactions → Copy and export).
 * Full: the old icon shrinks out and the tick scales in over --dur-quick. Reduced: a cross-fade. Off: a swap. */
export function MorphIcon({ done, Icon, className = "size-4" }: { done: boolean; Icon: LucideIcon; className?: string }) {
  const level = motionLevel();
  const move = level === "full";
  return (
    <span className={`relative grid place-items-center ${className}`} aria-hidden>
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={done ? "done" : "idle"}
          initial={move ? { scale: 0.5, opacity: 0 } : { opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={move ? { scale: 0.5, opacity: 0 } : { opacity: 0 }}
          transition={{ duration: level === "off" ? 0 : dur.quick() }}
          className="grid place-items-center"
        >
          {done ? <Check className={className} strokeWidth={2.5} /> : <Icon className={className} />}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}
