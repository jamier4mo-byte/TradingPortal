import type { InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";

/** Label above, control, then help or error text. One job per line. */
export function Field({
  label,
  help,
  error,
  children,
  id,
}: {
  label: string;
  help?: string;
  error?: string | null;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean }) => ReactNode;
  id?: string;
}) {
  const auto = useId();
  const fieldId = id ?? auto;
  const helpId = `${fieldId}-help`;
  const errId = `${fieldId}-err`;
  const describedBy = [help ? helpId : null, error ? errId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-body font-medium">
        {label}
      </label>
      {children({ id: fieldId, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {help && !error ? (
        <p id={helpId} className="text-label text-muted">
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={errId} role="alert" className="text-label text-loss">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`input ${props.className ?? ""}`} />;
}
