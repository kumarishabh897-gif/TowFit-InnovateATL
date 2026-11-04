"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { evaluate } from "./api/hooks";
import type { EvaluationResponse } from "./api/types";
import { missingFields, toInput } from "./draft";
import { useConsole } from "./store";

/** Evaluation is near-instant; this keeps the "computing" state on screen long enough to register. */
const MIN_COMPUTING_MS = 260;
/** After typing stops, wait this long before evaluating, so half-typed numbers are not logged. */
const TYPING_DEBOUNCE_MS = 450;

export type EvalPhase = "empty" | "incomplete" | "computing" | "ready" | "error";

export type LiveEvaluation = {
  phase: EvalPhase;
  response: EvaluationResponse | null;
  error: string | null;
  missing: { id: string; label: string }[];
  retry: () => void;
};

/**
 * Evaluates the current form on every settled change. Each evaluation is a real POST that logs a
 * Decision Record; the verdict shown always comes from the engine's response, never from the form.
 */
export function useLiveEvaluation(): LiveEvaluation {
  const draft = useConsole((s) => s.draft);
  const queryClient = useQueryClient();
  const input = useMemo(() => (draft ? toInput(draft) : null), [draft]);
  const inputKey = input ? JSON.stringify(input) : null;
  const missing = useMemo(() => (draft ? missingFields(draft) : []), [draft]);

  const [state, setState] = useState<{ response: EvaluationResponse | null; error: string | null; computing: boolean }>({
    response: null,
    error: null,
    computing: false,
  });
  const [attempt, setAttempt] = useState(0);
  const latest = useRef(0);

  useEffect(() => {
    const mine = ++latest.current;
    if (!input) {
      setState({ response: null, computing: false, error: null });
      return;
    }
    setState((s) => ({ ...s, computing: true, error: null }));
    const delay = useConsole.getState().editKind === "typing" ? TYPING_DEBOUNCE_MS : 0;
    const timer = setTimeout(async () => {
      const started = performance.now();
      try {
        const response = await evaluate(input);
        const remaining = MIN_COMPUTING_MS - (performance.now() - started);
        if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
        if (mine !== latest.current) return; // a newer edit superseded this one
        setState({ response, error: null, computing: false });
        queryClient.invalidateQueries({ queryKey: ["decisions"] });
      } catch (error) {
        if (mine !== latest.current) return;
        setState((s) => ({ ...s, computing: false, error: error instanceof Error ? error.message : "Evaluation failed" }));
      }
    }, delay);
    return () => clearTimeout(timer);
    // `input` is fully determined by `inputKey`; re-running on object identity would re-evaluate unchanged forms.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputKey, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  let phase: EvalPhase;
  if (!draft) phase = "empty";
  else if (!input) phase = "incomplete";
  else if (state.error) phase = "error";
  else if (state.computing) phase = "computing";
  else phase = state.response ? "ready" : "computing";

  return { phase, response: draft ? state.response : null, error: state.error, missing, retry };
}
