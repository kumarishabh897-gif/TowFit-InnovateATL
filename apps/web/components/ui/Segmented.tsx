"use client";

import { ToggleGroup } from "radix-ui";
import { cn } from "./cn";

export type SegmentOption<T extends string | number> = { value: T; label: string; description?: string };

/** One choice out of a few, always visible. Never deselects: a state has to be chosen, not cleared. */
export function Segmented<T extends string | number>({
  value,
  onChange,
  options,
  label,
  invalid,
  columns,
  spans,
  size = "md",
}: {
  value: T | null;
  onChange: (value: T) => void;
  options: SegmentOption<T>[];
  label: string;
  invalid?: boolean;
  columns?: number;
  /** Column span per option, for uneven rows (for example 2,2,2,3,3 across 6 columns). */
  spans?: number[];
  size?: "md" | "lg";
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value === null ? "" : String(value)}
      onValueChange={(next) => {
        const match = options.find((o) => String(o.value) === next);
        if (match) onChange(match.value);
      }}
      aria-label={label}
      className={cn(
        "grid gap-1 rounded-control border p-1",
        invalid ? "border-dashed border-ink-3 bg-sunken" : "border-line bg-sunken",
      )}
      style={{ gridTemplateColumns: `repeat(${columns ?? options.length}, minmax(0, 1fr))` }}
    >
      {options.map((o, index) => (
        <ToggleGroup.Item
          key={String(o.value)}
          value={String(o.value)}
          style={spans ? { gridColumn: `span ${spans[index]}` } : undefined}
          className={cn(
            "press rounded-[6px] px-2 text-center font-medium text-ink-2",
            "data-[state=on]:bg-accent data-[state=on]:text-accent-fg",
            "data-[state=off]:hover:bg-surface",
            size === "lg" ? "min-h-11 py-1.5 text-sm" : "min-h-8 py-1 text-xs",
          )}
        >
          <span className="block leading-tight">{o.label}</span>
          {o.description && <span className="mt-0.5 block text-[11px] font-normal leading-tight opacity-80">{o.description}</span>}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
