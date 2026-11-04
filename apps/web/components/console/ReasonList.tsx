import type { Reason } from "@/lib/api/types";
import { cn } from "@/components/ui/cn";
import { EFFECT_LABEL } from "@/lib/labels";
import { ProvenanceText } from "./ProvenanceText";
import { EFFECT_STYLE } from "./verdictStyle";

/** Why the verdict is what it is: every rule that fired, in the order the engine evaluated them. */
export function ReasonList({ reasons, compact }: { reasons: Reason[]; compact?: boolean }) {
  return (
    <ol className="divide-y divide-line overflow-hidden rounded-panel border border-line bg-surface">
      {reasons.map((reason, index) => {
        const { Icon, tag, row } = EFFECT_STYLE[reason.effect];
        return (
          <li key={`${reason.rule_id}-${index}`} className={cn("flex gap-3 px-3.5", compact ? "py-1.5" : "py-2", row)}>
            <span
              className={cn(
                "mt-0.5 inline-flex h-6 w-[9.5rem] shrink-0 items-center gap-1.5 self-start rounded-control px-2 text-xs font-semibold",
                tag,
              )}
            >
              <Icon size={14} weight="fill" aria-hidden />
              {EFFECT_LABEL[reason.effect]}
            </span>
            <p className="min-w-0 flex-1 text-sm leading-6 text-ink">
              <ProvenanceText text={reason.text} />
            </p>
          </li>
        );
      })}
    </ol>
  );
}
