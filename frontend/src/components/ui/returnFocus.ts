import { useRef } from "react";

/**
 * Put focus back where it came from when a dialog closes (WCAG 2.4.3). Radix's modal `Dialog.Content`
 * returns focus to its `Dialog.Trigger` and, when there is none, to nothing: every dialog here is controlled
 * (opened from a button, a row, a card or a shortcut), so remember what has focus as `open` flips to true
 * and focus it again on close. The element is read while rendering the opening state, because a field with
 * `autoFocus` inside the dialog takes focus during the commit, before Radix's own open event fires. If the
 * opener has since left the page, Radix's default stands.
 */
export function useReturnFocus(open = true) {
  const opener = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);
  if (open && !wasOpen.current && typeof document !== "undefined") {
    const active = document.activeElement;
    opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
  }
  wasOpen.current = open;
  return {
    onCloseAutoFocus: (event: Event) => {
      const el = opener.current;
      opener.current = null;
      if (el && el.isConnected) {
        event.preventDefault();
        el.focus();
      }
    },
  };
}
