/** Brand marks from /brand/*.png, never recoloured, stretched, glowed or shadowed. */
export function Logo({ className = "h-7" }: { className?: string }) {
  // Intrinsic size (2041×320) so the browser reserves the right box; `self-start` + `object-contain` keep the
  // wordmark at its own aspect ratio even inside a stretching flex column (the login page stretched it).
  return (
    <img
      src="/brand/tradingportal-logo.png"
      alt="Trading Portal"
      width={2041}
      height={320}
      decoding="async"
      className={`${className} w-auto max-w-full shrink-0 self-start object-contain object-left`}
    />
  );
}

export function Tile({ className = "size-9" }: { className?: string }) {
  return <img src="/brand/t-tile.png" alt="" aria-hidden className={className} />;
}
