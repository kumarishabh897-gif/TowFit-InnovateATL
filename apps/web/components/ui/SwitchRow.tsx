"use client";

import { Switch } from "radix-ui";
import { cn } from "./cn";

/** A yes/no fact about the scene. The state is written out ("Yes" / "No"), not only shown by the switch. */
export function SwitchRow({
  id,
  label,
  description,
  checked,
  onChange,
  danger,
}: {
  id: string;
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  danger?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm text-ink">
          {label}
        </label>
        {description && <p className="text-xs text-ink-3">{description}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span
          aria-hidden
          className={cn("tnum w-7 text-right text-xs font-medium", checked ? (danger ? "text-stop-ink" : "text-ink") : "text-ink-3")}
        >
          {checked ? "Yes" : "No"}
        </span>
        <Switch.Root
          id={id}
          checked={checked}
          onCheckedChange={onChange}
          className={cn(
            "press relative h-6 w-10 rounded-full border border-line-strong bg-sunken",
            checked && (danger ? "border-stop bg-stop" : "border-accent bg-accent"),
          )}
        >
          <Switch.Thumb
            className={cn(
              "block h-4 w-4 translate-x-[3px] rounded-full bg-ink-3 transition-transform duration-150 ease-out",
              "data-[state=checked]:translate-x-[19px]",
              checked && (danger ? "bg-stop-fg" : "bg-accent-fg"),
            )}
          />
        </Switch.Root>
      </div>
    </div>
  );
}
