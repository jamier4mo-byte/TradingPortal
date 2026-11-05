import type { ReactNode } from "react";

/** The one card pattern: title (+ optional subtitle) top-left, controls top-right, content below. */
export default function Card({
  title,
  subtitle,
  controls,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  controls?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card p-4 tablet:p-5 ${className}`} aria-label={title}>
      <header className="mb-4 flex flex-wrap items-start gap-3">
        <div className="min-w-0">
          <h2 className="text-title font-semibold">{title}</h2>
          {subtitle ? <p className="text-label text-muted">{subtitle}</p> : null}
        </div>
        {controls ? <div className="ml-auto flex shrink-0 items-center gap-2">{controls}</div> : null}
      </header>
      {children}
    </section>
  );
}
