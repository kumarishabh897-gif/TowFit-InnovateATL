"use client";

import { CaretDown, Check } from "@phosphor-icons/react";
import { Select } from "radix-ui";
import { cn } from "./cn";
import { controlClass } from "./Field";

export type SelectOption = { value: string; label: string; description?: string };

export function SelectField({
  id,
  value,
  onChange,
  options,
  placeholder,
  invalid,
  ariaLabel,
}: {
  id?: string;
  value: string | null;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder: string;
  invalid?: boolean;
  ariaLabel?: string;
}) {
  return (
    <Select.Root value={value ?? ""} onValueChange={onChange}>
      <Select.Trigger
        id={id}
        aria-label={ariaLabel}
        className={cn(controlClass(invalid), "press flex items-center justify-between gap-2 text-left data-[placeholder]:text-ink-3")}
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon>
          <CaretDown size={14} weight="bold" className="text-ink-3" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          data-pop
          position="popper"
          sideOffset={4}
          className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-control border border-line-strong bg-surface p-1"
        >
          <Select.Viewport>
            {options.map((o) => (
              <Select.Item
                key={o.value}
                value={o.value}
                className="relative flex cursor-default select-none items-center rounded-[6px] py-1.5 pl-8 pr-3 text-sm text-ink outline-none data-[highlighted]:bg-accent-soft data-[highlighted]:text-ink"
              >
                <Select.ItemIndicator className="absolute left-2.5">
                  <Check size={14} weight="bold" className="text-accent" />
                </Select.ItemIndicator>
                <div>
                  <Select.ItemText>{o.label}</Select.ItemText>
                  {o.description && <p className="text-xs text-ink-3">{o.description}</p>}
                </div>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
