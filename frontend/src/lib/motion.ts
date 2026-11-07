/** Motion presets built from the tokens in index.css. The only animation library is `motion`. */
import type { Transition, Variants } from "motion/react";
import { useRef } from "react";

const ms = (name: string, fallback: number) => {
  if (typeof window === "undefined") return fallback / 1000;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const n = parseFloat(raw);
  if (Number.isNaN(n)) return fallback / 1000;
  // The production build minifies "600ms" to ".6s": read the unit rather than assuming milliseconds.
  return raw.endsWith("ms") ? n / 1000 : n;
};

export const dur = {
  quick: () => ms("--dur-quick", 150),
  standard: () => ms("--dur-standard", 250),
  emphasis: () => ms("--dur-emphasis", 500),
  /** Launch loader minimum on a tool's first open each day (F14). */
  launch: () => ms("--dur-launch", 600),
  /** The portal intro after sign-in (about 1 s, proposed token). */
  intro: () => ms("--dur-intro", 1000),
};

/** cubic-bezier(.16,1,.3,1): ease-out for things entering. */
export const easeEnter = [0.16, 1, 0.3, 1] as const;
/** cubic-bezier(.7,0,.84,0): ease-in for things leaving. */
export const easeLeave = [0.7, 0, 0.84, 0] as const;
export const spring: Transition = { type: "spring", stiffness: 500, damping: 32, mass: 0.8 };

export type MotionLevel = "full" | "reduced" | "off";

/** Resolves a stored preference the way the CSS does (`:root:not([data-motion="full"])` + the OS query):
 * Full overrides the OS reduce-motion setting on purpose (a user choice, see the tokens skill); Reduced and
 * Off are what they say; no preference (signed out) follows the OS. */
export function resolveMotion(pref: string | null | undefined): MotionLevel {
  if (pref === "off") return "off";
  if (pref === "reduced") return "reduced";
  if (pref === "full") return "full";
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return reduced ? "reduced" : "full";
}

export function motionLevel(): MotionLevel {
  if (typeof document === "undefined") return "full";
  return resolveMotion(document.documentElement.dataset.motion);
}

/** Page content: fade with an 8–12px rise. In Reduced it's a plain fade; Off is instant. */
export function pageVariants(level: MotionLevel): Variants {
  const rise = level === "full" ? 10 : 0;
  return {
    initial: { opacity: 0, y: rise },
    enter: { opacity: 1, y: 0, transition: { duration: level === "off" ? 0 : dur.standard(), ease: easeEnter } },
    exit: { opacity: 0, transition: { duration: level === "off" ? 0 : dur.quick(), ease: easeLeave } },
  };
}

/** Drawer/sheet panels. */
export function panelVariants(level: MotionLevel, from: "right" | "bottom"): Variants {
  const off = level === "full" ? (from === "right" ? { x: 24 } : { y: 24 }) : {};
  return {
    initial: { opacity: 0, ...off },
    enter: { opacity: 1, x: 0, y: 0, transition: { duration: level === "off" ? 0 : dur.standard(), ease: easeEnter } },
    exit: { opacity: 0, transition: { duration: level === "off" ? 0 : dur.quick(), ease: easeLeave } },
  };
}

/** First-load stagger for a list of cards: 40ms apart, only on first load. */
export const staggerChildren = (level: MotionLevel): Transition =>
  level === "full" ? { staggerChildren: 0.04 } : { staggerChildren: 0 };

/** Seconds between staggered cards (Motion doc: 30–50 ms). */
export const STAGGER_STEP = 0.04;

// Screens whose first-load entrance has already played this session (module-level, so a revisit is instant).
const entered = new Set<string>();

/** True the first time a screen mounts in this session, false on every revisit. Stable for the life of
 * the component instance, so a re-render after data arrives gives the same answer as the first render. */
export function useFirstLoad(screenKey: string): boolean {
  const first = useRef<boolean | null>(null);
  if (first.current === null) {
    first.current = !entered.has(screenKey);
    entered.add(screenKey);
  }
  return first.current;
}

/** Test hook: forget every screen so the next mount counts as a first load. */
export function resetFirstLoads(): void {
  entered.clear();
}

/** Marks <html data-hidden> while the tab is in the background so looping CSS motion (.pulse, .skeleton,
 * odometer strips) pauses instead of burning frames nobody sees. Idempotent. */
let visibilityInstalled = false;
export function installVisibilityPause(): void {
  if (visibilityInstalled || typeof document === "undefined") return;
  visibilityInstalled = true;
  const apply = () => {
    if (document.visibilityState === "hidden") document.documentElement.dataset.hidden = "";
    else delete document.documentElement.dataset.hidden;
  };
  document.addEventListener("visibilitychange", apply);
  apply();
}
