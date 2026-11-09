import type { ReactNode } from "react";

import { Logo } from "../../components/Brand.tsx";
import { OfflineBanner } from "../../components/ui/index.ts";
import { session, ukClock, ukDate } from "../../lib/time.ts";
import { useOnline } from "../../lib/useMediaQuery.ts";
import { useNow } from "../../lib/useNow.ts";

/** Auth screens share one frame: the logo over a brand hairline, the market clock as the only atmosphere,
 * and the form on the page itself rather than a card inside a card. */
export function AuthFrame({ title, intro, children, aside }: { title: string; intro?: string; children: ReactNode; aside?: ReactNode }) {
  const now = useNow(1000);
  const online = useOnline();
  const sess = session(now);
  const closed = sess === "Markets closed";
  return (
    <div className="safe-top safe-bottom min-h-dvh px-(--gutter-phone) py-8 tablet:px-(--gutter-tablet) laptop:grid laptop:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] laptop:gap-16 laptop:px-(--gutter-desktop) laptop:py-0">
      <section className="hidden laptop:flex laptop:min-h-dvh laptop:flex-col laptop:justify-between laptop:py-12">
        <Logo className="h-10 desktop:h-12" />
        <div>
          <p className="text-label text-muted">{ukDate(now)}</p>
          <p className="num mt-1 font-mono text-hero font-semibold leading-none">{ukClock(now)}</p>
          <p className="mt-4 inline-flex items-center gap-2 text-body text-muted">
            <span className={`size-2 rounded-full ${closed ? "bg-stale" : "bg-live pulse"}`} />
            {closed ? "Markets closed for the weekend" : `${sess} session open`}
          </p>
          <div className="brand-gradient brand-hairline mt-8 w-24" aria-hidden />
        </div>
        <p className="max-w-sm text-body text-muted">
          One place for the journal, the news and the week ahead. Built for Jamie and the mates.
        </p>
      </section>

      <section className="mx-auto flex w-full max-w-md flex-col laptop:justify-center laptop:py-12">
        <div className="mb-8 laptop:hidden">
          <Logo className="h-10" />
          <div className="brand-gradient brand-hairline mt-4 w-16" aria-hidden />
        </div>
        {online ? null : <OfflineBanner className="mb-6" />}
        <h1 className="text-heading font-semibold">{title}</h1>
        {intro ? <p className="mt-2 text-body text-muted">{intro}</p> : null}
        <div className="mt-6">{children}</div>
        {aside ? <div className="mt-8 border-t border-border pt-6 text-body text-muted">{aside}</div> : null}
      </section>
    </div>
  );
}
