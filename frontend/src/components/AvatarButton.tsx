import { type ComponentPropsWithoutRef, forwardRef } from "react";

import { useAuth } from "../lib/auth.tsx";
import { initials } from "../lib/format.ts";
import { ownerBg } from "./ui/Chips.tsx";

/** The avatar in the top bar. Rendered on its own while the account menu's chunk loads, then becomes the
 * menu's trigger (Radix passes its props through the ref and spread). */
export const AvatarButton = forwardRef<HTMLButtonElement, ComponentPropsWithoutRef<"button">>(function AvatarButton(props, ref) {
  const { user } = useAuth();
  return (
    <button ref={ref} type="button" className="btn btn-ghost size-11 px-0" aria-label="Account menu" aria-haspopup="menu" {...props}>
      <span className={`grid size-8 place-items-center rounded-full text-label font-semibold text-bg ${ownerBg(user?.colour_index ?? 0)}`}>
        {initials(user?.display_name ?? "?")}
      </span>
    </button>
  );
});
