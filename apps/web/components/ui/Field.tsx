import { cn } from "./cn";

export function Field({
  label,
  htmlFor,
  chip,
  hint,
  required,
  invalid,
  className,
  children,
}: {
  label: string;
  htmlFor?: string;
  chip?: React.ReactNode;
  hint?: React.ReactNode;
  required?: boolean;
  invalid?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <div className="mb-1.5 flex min-h-5 items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-xs font-medium text-ink-2">
          {label}
          {required && (
            <span className={cn("ml-1", invalid ? "text-stop-ink" : "text-ink-3")} aria-hidden>
              *
            </span>
          )}
        </label>
        {chip}
      </div>
      {children}
      {hint && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
    </div>
  );
}

export const controlClass = (invalid?: boolean) =>
  cn(
    "h-9 w-full rounded-control border bg-surface px-3 text-sm text-ink transition-colors duration-150",
    invalid ? "border-dashed border-ink-3 bg-sunken" : "border-line-strong",
  );
