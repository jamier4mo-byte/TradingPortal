import { useSearchParams } from "react-router-dom";

import { PillToggle } from "./PillToggle.tsx";

export type ViewScope = "mine" | "everyone" | "others";

const OPTIONS = [
  { value: "mine" as const, label: "Mine" },
  { value: "everyone" as const, label: "Everyone" },
  { value: "others" as const, label: "Others" },
];

/** Mine · Everyone · Others (F12). Kept in the URL as ?scope= so links share the view. */
export function useViewScope(): [ViewScope, (s: ViewScope) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("scope");
  const scope: ViewScope = raw === "mine" || raw === "others" ? raw : "everyone";
  const set = (s: ViewScope) => {
    const next = new URLSearchParams(params);
    if (s === "everyone") next.delete("scope");
    else next.set("scope", s);
    setParams(next, { replace: true });
  };
  return [scope, set];
}

export function ViewScopeToggle({ size = "md" }: { size?: "sm" | "md" }) {
  const [scope, setScope] = useViewScope();
  return <PillToggle value={scope} onChange={setScope} options={OPTIONS} label="Whose work to show" size={size} />;
}
