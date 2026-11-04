import type { Provenance } from "@/lib/api/types";
import { cn } from "./cn";

const TONE: Record<Provenance, string> = {
  LIVE: "bg-go-soft text-go-ink border-transparent",
  ESTIMATED: "bg-accent-soft text-accent border-transparent",
  ASSUMED: "bg-hold-soft text-hold-ink border-transparent",
  SIM: "bg-sunken text-ink-2 border-dashed border-line-strong",
  OPERATOR: "bg-sunken text-ink-2 border-line",
};

const MEANING: Record<Provenance, string> = {
  LIVE: "Real feed",
  ESTIMATED: "A public spec, with its source",
  ASSUMED: "Invented for the demo; no source yet",
  SIM: "Simulator or demo fixture, not real data",
  OPERATOR: "Entered by the operator, not sensor-derived",
};

/** The label every number carries: where it came from. */
export function ProvenanceChip({ provenance, className }: { provenance: Provenance; className?: string }) {
  return (
    <span
      title={MEANING[provenance]}
      className={cn(
        "inline-flex items-center rounded-full border px-1.5 py-[3px] text-[11px] font-semibold leading-none tracking-wide",
        TONE[provenance],
        className,
      )}
    >
      {provenance}
    </span>
  );
}
