/** A valid, unique view-transition-name for a shared element (list item → detail). */
export function vtName(kind: string, id: string | number): string {
  return `${kind}-${String(id).replace(/[^A-Za-z0-9_-]/g, "_")}`;
}
