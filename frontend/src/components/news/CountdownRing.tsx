import { countdownText } from "../../lib/news.ts";

/** The next high-impact event: a ring that depletes as time runs down. Accent until the last 15 minutes,
 * then orange, then red in the last 5, with a gentle opacity pulse (`.pulse`: opacity only; Off and the
 * device's reduce-motion setting stop it). The ring empties over the last `spanSeconds` (default 4 hours). */
export function CountdownRing({
  secondsLeft,
  spanSeconds = 4 * 3600,
  size = 112,
  label,
}: {
  secondsLeft: number;
  spanSeconds?: number;
  size?: number;
  label: string;
}) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const left = Math.max(0, secondsLeft);
  const pct = Math.min(1, left / spanSeconds);
  const final = left <= 15 * 60;
  const tone = left <= 5 * 60 ? "text-impact-high" : final ? "text-impact-medium" : "text-accent";
  const text = left <= 0 ? "Now" : countdownText(left);
  return (
    <div
      className="relative inline-grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
      role="timer"
      aria-live="off"
      aria-label={`${label}: ${left <= 0 ? "now" : `in ${text}`}`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-surface-2" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          className={`${tone} transition-[stroke-dashoffset] duration-(--dur-emphasis) ease-(--ease-in-enter) ${final && left > 0 ? "pulse" : ""}`}
        />
      </svg>
      <span className={`num absolute text-center font-semibold ${size < 96 ? "text-label" : "text-title"} ${final ? tone : ""}`} aria-hidden>
        {text}
      </span>
    </div>
  );
}
