import { animate, stagger } from "motion/react";
import { type ComponentPropsWithoutRef, type ElementType, useLayoutEffect, useRef } from "react";

import { dur, easeEnter, motionLevel, STAGGER_STEP, useFirstLoad } from "../../lib/motion.ts";

/** Staggered first-load entrance (Motion doc → Fades and page transitions): the direct children fade and
 * rise in sequence, 40 ms apart, the first time `screenKey` is shown this session. Revisits render at once.
 * Reduced: a plain fade. Off: nothing. The container is whatever element the layout needs (`as="ul"` for a
 * card grid) and keeps its own classes, so the children's grid columns are untouched. */
export function Stagger<T extends ElementType = "div">({
  as,
  screenKey,
  children,
  ...rest
}: { as?: T; screenKey: string } & Omit<ComponentPropsWithoutRef<T>, "as">) {
  const Tag = (as ?? "div") as ElementType;
  const ref = useRef<HTMLElement>(null);
  const first = useFirstLoad(screenKey);

  useLayoutEffect(() => {
    const el = ref.current;
    const level = motionLevel();
    if (!el || !first) return;
    const items = Array.from(el.children).filter((c): c is HTMLElement => c instanceof HTMLElement).slice(0, 24);
    if (level === "off" || !items.length) {
      el.dataset.stagger = "done";
      return;
    }
    // Hide before first paint; the animation's first keyframe takes over from here.
    for (const item of items) item.style.opacity = "0";
    el.dataset.stagger = "entering";
    const keyframes = level === "full" ? { opacity: [0, 1], transform: ["translateY(10px)", "translateY(0px)"] } : { opacity: [0, 1] };
    const controls = animate(items, keyframes, { duration: dur.standard(), ease: [...easeEnter], delay: stagger(STAGGER_STEP) });
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      for (const item of items) {
        item.style.removeProperty("opacity");
        item.style.removeProperty("transform");
      }
      el.dataset.stagger = "done";
    };
    void controls.then(finish, finish);
    return () => {
      controls.stop();
      finish();
    };
    // Runs once per mount: a later re-render must not restart the entrance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Tag ref={ref} data-stagger={first ? undefined : "skipped"} {...rest}>
      {children}
    </Tag>
  );
}
