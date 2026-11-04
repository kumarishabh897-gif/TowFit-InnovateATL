import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL, ApiError, api, unwrap } from "./client";
import type { EvaluationInput, OperatorAction } from "./types";

/** Runs a request and turns a network failure into an error that says what to check. */
async function call<T>(run: () => Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  try {
    return unwrap(await run());
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(`Cannot reach the API at ${API_BASE_URL}. Is it running?`, null);
  }
}

export const evaluate = (input: EvaluationInput) => call(() => api.POST("/v1/towfit/evaluate", { body: input }));

export const loadScenario = (scenario_id: string) =>
  call(() => api.POST("/v1/scenarios/{scenario_id}/load", { params: { path: { scenario_id } } }));

export const classifyFrame = (frame_id: string) =>
  call(() => api.POST("/v1/camera/frames/{frame_id}/classify", { params: { path: { frame_id } } }));

export const recordEvent = (decision_id: number, body: { action: OperatorAction; note?: string }) =>
  call(() =>
    api.POST("/v1/decisions/{decision_id}/events", {
      params: { path: { decision_id } },
      body: { kind: "operator_action", action: body.action, note: body.note ?? null },
    }),
  );

export const useFleet = () =>
  useQuery({ queryKey: ["fleet"], queryFn: () => call(() => api.GET("/v1/fleet")), staleTime: 30_000 });

export const useVehicleSpecs = () =>
  useQuery({ queryKey: ["vehicle-specs"], queryFn: () => call(() => api.GET("/v1/vehicle-specs")), staleTime: 60_000 });

export const useScenarios = () =>
  useQuery({ queryKey: ["scenarios"], queryFn: () => call(() => api.GET("/v1/scenarios")), staleTime: 60_000 });

export const useCameraFrames = (enabled: boolean) =>
  useQuery({
    queryKey: ["camera-frames"],
    queryFn: () => call(() => api.GET("/v1/camera/frames")),
    enabled,
    staleTime: 60_000,
  });

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => call(() => api.GET("/health")),
    refetchInterval: 15_000,
    retry: false,
  });

/** The Decision Record log. `since` limits it to this session; null means all records. */
export const useDecisions = (since: string | null) =>
  useQuery({
    queryKey: ["decisions", since],
    queryFn: () =>
      call(() => api.GET("/v1/decisions", { params: { query: { since: since ?? undefined, limit: 100 } } })),
  });

export const useDecisionDetail = (id: number | null) =>
  useQuery({
    queryKey: ["decision", id],
    queryFn: () => call(() => api.GET("/v1/decisions/{decision_id}", { params: { path: { decision_id: id as number } } })),
    enabled: id !== null,
  });
