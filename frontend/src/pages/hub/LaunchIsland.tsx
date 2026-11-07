import { ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";
import { type MouseEvent, useState } from "react";
import { Link } from "react-router-dom";

import type { Tool } from "../../components/launch/useLaunch.ts";
import { TOOLS } from "../../components/launch/useLaunch.ts";
import { motionLevel, spring } from "../../lib/motion.ts";

/** Launch island (1.3): logo, subtitle and a live mini-stat. A real link (new-tab clicks work), but a plain
 * click plays the launch loader instead (F14). Hover lifts and glows (`.launch-island`); the arrow springs. */
export function LaunchIsland({
  tool,
  logo,
  subtitle,
  stat,
  onLaunch,
  className = "",
}: {
  tool: Tool;
  logo: string;
  subtitle: string;
  /** undefined while loading, null when it can't load */
  stat: string | null | undefined;
  onLaunch: (tool: Tool) => void;
  className?: string;
}) {
  const [lit, setLit] = useState(false);
  const meta = TOOLS[tool];
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    onLaunch(tool);
  };
  const full = motionLevel() === "full";
  return (
    <Link
      to={meta.to}
      // The whole card is the link: its name says what it opens and carries the subtitle and the live stat,
      // so a screen reader hears the same as a sighted user ("Open Replay Journal. Ideal trades… Last session…").
      aria-label={[`Open ${meta.name}`, subtitle, typeof stat === "string" ? stat : null].filter(Boolean).join(". ")}
      onClick={onClick}
      onMouseEnter={() => setLit(true)}
      onMouseLeave={() => setLit(false)}
      onFocus={() => setLit(true)}
      onBlur={() => setLit(false)}
      className={`launch-island card group flex min-h-36 flex-col justify-between p-4 tablet:p-6 ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <img src={logo} alt={meta.name} className="h-auto max-h-10 w-auto min-w-0 max-w-full object-contain object-left" />
        <motion.span
          aria-hidden
          className="hidden shrink-0 text-subtle group-hover:text-accent tablet:block"
          animate={{ x: lit ? 3 : 0, y: lit ? -3 : 0 }}
          transition={full ? spring : { duration: 0 }}
        >
          <ArrowUpRight className="size-5" />
        </motion.span>
      </div>
      <div className="mt-4">
        <p className="text-label text-muted tablet:text-body">{subtitle}</p>
        {stat === undefined ? (
          <span className="skeleton mt-1.5 block h-3.5 w-40 max-w-full" role="status" aria-label="Loading" />
        ) : stat === null ? null : (
          <p className="num mt-1 line-clamp-2 text-label text-text">{stat}</p>
        )}
      </div>
    </Link>
  );
}
