import type { VerdictStatus } from "@/lib/api/types";
import { cn } from "@/components/ui/cn";
import { VERDICT_STYLE } from "./verdictStyle";

/** The verdict in miniature: shape, word and color together. Used in the log and the record drawer. */
export function VerdictBadge({ status, className }: { status: VerdictStatus; className?: string }) {
  const { Icon, solid } = VERDICT_STYLE[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-xs font-bold tracking-wide", solid, className)}>
      <Icon size={14} weight="fill" aria-hidden />
      {status}
    </span>
  );
}
