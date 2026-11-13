import { useId } from "react";

import { IconAlert, IconCheck } from "@/components/icons";
import { BLOOD_GROUPS, COMPONENTS, COMPONENT_LABELS, CONDITIONS, type BloodGroup, type Component, type Condition } from "@/lib/types";

/* ---- Buttons ------------------------------------------------------------- */

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet" | "ghost";
  size?: "sm" | "md" | "lg";
  busy?: boolean;
};

const BUTTON_VARIANTS = {
  primary: "bg-accent text-white shadow-[var(--shadow-accent)] hover:bg-accent-dark",
  secondary: "border border-line bg-white text-ink shadow-[var(--shadow-raise)] hover:border-line-strong hover:bg-canvas",
  quiet: "bg-surface text-ink hover:bg-[#eceef2]",
  ghost: "text-accent underline decoration-accent/40 underline-offset-[3px] hover:text-accent-dark hover:decoration-accent-dark",
};
const BUTTON_SIZES = { sm: "min-h-9 px-3 text-[13px]", md: "min-h-11 px-4 text-sm", lg: "min-h-12 px-5 text-[15px]" };

export function Button({ variant = "primary", size = "md", busy = false, className = "", children, ...props }: ButtonProps) {
  const sizing = variant === "ghost" ? "min-h-6 px-0.5 text-sm" : BUTTON_SIZES[size];
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex select-none items-center justify-center gap-2 rounded-[var(--radius-control)] font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-55 disabled:active:translate-y-0 ${sizing} ${BUTTON_VARIANTS[variant]} ${className}`}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

function Spinner() {
  return <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />;
}

/* ---- Feedback ------------------------------------------------------------ */

export function LoadingSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2.5 py-8 text-sm text-muted">
      <span className="text-accent">
        <Spinner />
      </span>
      {label}
    </p>
  );
}

/** A grey placeholder shaped like the content that is loading. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />;
}

/** Placeholder rows for a list of results while they load. */
export function SkeletonList({ rows = 3, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-[var(--radius-panel)] border border-line bg-white p-4">
          <div className="flex justify-between gap-4">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/5" />
              <Skeleton className="h-3 w-2/5" />
            </div>
            <Skeleton className="h-6 w-14" />
          </div>
          <Skeleton className="mt-4 h-9 w-32" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-panel)] border border-dashed border-line-strong bg-white px-5 py-8 text-center">
      {icon && <div className="mx-auto mb-3 grid size-10 place-items-center rounded-full bg-surface text-muted">{icon}</div>}
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-sm text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorMessage({ children, onRetry }: { children: React.ReactNode; onRetry?: () => void }) {
  if (!children) return null;
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-[var(--radius-control)] border border-accent/25 bg-accent-soft px-3 py-2.5 text-sm text-accent-dark">
      <IconAlert size={18} className="mt-px" />
      <div className="min-w-0 flex-1">
        {children}{" "}
        {onRetry && (
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

/** Confirmation that an action worked. Announced politely to screen readers. */
export function Notice({ children }: { children: React.ReactNode }) {
  return (
    <p role="status" className="flex items-start gap-2 text-sm text-ink-soft">
      {children && (
        <>
          <IconCheck size={18} className="mt-px text-ok" />
          <span className="min-w-0">{children}</span>
        </>
      )}
    </p>
  );
}

/* ---- Forms --------------------------------------------------------------- */

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
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-ink-soft">
        {label}
      </label>
      {children({ id, className: "control", "aria-describedby": hint ? hintId : undefined })}
      {hint && (
        <p id={hintId} className="mt-1.5 text-xs leading-relaxed text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

const SIGN = { "+": "+", "-": "−" } as const;

/**
 * The eight blood groups as large tiles (a radio group), like the group printed
 * on a donor card. One tap on a phone; arrow keys move between groups.
 */
export function BloodGroupPicker({
  value,
  onChange,
  label = "Blood group",
  disabled = false,
  name,
}: {
  value: BloodGroup;
  onChange: (group: BloodGroup) => void;
  label?: string;
  disabled?: boolean;
  name?: string;
}) {
  const auto = useId();
  return (
    <fieldset disabled={disabled} className="min-w-0 disabled:opacity-50">
      <legend className="mb-1.5 text-[13px] font-medium text-ink-soft">{label}</legend>
      <div className="grid grid-cols-4 gap-1.5">
        {BLOOD_GROUPS.map((group) => {
          const letters = group.slice(0, -1);
          const sign = group.slice(-1) as "+" | "-";
          return (
            <label key={group} className="relative">
              <input
                type="radio"
                name={name ?? auto}
                value={group}
                aria-label={group}
                checked={value === group}
                onChange={() => onChange(group)}
                className="peer absolute inset-0 size-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
              />
              <span
                aria-hidden="true"
                className="flex h-12 items-baseline justify-center gap-px rounded-[var(--radius-control)] border border-line bg-white pt-2.5 font-semibold text-ink shadow-[var(--shadow-raise)] transition-[background-color,border-color,color,box-shadow] duration-150 peer-hover:border-line-strong peer-checked:border-accent peer-checked:bg-accent peer-checked:text-white peer-checked:shadow-[var(--shadow-accent)] peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent"
              >
                <span className="text-[19px] leading-none tracking-tight">{letters}</span>
                <span className="text-[15px] leading-none">{SIGN[sign]}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Whole blood / red cells / platelets / plasma as a segmented control (radio group). */
export function ComponentPicker({
  value,
  onChange,
  label = "Component",
  name,
}: {
  value: Component;
  onChange: (component: Component) => void;
  label?: string;
  name?: string;
}) {
  const auto = useId();
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-[13px] font-medium text-ink-soft">{label}</legend>
      <div className="grid grid-cols-2 gap-1 rounded-[var(--radius-control)] bg-surface p-1 sm:grid-cols-4">
        {COMPONENTS.map((component) => (
          <label key={component} className="relative">
            <input
              type="radio"
              name={name ?? auto}
              value={component}
              checked={value === component}
              onChange={() => onChange(component)}
              className="peer absolute inset-0 size-full cursor-pointer opacity-0"
            />
            <span className="flex min-h-10 items-center justify-center whitespace-nowrap rounded-[8px] px-1 text-center text-[13px] font-medium leading-tight text-muted transition-[background-color,color,box-shadow] duration-150 peer-hover:text-ink peer-checked:bg-white peer-checked:font-semibold peer-checked:text-ink peer-checked:shadow-[var(--shadow-raise)] peer-focus-visible:outline-2 peer-focus-visible:outline-offset-1 peer-focus-visible:outline-accent">
              {COMPONENT_LABELS[component]}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/* ---- Badges -------------------------------------------------------------- */

type Tone = "neutral" | "accent" | "solid" | "ok" | "quiet";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface text-ink-soft ring-1 ring-inset ring-line",
  accent: "bg-accent-soft text-accent-dark ring-1 ring-inset ring-accent/20",
  solid: "bg-accent text-white",
  ok: "bg-[#eaf6ef] text-ok ring-1 ring-inset ring-ok/20",
  quiet: "bg-transparent text-muted ring-1 ring-inset ring-line",
};

export function Badge({ tone = "neutral", children, dot = false }: { tone?: Tone; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {dot && <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function UrgencyBadge({ condition }: { condition: Condition }) {
  const { label, score } = CONDITIONS[condition] ?? CONDITIONS.other;
  const level = score >= 100 ? "Critical" : score >= 65 ? "High" : score >= 40 ? "Medium" : "Low";
  const tone: Tone = score >= 100 ? "solid" : score >= 65 ? "accent" : "neutral";
  return (
    <Badge tone={tone}>
      {level}: {label}
    </Badge>
  );
}

const STATUS: Record<string, { text: string; tone: Tone }> = {
  queued: { text: "In queue", tone: "accent" },
  pending: { text: "Pending", tone: "accent" },
  allocated: { text: "Allocated", tone: "neutral" },
  partial: { text: "Partly filled", tone: "accent" },
  unfulfilled: { text: "No bank stock", tone: "accent" },
  completed: { text: "Completed", tone: "ok" },
  accepted: { text: "Accepted", tone: "ok" },
  rejected: { text: "Declined", tone: "quiet" },
  verified: { text: "Verified", tone: "ok" },
  open: { text: "Open", tone: "accent" },
};

export function StatusBadge({ status }: { status: string }) {
  const { text, tone } = STATUS[status] ?? { text: status, tone: "neutral" as Tone };
  return (
    <Badge tone={tone} dot>
      {text}
    </Badge>
  );
}

/* ---- Layout -------------------------------------------------------------- */

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-raise)] sm:p-5 ${className}`}>{children}</div>;
}

export function PageTitle({ title, children, actions }: { title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">{title}</h1>
        {children && <p className="mt-1.5 max-w-prose text-[15px] leading-relaxed text-muted">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/** A heading for a section of a page, with an optional line of help and actions. */
export function SectionTitle({ id, title, children, actions }: { id?: string; title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <h2 id={id} className="text-[17px] font-semibold tracking-tight">
          {title}
        </h2>
        {children && <p className="mt-0.5 text-sm text-muted">{children}</p>}
      </div>
      {actions}
    </div>
  );
}

/** A single figure with its label, for summary rows. */
export function Stat({ label, value, tone = "neutral", hint }: { label: string; value: React.ReactNode; tone?: "neutral" | "accent"; hint?: string }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-panel)] border border-line bg-white px-4 py-3.5 shadow-[var(--shadow-raise)]">
      <p className="text-[13px] font-medium text-muted">{label}</p>
      <p className={`tabular mt-1 text-[28px] font-semibold leading-none tracking-tight ${tone === "accent" ? "text-accent" : "text-ink"}`}>{value}</p>
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

/* ---- Formatting ---------------------------------------------------------- */

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const shortDate = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const timeFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "2026-11-18" -> "18 Nov 2026" */
export function formatDate(iso: string | null): string {
  return iso ? dateFormat.format(new Date(`${iso.slice(0, 10)}T00:00:00`)) : "—";
}

/** "2026-11-18" -> "18 Nov" */
export function formatShortDate(iso: string): string {
  return shortDate.format(new Date(`${iso.slice(0, 10)}T00:00:00`));
}

/** A UTC timestamp from the API -> local date and time. */
export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso.endsWith("Z") ? iso : `${iso}Z`));
}
