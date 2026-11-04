"use client";

import { Sheet } from "@/components/ui/Sheet";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";
import { useDecisionDetail } from "@/lib/api/hooks";
import type { AssumptionUse, DecisionDetail, EvaluationInput } from "@/lib/api/types";
import { clock, lb } from "@/lib/format";
import { ACTION_DONE, ACTION_LABEL, CLASS_OPTIONS, NEUTRAL_OPTIONS } from "@/lib/labels";
import { Disclaimer } from "./Disclaimer";
import { OperatorActionCell } from "./DecisionStrip";
import { ReasonList } from "./ReasonList";
import { VerdictBadge } from "./VerdictBadge";

const yesNo = (b: boolean) => (b ? "Yes" : "No");

function inputRows(i: EvaluationInput): [string, React.ReactNode][] {
  const v = i.vehicle;
  const c = i.crash;
  const s = i.scene;
  const klass = CLASS_OPTIONS.find((o) => o.value === v.vehicle_class)?.label ?? v.vehicle_class;
  const neutral = NEUTRAL_OPTIONS.find((o) => o.value === c.neutral_status)?.label ?? c.neutral_status;
  return [
    ["Unit", i.unit_id],
    ["Vehicle", `${v.make_model} (${klass})`],
    ["Curb weight", <span key="w" className="inline-flex items-center gap-1.5">{lb(v.estimated_curb_weight_lb)} <ProvenanceChip provenance={v.curb_weight_provenance} /></span>],
    ...(v.estimated_load_weight_lb
      ? ([["Load weight", <span key="l" className="inline-flex items-center gap-1.5">{lb(v.estimated_load_weight_lb)} <ProvenanceChip provenance={v.load_weight_provenance} /></span>]] as [string, React.ReactNode][])
      : []),
    ["Neutral status", <span key="n" className="inline-flex items-center gap-1.5">{neutral} <ProvenanceChip provenance="OPERATOR" /></span>],
    ["Tires intact", `${c.tires_intact} of 4`],
    ["Wheels locked or damaged", String(c.wheels_locked_or_damaged)],
    ["Orientation", c.orientation.replace("_", " ")],
    ["Fire or fuel leak", yesNo(c.fire_or_fuel_leak)],
    ["Axle damage", yesNo(c.axle_damage)],
    ["Airbags deployed", yesNo(c.airbags_deployed)],
    ["Lanes blocked", `${s.lanes_blocked} of ${s.lanes_total}`],
    ["Shoulder available", yesNo(s.shoulder_available)],
    ["Shoulder wide enough", yesNo(s.shoulder_width_ok)],
    ["Grade or curve", yesNo(s.grade_or_curve)],
    ["Live traffic risk", <span key="t" className="inline-flex items-center gap-1.5">{s.live_traffic_risk} <ProvenanceChip provenance={s.live_traffic_risk_provenance} /></span>],
    ["Severity", <span key="s" className="inline-flex items-center gap-1.5">{i.severity.level} <ProvenanceChip provenance={i.severity.provenance} /></span>],
  ];
}

function formatValue(u: AssumptionUse): string {
  const v = u.value;
  if (v === null || v === undefined) return "none";
  if (typeof v === "number") return `${v.toLocaleString("en-US")}${u.unit ? ` ${u.unit}` : ""}`;
  if (Array.isArray(v)) return `${v[0]} to ${v[1]}${u.unit ? ` ${u.unit}` : ""}`;
  return Object.entries(v).map(([k, n]) => `${k.replace(/_/g, " ")} ${n.toLocaleString("en-US")}`).join(", ");
}

function Body({ d }: { d: DecisionDetail }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <VerdictBadge status={d.verdict} className="px-3 py-1.5 text-sm" />
        <span className="text-sm text-ink-2">
          Recommended: <strong className="font-semibold text-ink">{ACTION_LABEL[d.recommended_action]}</strong>
        </span>
        <span className="text-sm text-ink-2">
          Operator: <OperatorActionCell row={d} />
        </span>
      </div>

      <Disclaimer text={d.result.disclaimer} />

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">Reasons</h3>
        <ReasonList reasons={d.result.reasons} compact />
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">Inputs as submitted</h3>
        <dl className="divide-y divide-line rounded-panel border border-line">
          {inputRows(d.inputs).map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 px-3.5 py-2 text-sm">
              <dt className="text-ink-2">{label}</dt>
              <dd className="tnum text-right capitalize text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h3 className="mb-1 text-sm font-semibold text-ink">Assumptions this verdict used</h3>
        <p className="mb-2 text-xs text-ink-3">Values as they were when it was evaluated. Later edits do not change this record.</p>
        <ul className="divide-y divide-line rounded-panel border border-line">
          {d.assumptions_used.map((u) => (
            <li key={u.key} className="px-3.5 py-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <code className="font-mono text-xs text-ink-2">{u.key}</code>
                <span className="inline-flex items-center gap-1.5">
                  <ProvenanceChip provenance={u.provenance} />
                  <span className="text-xs text-ink-3">{u.status.toLowerCase()}</span>
                </span>
              </div>
              <div className="tnum mt-0.5 text-ink">{formatValue(u)}</div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">What happened next</h3>
        {d.events.length === 0 ? (
          <p className="text-sm text-ink-3">No action recorded for this evaluation.</p>
        ) : (
          <ol className="space-y-2">
            {d.events.map((e) => (
              <li key={e.id} className="flex gap-3 text-sm">
                <span className="tnum w-20 shrink-0 text-ink-3">{clock(e.created_at)}</span>
                <span className="text-ink">
                  {e.kind === "operator_action" && e.action ? ACTION_DONE[e.action] : "Outcome"}
                  {e.note ? `: ${e.note}` : ""}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export function DecisionSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const detail = useDecisionDetail(id);
  const d = detail.data;
  return (
    <Sheet
      open={id !== null}
      onOpenChange={(open) => !open && onClose()}
      title={id !== null ? `Decision Record ${id}` : "Decision Record"}
      description={d ? `${clock(d.created_at)}, ${d.unit_id}, ${d.vehicle_summary}` : undefined}
    >
      {detail.isPending && id !== null && <p className="text-sm text-ink-3">Loading record</p>}
      {detail.isError && <p className="text-sm text-stop-ink">Could not load this record: {detail.error.message}</p>}
      {d && <Body d={d} />}
    </Sheet>
  );
}
