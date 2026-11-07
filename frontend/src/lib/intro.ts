/** Portal intro bookkeeping (Loading screens → Portal intro). Login marks a sign-in; AppShell asks whether
 * to play. Plays once per UK day per device, only in Full motion, only right after a successful sign-in. */
import { remember, remembered } from "./hub.ts";
import { resolveMotion } from "./motion.ts";
import { ukISODate } from "./news.ts";

const FLAG = "tp.intro.pending"; // sessionStorage: a sign-in just happened (consumed by the first decision)
export const introKey = (ukDate: string) => `tp.intro.${ukDate}`;

// The decision for the current page load, so StrictMode's double initialiser (and a re-mount of the shell)
// gets the same answer. A reload clears it along with the module, and the flag is already consumed by then.
let decision: boolean | null = null;

/** Called on the sign-in success path (password or passkey). */
export function markIntroPending(): void {
  decision = null;
  try {
    sessionStorage.setItem(FLAG, "1");
  } catch {
    /* private mode */
  }
}

/** Whether the intro plays now. `pref` is the user's motion_pref, read directly because the <html
 * data-motion> attribute is written by a parent effect that runs after the shell's first render. */
export function takeIntro(pref: string | null | undefined): boolean {
  if (decision !== null) return decision;
  let pending = false;
  try {
    pending = sessionStorage.getItem(FLAG) === "1";
    if (pending) sessionStorage.removeItem(FLAG);
  } catch {
    return false;
  }
  if (!pending || resolveMotion(pref) !== "full") {
    decision = false;
    return false;
  }
  const key = introKey(ukISODate(new Date()));
  decision = !remembered(key);
  if (decision) remember(key);
  return decision;
}

/** The intro has finished (or was dismissed). */
export function introDone(): void {
  decision = false;
}
