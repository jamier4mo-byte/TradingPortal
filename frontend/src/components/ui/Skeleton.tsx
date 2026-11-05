/** Placeholder in the shape of the content, with a faint shimmer. No spinners in the main area. */
export function Skeleton({ className = "", label = "Loading" }: { className?: string; label?: string }) {
  return <div className={`skeleton ${className}`} role="status" aria-label={label} />;
}

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-3.5" style={{ width: `${100 - (i % 3) * 18}%` }} />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card p-4 tablet:p-5 ${className}`} role="status" aria-label="Loading">
      <div className="mb-4 flex items-center gap-3">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton ml-auto h-8 w-24 rounded-pill" />
      </div>
      <div className="skeleton h-28 w-full" />
    </div>
  );
}
