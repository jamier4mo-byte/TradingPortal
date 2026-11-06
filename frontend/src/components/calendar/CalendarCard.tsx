/** Team calendar card contents for the Hub (1.4 on the Hub, 1.6 layout order).
 *
 * Contract (shared between the Hub and the calendar build): a self-contained component that fetches
 * its own data and renders the card *contents* only; the Hub supplies the `Card` wrapper, title and
 * the "Open calendar" control. `variant="week"` is the desktop week strip; `variant="agenda"` is the
 * phone's day / 3-day agenda list. It carries its own loading, empty, error and offline states.
 *
 * This file is a placeholder until the calendar build replaces it. */
import { EmptyState } from "../ui/index.ts";

export default function CalendarCard({ variant }: { variant: "week" | "agenda" }) {
  return <EmptyState title="No tasks yet" text={variant === "week" ? "The week ahead shows here." : "Today's tasks show here."} />;
}
