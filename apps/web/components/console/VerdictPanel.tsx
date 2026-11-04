"use client";

import { ArrowCounterClockwise, WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";
import { useFleet } from "@/lib/api/hooks";
import { isEdited } from "@/lib/draft";
import { DISCLAIMER } from "@/lib/labels";
import { lb } from "@/lib/format";
import { useConsole } from "@/lib/store";
import type { LiveEvaluation } from "@/lib/useLiveEvaluation";
import { ActionBar } from "./ActionBar";
import { Disclaimer } from "./Disclaimer";
import { OutcomeMetrics } from "./OutcomeMetrics";
import { ReasonList } from "./ReasonList";
import { VerdictHero } from "./VerdictHero";

function ContextLine() {
  const draft = useConsole((s) => s.draft);
  const scenario = useConsole((s) => s.scenario);
  const reset = useConsole((s) => s.resetToScenario);
  const fleet = useFleet();
  if (!draft) return null;
  const edited = scenario ? isEdited(draft, scenario.base) : false;
  const unit = fleet.data?.find((u) => u.unit.unit_id === draft.unit_id);
  const capacity = unit?.rig_assumptions.rig_capacity_lb;

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-ink-2">
        {scenario ? (
          <>
            <span>
              Loaded: <strong className="font-semibold text-ink">{scenario.title}</strong>
            </span>
            {edited && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">Edited</span>}
          </>
        ) : (
          <strong className="font-semibold text-ink">Manual entry</strong>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-ink-2">
        {unit && capacity && (
          <span className="inline-flex items-center gap-1.5">
            {unit.unit.unit_id}, rig rated <span className="tnum font-medium text-ink">{lb(unit.unit.rig_capacity_lb)}</span>
            <ProvenanceChip provenance={capacity.provenance} />
          </span>
        )}
        {scenario && edited && (
          <Button variant="ghost" size="sm" onClick={reset}>
            <ArrowCounterClockwise size={14} weight="bold" aria-hidden />
            Reset to scenario
          </Button>
        )}
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4" aria-busy aria-label="Evaluating">
      <div className="h-44 animate-pulse rounded-panel bg-sunken motion-reduce:animate-none" />
      <div className="h-14 animate-pulse rounded-panel bg-sunken motion-reduce:animate-none" />
      <div className="h-48 animate-pulse rounded-panel bg-sunken motion-reduce:animate-none" />
    </div>
  );
}

export function VerdictPanel({ live }: { live: LiveEvaluation }) {
  const { phase, response, error, missing, retry } = live;
  const scenarioId = useConsole((s) => s.scenario?.id ?? "manual");

  return (
    <section aria-label="TowFit verdict" className="flex min-h-0 flex-col gap-4">
      <ContextLine />

      {phase === "incomplete" && (
        <div className="rounded-panel border border-dashed border-line-strong bg-surface px-5 py-5">
          <h2 className="text-lg font-semibold text-ink">Waiting for details</h2>
          <p className="mt-1 text-sm text-ink-2">
            TowFit will not guess these. Fill them in and the verdict appears.
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {missing.map((m) => (
              <li key={m.id} className="rounded-control bg-sunken px-2.5 py-1 text-sm font-medium text-ink">
                {m.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase === "error" && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-panel bg-stop-soft px-4 py-3.5 text-stop-ink">
          <span className="flex items-start gap-2 text-sm">
            <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
            <span>
              <strong>Could not evaluate.</strong> {error}
            </span>
          </span>
          <Button size="sm" variant="secondary" onClick={retry}>
            Try again
          </Button>
        </div>
      )}

      {phase === "computing" && !response && <Skeleton />}

      {response && (phase === "ready" || phase === "computing") && (
        <>
          <div className="space-y-3">
            <VerdictHero status={response.verdict.status} computing={phase === "computing"} />
            <Disclaimer text={response.verdict.disclaimer} />
          </div>
          {/* keyed by scenario: loading a new case starts the reasons back at the top */}
          <div key={scenarioId} className="min-h-0 flex-1 space-y-4 lg:overflow-y-auto lg:pr-1">
            <div className={phase === "computing" ? "opacity-60 transition-opacity duration-150" : "transition-opacity duration-150"}>
              <ReasonList reasons={response.verdict.reasons} />
            </div>
            <OutcomeMetrics response={response} />
            <ActionBar key={response.decision_id} response={response} />
          </div>
        </>
      )}

      {(phase === "incomplete" || phase === "error") && <Disclaimer text={response?.verdict.disclaimer ?? DISCLAIMER} />}
    </section>
  );
}
