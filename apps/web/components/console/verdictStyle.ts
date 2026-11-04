import { CheckCircle, Info, Warning, WarningOctagon } from "@phosphor-icons/react";
import type { ReasonEffect, VerdictStatus } from "@/lib/api/types";

// Each state has its own shape as well as its own color: circle, triangle, octagon.
export const VERDICT_STYLE = {
  GREEN: { Icon: CheckCircle, solid: "bg-go text-go-fg", soft: "bg-go-soft text-go-ink" },
  YELLOW: { Icon: Warning, solid: "bg-hold text-hold-fg", soft: "bg-hold-soft text-hold-ink" },
  RED: { Icon: WarningOctagon, solid: "bg-stop text-stop-fg", soft: "bg-stop-soft text-stop-ink" },
} as const satisfies Record<VerdictStatus, unknown>;

export const EFFECT_STYLE = {
  RED: { Icon: WarningOctagon, tag: "bg-stop text-stop-fg", row: "bg-stop-soft" },
  YELLOW: { Icon: Warning, tag: "bg-hold text-hold-fg", row: "bg-hold-soft" },
  GREEN: { Icon: CheckCircle, tag: "bg-go-soft text-go-ink", row: "" },
  ADVISORY: { Icon: Info, tag: "bg-sunken text-ink-2", row: "" },
} as const satisfies Record<ReasonEffect, unknown>;
