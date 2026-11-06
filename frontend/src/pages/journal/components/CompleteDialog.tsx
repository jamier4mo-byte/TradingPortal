import { ConfirmDialog } from "../../../components/ui/index.ts";

/** Warns about what a trade is still missing before it is marked completed. Never blocks: Jamie decides. */
export function CompleteDialog({ missing, onConfirm, onCancel, busy = false }: { missing: string[] | null; onConfirm: () => void; onCancel: () => void; busy?: boolean }) {
  return (
    <ConfirmDialog
      open={!!missing}
      onOpenChange={(o) => !o && onCancel()}
      title="Mark completed anyway?"
      text={`This trade still has no ${missing?.join(" and ") ?? ""}. You can mark it completed now and add them later.`}
      confirmLabel="Mark completed anyway"
      busy={busy}
      onConfirm={onConfirm}
    />
  );
}
