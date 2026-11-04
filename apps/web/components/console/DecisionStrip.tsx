"use client";

import { CheckCircle, Warning } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Segmented } from "@/components/ui/Segmented";
import { useDecisions } from "@/lib/api/hooks";
import type { DecisionSummary } from "@/lib/api/types";
import { clock } from "@/lib/format";
import { ACTION_DONE, ACTION_LABEL } from "@/lib/labels";
import { useConsole } from "@/lib/store";
import { VerdictBadge } from "./VerdictBadge";

export function OperatorActionCell({ row }: { row: Pick<DecisionSummary, "operator_action" | "followed_recommendation"> }) {
  if (!row.operator_action) return <span className="text-ink-3">Not recorded</span>;
  const followed = row.followed_recommendation;
  return (
    <span className="inline-flex items-center gap-1.5 text-ink">
      {followed ? <CheckCircle size={14} weight="fill" className="text-go" aria-hidden /> : <Warning size={14} weight="fill" className="text-hold-ink" aria-hidden />}
      {ACTION_DONE[row.operator_action]}
      <span className="text-xs text-ink-3">{followed ? "Followed" : "Override"}</span>
    </span>
  );
}

/** The running log of evaluations: what TowFit said, what it recommended, and what the operator actually did. */
export function DecisionStrip({ onOpen }: { onOpen: (id: number) => void }) {
  const sessionStart = useConsole((s) => s.sessionStart);
  const [scope, setScope] = useState<"session" | "all">("session");
  const decisions = useDecisions(scope === "session" ? sessionStart : null);
  const items = decisions.data?.items ?? [];

  return (
    <section aria-labelledby="log-title" className="flex min-h-0 shrink-0 flex-col border-t border-line bg-surface lg:h-[13rem]">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 lg:px-6">
        <div className="flex items-baseline gap-3">
          <h2 id="log-title" className="text-sm font-semibold text-ink">
            Decision Records
          </h2>
          <span className="tnum text-xs text-ink-3">
            {decisions.data ? `${decisions.data.total} ${scope === "session" ? "this session" : "in total"}` : ""}
          </span>
        </div>
        <div className="w-56">
          <Segmented
            label="Which records to show"
            value={scope}
            options={[
              { value: "session", label: "This session" },
              { value: "all", label: "All" },
            ]}
            onChange={setScope}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-2 pb-2 lg:px-4">
        {decisions.isError ? (
          <p className="px-2 py-3 text-sm text-stop-ink">The log is unavailable: {decisions.error.message}</p>
        ) : items.length === 0 ? (
          <p className="px-2 py-4 text-sm text-ink-3">
            {decisions.isPending ? "Loading records" : "No evaluations yet. Every evaluation is logged here with its inputs, reasons and your recorded action."}
          </p>
        ) : (
          <table className="w-full min-w-[46rem] border-separate border-spacing-0 text-left text-sm">
            <thead>
              <tr className="text-xs text-ink-3">
                {["Time", "Unit", "Vehicle", "Verdict", "Recommended", "Operator action"].map((h) => (
                  <th key={h} scope="col" className="sticky top-0 bg-surface px-2 py-1.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* initial={false}: rows already there on first paint appear at once; rows that arrive later ease in. */}
              <AnimatePresence initial={false}>
              {items.map((row) => (
                <motion.tr
                  key={row.id}
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
                  onClick={() => onOpen(row.id)}
                  className="cursor-pointer hover:bg-sunken"
                >
                  <td className="tnum whitespace-nowrap border-t border-line px-2 py-1.5 text-ink-2">{clock(row.created_at)}</td>
                  <td className="whitespace-nowrap border-t border-line px-2 py-1.5 font-medium text-ink">{row.unit_id}</td>
                  <td className="max-w-[16rem] truncate border-t border-line px-2 py-1.5 text-ink">{row.vehicle_summary}</td>
                  <td className="border-t border-line px-2 py-1.5">
                    <VerdictBadge status={row.verdict} />
                  </td>
                  <td className="whitespace-nowrap border-t border-line px-2 py-1.5 text-ink-2">{ACTION_LABEL[row.recommended_action]}</td>
                  <td className="whitespace-nowrap border-t border-line px-2 py-1.5">
                    <span className="flex items-center justify-between gap-3">
                      <OperatorActionCell row={row} />
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpen(row.id);
                        }}
                        className="press rounded-control px-2 py-1 text-xs font-medium text-accent underline underline-offset-2"
                        aria-label={`Open record ${row.id}`}
                      >
                        Open
                      </button>
                    </span>
                  </td>
                </motion.tr>
              ))}
              </AnimatePresence>
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
