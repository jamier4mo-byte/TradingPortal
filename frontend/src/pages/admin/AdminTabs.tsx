import { NavLink } from "react-router-dom";

export function AdminTabs() {
  const cls = ({ isActive }: { isActive: boolean }) =>
    `inline-flex min-h-11 items-center rounded-pill px-4 text-body ${isActive ? "bg-accent text-on-accent" : "text-muted hover:text-text"}`;
  return (
    <nav aria-label="Admin" className="inline-flex rounded-pill border border-border bg-surface-2 p-0.5">
      <NavLink to="/admin/users" className={cls}>
        Users
      </NavLink>
      <NavLink to="/admin/tags" className={cls}>
        Tags
      </NavLink>
    </nav>
  );
}
