"use client";

import { ArrowRight } from "@phosphor-icons/react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { loadScenario, useScenarios } from "@/lib/api/hooks";
import { Button } from "@/components/ui/Button";
import { SCENARIO_SHORT, DISCLAIMER } from "@/lib/labels";
import { useConsole } from "@/lib/store";
import { Disclaimer } from "./Disclaimer";

/** Nothing loaded yet: say plainly what to do first. */
export function EmptyState() {
  const unitId = useConsole((s) => s.unitId);
  const startManual = useConsole((s) => s.startManual);
  const load = useConsole((s) => s.loadScenario);
  const scenarios = useScenarios();
  const mutation = useMutation({
    mutationFn: loadScenario,
    onSuccess: load,
    onError: (error) => toast.error("Could not load the scenario", { description: error.message }),
  });

  return (
    <section aria-labelledby="empty-title" className="mx-auto flex max-w-2xl flex-col gap-6 py-6 lg:py-10">
      <div>
        <h2 id="empty-title" className="text-2xl font-semibold tracking-tight text-ink">
          No vehicle loaded
        </h2>
        <p className="mt-2 max-w-[60ch] text-base leading-7 text-ink-2">
          {unitId
            ? `Unit ${unitId} is selected. Load a scenario to start from a case, or enter the disabled vehicle yourself.`
            : "Pick the patrol unit at the top, then load a scenario to start from a case, or enter the disabled vehicle yourself."}
        </p>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-ink">Start from a scenario</h3>
        <ul className="divide-y divide-line overflow-hidden rounded-panel border border-line bg-surface">
          {scenarios.data?.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(s.id)}
                className="press group flex w-full items-center gap-4 px-4 py-3.5 text-left hover:bg-sunken disabled:opacity-60"
              >
                <span className="tnum flex size-8 shrink-0 items-center justify-center rounded-control bg-sunken text-sm font-semibold text-ink">
                  {SCENARIO_SHORT[s.id] ?? "#"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-ink">{s.title}</span>
                  <span className="block text-sm text-ink-2">{s.description}</span>
                </span>
                <ArrowRight size={16} className="shrink-0 text-ink-3" aria-hidden />
              </button>
            </li>
          ))}
          {scenarios.isPending && <li className="px-4 py-3.5 text-sm text-ink-3">Loading scenarios</li>}
          {scenarios.isError && <li className="px-4 py-3.5 text-sm text-stop-ink">Scenarios unavailable: {scenarios.error.message}</li>}
        </ul>
        <p className="mt-2 text-xs text-ink-3">Scenarios fill the form with inputs only. The engine computes the verdict, so you can change any field afterwards.</p>
      </div>

      <div>
        <Button variant="secondary" size="lg" onClick={startManual}>
          Enter a vehicle manually
        </Button>
      </div>

      <Disclaimer text={DISCLAIMER} />
    </section>
  );
}
