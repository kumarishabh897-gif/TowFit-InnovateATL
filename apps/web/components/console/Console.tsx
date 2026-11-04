"use client";

import { useState } from "react";
import { useConsole } from "@/lib/store";
import { useLiveEvaluation } from "@/lib/useLiveEvaluation";
import { DecisionSheet } from "./DecisionSheet";
import { DecisionStrip } from "./DecisionStrip";
import { EmptyState } from "./EmptyState";
import { InputsPanel } from "./InputsPanel";
import { TopBar } from "./TopBar";
import { VerdictPanel } from "./VerdictPanel";

export function Console() {
  const live = useLiveEvaluation();
  const hasDraft = useConsole((s) => s.draft !== null);
  const [openRecord, setOpenRecord] = useState<number | null>(null);

  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh lg:overflow-hidden">
      <TopBar />
      <main className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-rows-[minmax(0,1fr)] lg:px-6 lg:[grid-template-columns:minmax(22rem,27rem)_minmax(0,1fr)]">
        {hasDraft ? (
          <>
            <div className="flex min-h-0 flex-col lg:order-1">
              <InputsPanel />
            </div>
            <div className="flex min-h-0 flex-col lg:order-2">
              <VerdictPanel live={live} />
            </div>
          </>
        ) : (
          <div className="min-h-0 lg:col-span-2 lg:overflow-y-auto">
            <EmptyState />
          </div>
        )}
      </main>
      <DecisionStrip onOpen={setOpenRecord} />
      <DecisionSheet id={openRecord} onClose={() => setOpenRecord(null)} />
    </div>
  );
}
