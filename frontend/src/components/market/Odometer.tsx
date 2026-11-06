/** A number whose changed digits roll like an odometer (transform only). Screen readers get the plain text. */
export function Odometer({ text, className = "" }: { text: string; className?: string }) {
  return (
    <span className={`num inline-flex ${className}`}>
      <span className="sr-only">{text}</span>
      <span aria-hidden className="inline-flex">
        {[...text].map((ch, i) =>
          /\d/.test(ch) ? (
            <span key={`${text.length - i}`} className="odo-digit">
              <span className="odo-strip" style={{ transform: `translateY(${-Number(ch) * 1.2}em)` }}>
                {DIGITS.map((d) => (
                  <span key={d}>{d}</span>
                ))}
              </span>
            </span>
          ) : (
            <span key={`${text.length - i}-${ch}`}>{ch}</span>
          ),
        )}
      </span>
    </span>
  );
}

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];
