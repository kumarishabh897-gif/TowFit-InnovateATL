import type { Provenance } from "@/lib/api/types";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";

const PATTERN = /\b(ESTIMATED|ASSUMED|SIM|OPERATOR|LIVE)\b|\(operator-entered\)/g;

/** Reason text names where a number came from; show those words as the same chips used everywhere else. */
export function ProvenanceText({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(PATTERN)) {
    const start = match.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    const provenance = (match[1] ?? "OPERATOR") as Provenance;
    parts.push(<ProvenanceChip key={start} provenance={provenance} className="mx-0.5 align-[1px]" />);
    last = start + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
