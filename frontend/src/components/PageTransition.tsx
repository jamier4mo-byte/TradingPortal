import { AnimatePresence, motion } from "motion/react";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useLocation } from "react-router-dom";

import { motionLevel, pageVariants } from "../lib/motion.ts";

const supportsViewTransitions = typeof document !== "undefined" && "startViewTransition" in document;

/** Route change: the shell stays still while the content cross-fades with an 8–12px rise.
 * Uses the View Transitions API where the browser has it; otherwise `motion` does the same thing. */
export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const level = motionLevel();

  if (supportsViewTransitions) {
    return <ViewTransitionPage key="vt" pathname={location.pathname}>{children}</ViewTransitionPage>;
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={location.pathname} variants={pageVariants(level)} initial="initial" animate="enter" exit="exit">
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

function ViewTransitionPage({ pathname, children }: { pathname: string; children: ReactNode }) {
  const [shown, setShown] = useState({ pathname, children });
  const pending = useRef<ReturnType<typeof setShown> | null>(null);

  useLayoutEffect(() => {
    if (pathname === shown.pathname) {
      setShown({ pathname, children });
      return;
    }
    const level = motionLevel();
    const doc = document as Document & { startViewTransition?: (cb: () => void) => { finished: Promise<void> } };
    if (level === "off" || !doc.startViewTransition) {
      setShown({ pathname, children });
      return;
    }
    // flushSync: the new page must be in the DOM when the callback returns, so the browser captures it
    // (and shared elements with matching view-transition-name morph from list to detail).
    doc.startViewTransition(() => {
      flushSync(() => setShown({ pathname, children }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, children]);

  useEffect(() => {
    pending.current = null;
  }, [shown]);

  return <div style={{ viewTransitionName: "page" }}>{shown.children}</div>;
}
