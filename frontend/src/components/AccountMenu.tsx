import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { LogOut, Settings, Shield } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth.tsx";
import { AvatarButton } from "./AvatarButton.tsx";

/** The account menu behind the avatar. Lazy-loaded by the shell: Radix's menu and floating-ui are ~9 KB
 * gzip that the Hub's first paint doesn't need (F18 budget); the plain avatar button shows until it lands. */
export default function AccountMenu() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <AvatarButton />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} className="card z-30 min-w-56 p-1.5 data-[state=open]:animate-[page-enter_var(--dur-quick)_var(--ease-in-enter)]">
          <div className="px-3 py-2">
            <p className="truncate text-body font-medium">{user?.display_name}</p>
            <p className="truncate text-label text-muted">{user?.email}</p>
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <MenuItem onSelect={() => navigate("/settings")} icon={Settings}>
            Settings
          </MenuItem>
          {isAdmin ? (
            <MenuItem onSelect={() => navigate("/admin/users")} icon={Shield}>
              Admin
            </MenuItem>
          ) : null}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <MenuItem
            onSelect={() => {
              void signOut().then(() => navigate("/login"));
            }}
            icon={LogOut}
          >
            Sign out
          </MenuItem>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function MenuItem({ children, onSelect, icon: Icon }: { children: ReactNode; onSelect: () => void; icon: typeof Settings }) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className="flex min-h-11 cursor-pointer items-center gap-3 rounded-panel px-3 text-body text-muted outline-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-text"
    >
      <Icon aria-hidden className="size-4" strokeWidth={1.75} />
      {children}
    </DropdownMenu.Item>
  );
}
