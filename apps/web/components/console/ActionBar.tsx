"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Hand } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { recordEvent } from "@/lib/api/hooks";
import type { DecisionSummary, EvaluationResponse, OperatorAction } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";
import { ACTION_DONE, ACTION_LABEL } from "@/lib/labels";

const ACTIONS: OperatorAction[] = ["deploy", "wait_for_confirmation", "dispatch_wrecker"];

/**
 * A person decides; this records what they did. TowFit never deploys anything.
 * Choosing something other than the recommendation takes a second, explicit click, and is logged as an override.
 * Rendered with key={decision_id}: every evaluation is its own record, so it starts with no action recorded.
 */
export function ActionBar({ response }: { response: EvaluationResponse }) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<OperatorAction | null>(null);
  const [recorded, setRecorded] = useState<DecisionSummary | null>(null);
  const decisionId = response.decision_id;
  const alertRef = useRef<HTMLDivElement>(null);
  const recordedRef = useRef<HTMLParagraphElement>(null);

  // These appear below the buttons, possibly under the fold of the scrolling panel: bring them into view.
  useEffect(() => {
    if (pending) alertRef.current?.scrollIntoView({ block: "nearest" });
  }, [pending]);
  useEffect(() => {
    if (recorded) recordedRef.current?.scrollIntoView({ block: "nearest" });
  }, [recorded]);

  const mutation = useMutation({
    mutationFn: (action: OperatorAction) => recordEvent(decisionId, { action }),
    onSuccess: (summary) => {
      setRecorded(summary);
      setPending(null);
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
      queryClient.invalidateQueries({ queryKey: ["decision", decisionId] });
      toast.success(`Recorded: ${ACTION_DONE[summary.operator_action as OperatorAction]}`, {
        description: summary.followed_recommendation ? "Followed the recommendation." : "Recorded as an override of the recommendation.",
      });
    },
    onError: (error) => toast.error("Could not record the action", { description: error.message }),
  });

  const recommended = response.recommended_action;

  function choose(action: OperatorAction) {
    if (action === recommended) mutation.mutate(action);
    else setPending(action);
  }

  return (
    <section aria-labelledby="record-action" className="rounded-panel border border-line bg-surface px-4 py-4">
      <div className="flex items-start gap-2.5">
        <Hand size={18} weight="duotone" className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
        <div>
          <h3 id="record-action" className="text-sm font-semibold text-ink">
            Record your action
          </h3>
          <p className="text-sm text-ink-2">TowFit does not deploy anything. A person decides, and this records what they did.</p>
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {ACTIONS.map((action) => {
          const isRecommended = action === recommended;
          return (
            <Button
              key={action}
              variant={isRecommended ? "primary" : "secondary"}
              size="lg"
              disabled={mutation.isPending}
              onClick={() => choose(action)}
              className="h-auto min-h-12 flex-col gap-0 py-2"
            >
              <span>{ACTION_LABEL[action]}</span>
              {isRecommended && <span className="text-[11px] font-normal opacity-85">Recommended</span>}
            </Button>
          );
        })}
      </div>

      {pending && (
        <div ref={alertRef} role="alert" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-control bg-hold-soft px-3 py-2.5 text-sm text-hold-ink">
          <span>
            This differs from the recommendation. Record <strong>{ACTION_LABEL[pending]}</strong> anyway?
          </span>
          <span className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button size="sm" variant="primary" onClick={() => mutation.mutate(pending)}>
              Record override
            </Button>
          </span>
        </div>
      )}

      {recorded?.operator_action && (
        <p ref={recordedRef} className="mt-3 flex items-center gap-2 text-sm text-ink">
          <CheckCircle size={18} weight="fill" className="shrink-0 text-go" aria-hidden />
          <span>
            Recorded: <strong>{ACTION_DONE[recorded.operator_action]}</strong>.{" "}
            {recorded.followed_recommendation ? "Followed the recommendation." : "Override of the recommendation."}
          </span>
        </p>
      )}
    </section>
  );
}
