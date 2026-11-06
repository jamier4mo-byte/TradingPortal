import { Search } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { type SearchResult, useSearch } from "../../lib/markets.ts";

/** Autocomplete by symbol or name (EUR/USD, XAUUSD, BTC/USD, GER40). Searches go to our backend, which
 * caches them for 24 hours. Keyboard: ↑/↓ to move, Enter to pick, Esc to close. */
export function InstrumentSearch({
  onPick,
  label = "Search instruments",
  pinned = [],
  className = "",
}: {
  onPick: (r: SearchResult) => void;
  label?: string;
  pinned?: string[];
  className?: string;
}) {
  const [text, setText] = useState("");
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const inputId = useId();
  useEffect(() => {
    const t = window.setTimeout(() => setTerm(text), 300);
    return () => window.clearTimeout(t);
  }, [text]);
  const search = useSearch(term);
  const results = search.data?.results ?? [];
  const showList = open && term.trim().length >= 2;

  const pick = (r: SearchResult) => {
    if (r.available === false) return;
    onPick(r);
    setText("");
    setTerm("");
    setOpen(false);
  };

  return (
    <div className={`relative ${className}`}>
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" />
      <input
        id={inputId}
        className="input pl-9"
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
        placeholder="Symbol or name, e.g. EUR/USD"
        autoComplete="off"
        spellCheck={false}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, Math.max(0, results.length - 1)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(0, a - 1));
          } else if (e.key === "Enter" && showList && results[active]) {
            e.preventDefault();
            pick(results[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      <p className="sr-only" role="status" aria-live="polite">
        {!showList ? "" : search.isPending || text !== term ? "Searching" : search.isError ? "Search didn't load" : `${results.length} ${results.length === 1 ? "match" : "matches"}`}
      </p>
      {showList ? (
        <ul id={listId} role="listbox" aria-label="Matching instruments" className="absolute inset-x-0 top-full z-30 mt-1 max-h-80 overflow-y-auto rounded-panel border border-border-strong bg-surface-1 py-1">
          {search.isPending || (text !== term) ? (
            <li className="px-3 py-2 text-body text-muted" role="presentation">
              Searching…
            </li>
          ) : search.isError ? (
            <li className="px-3 py-2 text-body text-muted" role="presentation">
              Search didn&rsquo;t load: {search.error.message}
            </li>
          ) : results.length === 0 ? (
            <li className="px-3 py-2 text-body text-muted" role="presentation">
              Nothing matches &ldquo;{term}&rdquo;.
            </li>
          ) : (
            results.map((r, i) => {
              const isPinned = pinned.includes(r.code ?? r.symbol) || pinned.includes(r.symbol);
              return (
                <li
                  key={`${r.symbol}-${r.exchange}`}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  aria-disabled={r.available === false}
                  className={`flex min-h-11 items-center gap-3 px-3 ${r.available === false ? "cursor-not-allowed" : "cursor-pointer"} ${
                    i === active ? "bg-accent-soft shadow-[inset_2px_0_0_var(--color-accent)]" : ""
                  }`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(r)}
                >
                  <span className="w-24 shrink-0 truncate font-mono text-body">{r.code ?? r.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-body text-muted">
                    {r.name}
                    {r.exchange ? ` · ${r.exchange}` : ""}
                  </span>
                  {r.available === false ? (
                    <span className="shrink-0 text-label text-muted">Not on your plan</span>
                  ) : isPinned ? (
                    <span className="shrink-0 text-label text-muted">Pinned</span>
                  ) : null}
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
