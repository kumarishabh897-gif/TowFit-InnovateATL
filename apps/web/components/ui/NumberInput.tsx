"use client";

import { useState } from "react";
import { cn } from "./cn";
import { controlClass } from "./Field";

function parse(raw: string): number | null | undefined {
  const cleaned = raw.replace(/,/g, "").trim();
  if (cleaned === "") return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : undefined; // undefined: not a number yet, keep typing
}

/** A number field that lets you type freely (no spinner, no wheel changes) and reports null when empty. */
export function NumberInput({
  id,
  value,
  onChange,
  unit,
  invalid,
  placeholder,
  min = 0,
  max,
  className,
  ...aria
}: {
  id?: string;
  value: number | null;
  onChange: (value: number | null) => void;
  unit?: string;
  invalid?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  className?: string;
} & Pick<React.AriaAttributes, "aria-label">) {
  const [text, setText] = useState(value === null ? "" : String(value));
  const [seenValue, setSeenValue] = useState(value);

  // Follow outside changes (a scenario load, a camera classification) without fighting the user's typing:
  // only when the value prop itself changes, and only if the text does not already say the same number.
  if (value !== seenValue) {
    setSeenValue(value);
    if (parse(text) !== value) setText(value === null ? "" : String(value));
  }

  return (
    <div className={cn("relative", className)}>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={text}
        placeholder={placeholder}
        onChange={(e) => {
          setText(e.target.value);
          const n = parse(e.target.value);
          if (n === undefined) return;
          if (n !== null && (n < min || (max !== undefined && n > max))) return;
          onChange(n);
        }}
        className={cn(controlClass(invalid), "tnum", unit && "pr-10")}
        {...aria}
      />
      {unit && (
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-ink-3">{unit}</span>
      )}
    </div>
  );
}
