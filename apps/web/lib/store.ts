import { create } from "zustand";
import type { EvaluationInput, ScenarioLoad, VehicleProfile } from "./api/types";
import { type Draft, blankDraft, draftFromInput, vehicleFromProfile } from "./draft";

type LoadedScenario = { id: string; title: string; base: EvaluationInput };

/** How the last edit was made: typing waits a moment before evaluating, a click evaluates at once. */
type EditKind = "discrete" | "typing";

type ConsoleState = {
  unitId: string | null;
  draft: Draft | null;
  scenario: LoadedScenario | null;
  editKind: EditKind;
  sessionStart: string;

  selectUnit: (unitId: string) => void;
  startManual: () => void;
  loadScenario: (scenario: ScenarioLoad) => void;
  resetToScenario: () => void;
  clear: () => void;
  patchVehicle: (patch: Partial<Draft["vehicle"]>, kind?: EditKind) => void;
  patchCrash: (patch: Partial<Draft["crash"]>) => void;
  patchScene: (patch: Partial<Draft["scene"]>, kind?: EditKind) => void;
  setSeverity: (level: NonNullable<Draft["severity"]["level"]>) => void;
  applyProfile: (profile: VehicleProfile) => void;
};

export const useConsole = create<ConsoleState>((set, get) => ({
  unitId: null,
  draft: null,
  scenario: null,
  editKind: "discrete",
  sessionStart: new Date().toISOString(),

  selectUnit: (unitId) =>
    set((s) => ({ unitId, editKind: "discrete", draft: s.draft ? { ...s.draft, unit_id: unitId } : s.draft })),

  startManual: () => set((s) => ({ scenario: null, editKind: "discrete", draft: blankDraft(s.unitId) })),

  // A unit the operator already chose stays chosen: the scenario supplies the vehicle, crash and scene.
  loadScenario: (load) =>
    set((s) => ({
      scenario: { id: load.id, title: load.title, base: load.input },
      unitId: s.unitId ?? load.input.unit_id,
      editKind: "discrete",
      draft: draftFromInput(load.input, s.unitId ?? load.input.unit_id),
    })),

  resetToScenario: () => {
    const { scenario, unitId } = get();
    if (!scenario) return;
    set({ editKind: "discrete", draft: draftFromInput(scenario.base, unitId ?? scenario.base.unit_id) });
  },

  clear: () => set({ draft: null, scenario: null, editKind: "discrete" }),

  patchVehicle: (patch, kind = "discrete") =>
    set((s) => (s.draft ? { editKind: kind, draft: { ...s.draft, vehicle: { ...s.draft.vehicle, ...patch } } } : s)),

  patchCrash: (patch) =>
    set((s) => (s.draft ? { editKind: "discrete", draft: { ...s.draft, crash: { ...s.draft.crash, ...patch } } } : s)),

  patchScene: (patch, kind = "discrete") =>
    set((s) => (s.draft ? { editKind: kind, draft: { ...s.draft, scene: { ...s.draft.scene, ...patch } } } : s)),

  setSeverity: (level) =>
    set((s) => (s.draft ? { editKind: "discrete", draft: { ...s.draft, severity: { ...s.draft.severity, level } } } : s)),

  applyProfile: (profile) =>
    set((s) =>
      s.draft ? { editKind: "discrete", draft: { ...s.draft, vehicle: vehicleFromProfile(profile) } } : s,
    ),
}));
