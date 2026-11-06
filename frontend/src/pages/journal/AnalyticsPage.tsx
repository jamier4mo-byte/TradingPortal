import { ArrowLeft } from "lucide-react";
import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

import { SkeletonCard, ViewScopeToggle } from "../../components/ui/index.ts";

const AnalyticsView = lazy(() => import("./analytics/AnalyticsView.tsx"));

/** Analytics across every strategy: the place to split by owner (F12) with Mine · Everyone · Others. */
export default function AnalyticsPage() {
  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      <header className="flex flex-col gap-3">
        <Link to="/journal" className="inline-flex min-h-11 w-fit items-center gap-1 text-body text-muted hover:text-text print:hidden">
          <ArrowLeft aria-hidden className="size-4" /> Strategies
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-heading font-semibold">Analytics</h1>
            <p className="text-body text-muted">Every strategy together. Filter, split by owner, or export for AI.</p>
          </div>
          <ViewScopeToggle size="sm" />
        </div>
      </header>
      <Suspense fallback={<SkeletonCard />}>
        <AnalyticsView />
      </Suspense>
    </div>
  );
}
