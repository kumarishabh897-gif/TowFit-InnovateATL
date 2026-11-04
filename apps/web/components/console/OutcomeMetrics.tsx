import { Clock, Truck, UserCheck } from "@phosphor-icons/react";
import type { AssumptionUse, EvaluationResponse } from "@/lib/api/types";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";
import { WRECKER_LABEL } from "@/lib/labels";
import { minutes } from "@/lib/format";

/** ASSUMED while any number behind it is still a placeholder. */
function provenanceOf(prefix: string, used: AssumptionUse[]) {
  const relevant = used.filter((u) => u.key.startsWith(prefix));
  return relevant.some((u) => u.status === "PLACEHOLDER") ? ("ASSUMED" as const) : ("ESTIMATED" as const);
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** "on-scene supervisor: attempt neutral; on-scene supervisor: confirm shoulder" becomes one person with two tasks. */
function groupByPerson(items: string[]): [string, string[]][] {
  const groups = new Map<string, string[]>();
  for (const item of items) {
    const at = item.indexOf(": ");
    const who = at > 0 ? item.slice(0, at) : "Supervisor";
    const task = at > 0 ? item.slice(at + 2) : item;
    groups.set(who, [...(groups.get(who) ?? []), task]);
  }
  return [...groups];
}

function Metric({ icon, label, value, note, chip }: { icon: React.ReactNode; label: string; value: string; note?: string; chip: React.ReactNode }) {
  return (
    <div className="rounded-panel border border-line bg-surface px-4 py-3.5">
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          {icon}
          {label}
        </span>
        {chip}
      </div>
      <div className="tnum mt-1.5 text-3xl font-bold tracking-tight text-ink">{value}</div>
      {note && <div className="tnum mt-0.5 text-sm text-ink-2">{note}</div>}
    </div>
  );
}

/** Clearance time for GREEN and YELLOW, or the wrecker to send and when it arrives for RED. */
export function OutcomeMetrics({ response }: { response: EvaluationResponse }) {
  const { verdict, assumptions_used: used } = response;

  if (verdict.status === "RED" && verdict.wrecker) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Metric
          icon={<Truck size={16} aria-hidden />}
          label="Recommended wrecker"
          value={WRECKER_LABEL[verdict.wrecker.wrecker_class] ?? verdict.wrecker.wrecker_class}
          chip={<ProvenanceChip provenance="ASSUMED" />}
        />
        <Metric
          icon={<Clock size={16} aria-hidden />}
          label="Estimated arrival"
          value={minutes(verdict.wrecker.eta_minutes)}
          note="Dispatch delay plus travel time"
          chip={<ProvenanceChip provenance={provenanceOf("wrecker.", used)} />}
        />
      </div>
    );
  }

  const clearance = verdict.estimated_clearance_minutes;
  const confirmations = verdict.confirmation_required_from?.split("; ").filter(Boolean) ?? [];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {clearance && (
        <Metric
          icon={<Clock size={16} aria-hidden />}
          label="Estimated clearance time"
          value={minutes(clearance.point)}
          note={`Range ${clearance.low} to ${clearance.high} min${verdict.status === "YELLOW" ? ", includes time to confirm" : ""}`}
          chip={<ProvenanceChip provenance={provenanceOf("clearance.", used)} />}
        />
      )}
      {verdict.status === "YELLOW" && confirmations.length > 0 && (
        <div className="rounded-panel border border-line bg-surface px-4 py-3.5">
          <div className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-2">
            <UserCheck size={16} aria-hidden />
            Confirmation needed
          </div>
          <div className="mt-1.5 space-y-2 text-sm">
            {groupByPerson(confirmations).map(([who, tasks]) => (
              <div key={who}>
                <div className="font-semibold text-ink">{capitalize(who)}</div>
                <ul className="list-disc pl-5 text-ink-2">
                  {tasks.map((task) => (
                    <li key={task}>{capitalize(task)}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
