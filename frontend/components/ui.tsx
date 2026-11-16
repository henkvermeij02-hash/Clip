"use client";

import { AlertTriangle, CheckCircle2, Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-zinc-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className, title, subtitle, actions }: {
  children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode;
}) {
  return (
    <section className={cx("rounded-2xl border border-ink-700 bg-ink-900/80 p-5", className)}>
      {(title || actions) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-white">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-zinc-400">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost";

export function Button({ variant = "secondary", loading, children, className, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: "brand-gradient text-white shadow-lg shadow-brand-500/20 hover:brightness-110",
    secondary: "border border-ink-600 bg-ink-800 text-zinc-100 hover:bg-ink-700",
    danger: "border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20",
    ghost: "text-zinc-300 hover:bg-ink-800 hover:text-white",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant], className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  succeeded: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  processing: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  running: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  pending: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  queued: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  error: "bg-red-500/15 text-red-300 ring-red-500/30",
  failed: "bg-red-500/15 text-red-300 ring-red-500/30",
  cancelled: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

const STATUS_LABELS: Record<string, string> = {
  ready: "Ready", succeeded: "Done", processing: "Processing", running: "Running",
  pending: "Waiting", queued: "Queued", error: "Error", failed: "Failed", cancelled: "Cancelled",
};

export function StatusBadge({ status }: { status: string }) {
  const spinning = status === "running" || status === "processing";
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", STATUS_STYLES[status] ?? STATUS_STYLES.cancelled)}>
      {spinning && <Loader2 className="h-3 w-3 animate-spin" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function Badge({ children, tone = "zinc" }: { children: ReactNode; tone?: "zinc" | "brand" | "amber" | "emerald" | "red" }) {
  const tones = {
    zinc: "bg-ink-800 text-zinc-300 ring-ink-600",
    brand: "bg-brand-500/15 text-brand-400 ring-brand-500/30",
    amber: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
    emerald: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
    red: "bg-red-500/15 text-red-300 ring-red-500/30",
  };
  return <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone])}>{children}</span>;
}

export function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cx("h-1.5 w-full overflow-hidden rounded-full bg-ink-700", className)}>
      <div className="brand-gradient h-full rounded-full transition-all duration-500" style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%` }} />
    </div>
  );
}

export function Alert({ tone = "error", children, onClose }: { tone?: "error" | "success" | "warning"; children: ReactNode; onClose?: () => void }) {
  const styles = {
    error: "border-red-500/30 bg-red-500/10 text-red-200",
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-100",
  };
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={cx("flex items-start gap-3 rounded-xl border px-4 py-3 text-sm", styles[tone])} role={tone === "error" ? "alert" : "status"}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
      {onClose && (
        <button onClick={onClose} className="opacity-60 hover:opacity-100" aria-label="Dismiss">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-600 px-6 py-14 text-center">
      <div className="mb-3 text-zinc-500">{icon}</div>
      <p className="font-medium text-zinc-200">{title}</p>
      {children && <div className="mt-1.5 max-w-md text-sm text-zinc-400">{children}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-zinc-400">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export const inputClass =
  "w-full rounded-xl border border-ink-600 bg-ink-850 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";

export function Field({ label, help, children, htmlFor }: { label: ReactNode; help?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-zinc-200">{label}</label>
      {children}
      {help && <p className="text-xs text-zinc-500">{help}</p>}
    </div>
  );
}
