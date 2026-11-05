/** Brand marks from /brand/*.png, never recoloured, stretched, glowed or shadowed. */
export function Logo({ className = "h-7" }: { className?: string }) {
  return <img src="/brand/tradingportal-logo.png" alt="Trading Portal" className={`${className} w-auto`} />;
}

export function Tile({ className = "size-9" }: { className?: string }) {
  return <img src="/brand/t-tile.png" alt="" aria-hidden className={className} />;
}
