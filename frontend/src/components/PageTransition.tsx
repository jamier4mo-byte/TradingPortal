import { AnimatePresence, motion } from "motion/react";
import { type ReactNode, useLayoutEffect, useState } from "react";
import { flushSync } from "react-dom";
import { useLocation, useNavigationType } from "react-router-dom";

import { motionLevel, pageVariants } from "../lib/motion.ts";

const supportsViewTransitions = typeof document !== "undefined" && "startViewTransition" in document;

/** Route change: the shell stays still while the content cross-fades with an 8–12px rise.
 * Uses the View Transitions API where the browser has it; otherwise `motion` does the same thing.
 * Going back (browser Back, or a POP navigation) reverses the direction: `<html data-nav="back">` is set
 * for the length of the transition and index.css swaps the keyframes. */
export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navType = useNavigationType();
  const level = motionLevel();

  if (supportsViewTransitions) {
    return (
      <ViewTransitionPage key="vt" pathname={location.pathname} back={navType === "POP"}>
        {children}
      </ViewTransitionPage>
    );
  }

  const variants = pageVariants(level);
  const back = navType === "POP" && level === "full";
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        variants={back ? { ...variants, initial: { opacity: 0, y: -10 } } : variants}
        initial="initial"
        animate="enter"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

type VTDocument = Document & { startViewTransition?: (cb: () => void) => { finished: Promise<void> } };

function ViewTransitionPage({ pathname, back, children }: { pathname: string; back: boolean; children: ReactNode }) {
  const [shown, setShown] = useState({ pathname, children });

  useLayoutEffect(() => {
    if (pathname === shown.pathname) {
      setShown({ pathname, children });
      return;
    }
    const level = motionLevel();
    const doc = document as VTDocument;
    // Off: swap at once, and never call startViewTransition (e2e spies on it).
    if (level === "off" || !doc.startViewTransition) {
      setShown({ pathname, children });
      return;
    }
    const root = document.documentElement;
    if (back) root.dataset.nav = "back";
    else delete root.dataset.nav;
    // flushSync: the new page must be in the DOM when the callback returns, so the browser captures it
    // (and shared elements with matching view-transition-name morph from list to detail).
    const transition = doc.startViewTransition(() => {
      flushSync(() => setShown({ pathname, children }));
    });
    void transition.finished.finally(() => {
      delete root.dataset.nav;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, children]);

  return <div style={{ viewTransitionName: "page" }}>{shown.children}</div>;
}
