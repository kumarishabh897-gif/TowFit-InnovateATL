import { ShieldCheck } from "@phosphor-icons/react";

/** Always visible, directly under the verdict, never collapsed into a tooltip. */
export function Disclaimer({ text }: { text: string }) {
  return (
    <p className="flex items-start gap-2.5 rounded-panel border border-line bg-surface px-4 py-3 text-sm leading-6 text-ink-2">
      <ShieldCheck size={18} weight="duotone" className="mt-[3px] shrink-0 text-ink-3" aria-hidden />
      <span>{text}</span>
    </p>
  );
}
