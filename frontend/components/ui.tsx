import { useId } from "react";

import { BLOOD_GROUPS, COMPONENTS, COMPONENT_LABELS, CONDITIONS, type Condition } from "@/lib/types";

const control =
  "h-11 w-full rounded-lg border border-line bg-white px-3 text-base text-ink disabled:bg-surface disabled:text-muted";

export function Button({
  variant = "primary",
  busy = false,
  className = "",
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; busy?: boolean }) {
  const styles = {
    primary: "bg-accent text-white hover:bg-accent-dark",
    secondary: "border border-line bg-white text-ink hover:bg-surface",
    ghost: "text-accent underline underline-offset-2 hover:text-accent-dark",
  }[variant];
  const size = variant === "ghost" ? "min-h-6 px-1" : "min-h-11 px-4";
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${size} ${styles} ${className}`}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none"
    />
  );
}

export function LoadingSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 py-6 text-sm text-muted">
      <span className="text-accent">
        <Spinner />
      </span>
      {label}
    </p>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-4 py-6 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorMessage({ children, onRetry }: { children: React.ReactNode; onRetry?: () => void }) {
  if (!children) return null;
  return (
    <div role="alert" className="rounded-lg border border-accent bg-accent-soft px-3 py-2 text-sm text-accent-dark">
      {children}{" "}
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (props: { id: string; className: string; "aria-describedby"?: string }) => React.ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {children({ id, className: control, "aria-describedby": hint ? hintId : undefined })}
      {hint && (
        <p id={hintId} className="mt-1 text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "children"> & { label?: string };

export function BloodGroupSelect({ label = "Blood group", ...props }: SelectProps) {
  return (
    <Field label={label}>
      {(field) => (
        <select {...field} name="blood_group" {...props}>
          {BLOOD_GROUPS.map((group) => (
            <option key={group}>{group}</option>
          ))}
        </select>
      )}
    </Field>
  );
}

export function ComponentSelect({ label = "Component", ...props }: SelectProps) {
  return (
    <Field label={label}>
      {(field) => (
        <select {...field} name="component" {...props}>
          {COMPONENTS.map((component) => (
            <option key={component} value={component}>
              {COMPONENT_LABELS[component]}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

export function UrgencyBadge({ condition }: { condition: Condition }) {
  const { label, score } = CONDITIONS[condition] ?? CONDITIONS.other;
  const level = score >= 100 ? "Critical" : score >= 65 ? "High" : score >= 40 ? "Medium" : "Low";
  const style = score >= 100 ? "bg-accent text-white" : score >= 65 ? "bg-accent-soft text-accent-dark" : "bg-surface text-ink";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${style}`}>
      {level}: {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const strong = ["queued", "pending", "partial", "unfulfilled", "open"].includes(status);
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${
        strong ? "bg-accent-soft text-accent-dark" : "bg-surface text-ink"
      }`}
    >
      {status}
    </span>
  );
}

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-xl border border-line bg-white p-4 ${className}`}>{children}</div>;
}

export function PageTitle({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="mb-5">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {children && <p className="mt-1 text-sm text-muted">{children}</p>}
    </header>
  );
}

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "2026-11-18" -> "18 Nov 2026" */
export function formatDate(iso: string | null): string {
  return iso ? dateFormat.format(new Date(`${iso.slice(0, 10)}T00:00:00`)) : "—";
}

/** A UTC timestamp from the API -> local date and time. */
export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso.endsWith("Z") ? iso : `${iso}Z`));
}
