import { useQuery } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";

import { Chip } from "../../../components/ui/index.ts";
import { api, type Tag } from "../../../lib/api.ts";

const BLUR_GRACE_MS = 120; // lets a mousedown on a suggestion land before the list closes

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** Chips plus a synonym-aware autocomplete over the shared vocabulary (U5). */
export function TagInput({ value, onChange, label = "Tags", id }: { value: string[]; onChange: (v: string[]) => void; label?: string; id?: string }) {
  const auto = useId();
  const inputId = id ?? auto;
  const listId = `${inputId}-list`;
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const tags = useQuery({ queryKey: ["tags"], queryFn: () => api.get<Tag[]>("/api/tags"), staleTime: 300_000 });

  const suggestions = useMemo(() => {
    const needle = norm(q);
    const chosen = new Set(value.map(norm));
    return (tags.data ?? [])
      .filter((t) => !chosen.has(norm(t.name)))
      .map((t) => {
        const viaSyn = t.synonyms.find((s) => norm(s).includes(needle));
        const hit = !needle || norm(t.name).includes(needle) || !!viaSyn;
        return hit ? { tag: t, via: needle && !norm(t.name).includes(needle) ? viaSyn : undefined } : null;
      })
      .filter((x): x is { tag: Tag; via: string | undefined } => !!x)
      .slice(0, 8);
  }, [tags.data, q, value]);

  const add = (name: string) => {
    const n = name.trim();
    if (!n || value.some((v) => norm(v) === norm(n))) return;
    onChange([...value, n]);
    setQ("");
    setIndex(0);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-body font-medium">
        {label}
      </label>
      <div className="relative">
        <div className="input flex min-h-11 flex-wrap items-center gap-1.5 py-0 focus-within:border-transparent focus-within:outline-2 focus-within:outline-accent" onClick={() => document.getElementById(inputId)?.focus()}>
          {value.map((v) => (
            <Chip key={v} onRemove={() => onChange(value.filter((x) => x !== v))}>
              {v}
            </Chip>
          ))}
          <input
            id={inputId}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), BLUR_GRACE_MS)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, suggestions.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter" && (q.trim() || suggestions.length)) {
                e.preventDefault();
                const pick = suggestions[index];
                add(pick && (q.trim() === "" || norm(pick.tag.name).startsWith(norm(q)) || pick.via) ? pick.tag.name : q);
              } else if (e.key === "Backspace" && !q && value.length) {
                onChange(value.slice(0, -1));
              }
            }}
            role="combobox"
            aria-expanded={open && suggestions.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && suggestions[index] ? `${listId}-${suggestions[index].tag.id}` : undefined}
            placeholder={value.length ? "" : "FVG, order block, SMT…"}
            className="min-h-11 min-w-24 flex-1 bg-transparent outline-none placeholder:text-muted"
          />
        </div>
        {open && suggestions.length ? (
          <ul id={listId} role="listbox" className="card absolute inset-x-0 top-full z-20 mt-1 max-h-60 overflow-auto p-1">
            {suggestions.map((s, i) => (
              <li
                key={s.tag.id}
                id={`${listId}-${s.tag.id}`}
                role="option"
                aria-selected={i === index}
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(s.tag.name);
                }}
                className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-panel px-3 text-body ${i === index ? "bg-surface-2" : ""}`}
              >
                <span>{s.tag.name}</span>
                {s.via ? <span className="text-label text-muted">= {s.via}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
