import type {
  CrashCondition,
  EvaluationInput,
  IncidentSeverity,
  NeutralStatus,
  Provenance,
  Scene,
  Severity,
  VehicleClass,
  VehicleProfile,
} from "./api/types";

/**
 * The form's working copy. Unlike EvaluationInput it can be incomplete: the fields an operator must state
 * (vehicle class, weight, neutral status, severity) start empty so the console never guesses them.
 */
export type Draft = {
  unit_id: string | null;
  loaded_scenario_id: string | null;
  vehicle: {
    make_model: string;
    vehicle_class: VehicleClass | null;
    estimated_curb_weight_lb: number | null;
    curb_weight_provenance: Provenance;
    curb_weight_source: string | null;
    estimated_load_weight_lb: number | null;
    load_weight_provenance: Provenance;
    drivetrain: string | null;
    tire_width_mm: number | null;
    ground_clearance_mm: number | null;
    wheelbase_mm: number | null;
    classification_provenance: "OPERATOR" | "SIM";
  };
  crash: Omit<CrashCondition, "neutral_status"> & { neutral_status: NeutralStatus | null };
  scene: Scene;
  severity: { level: Severity | null; provenance: IncidentSeverity["provenance"] };
};

/** Baseline for manual entry: the no-damage state, which the operator confirms or changes on scene. */
export function blankDraft(unitId: string | null): Draft {
  return {
    unit_id: unitId,
    loaded_scenario_id: null,
    vehicle: {
      make_model: "",
      vehicle_class: null,
      estimated_curb_weight_lb: null,
      curb_weight_provenance: "ASSUMED",
      curb_weight_source: null,
      estimated_load_weight_lb: null,
      load_weight_provenance: "ASSUMED",
      drivetrain: null,
      tire_width_mm: null,
      ground_clearance_mm: null,
      wheelbase_mm: null,
      classification_provenance: "OPERATOR",
    },
    crash: {
      tires_intact: 4,
      wheels_locked_or_damaged: 0,
      axle_damage: false,
      airbags_deployed: false,
      orientation: "upright",
      fire_or_fuel_leak: false,
      neutral_status: null,
    },
    scene: {
      lanes_total: 3,
      lanes_blocked: 1,
      shoulder_available: true,
      shoulder_width_ok: true,
      grade_or_curve: false,
      live_traffic_risk: "low",
      live_traffic_risk_provenance: "SIM",
    },
    severity: { level: null, provenance: "OPERATOR" },
  };
}

export function draftFromInput(input: EvaluationInput, unitOverride?: string | null): Draft {
  return {
    unit_id: unitOverride ?? input.unit_id,
    loaded_scenario_id: input.loaded_scenario_id ?? null,
    vehicle: vehicleFromProfile(input.vehicle),
    crash: { ...input.crash },
    scene: { ...input.scene },
    severity: { level: input.severity.level, provenance: input.severity.provenance },
  };
}

/** The vehicle section of the form, from a full profile (an API scenario, a spec row or a camera fixture). */
export function vehicleFromProfile(v: VehicleProfile): Draft["vehicle"] {
  return {
    make_model: v.make_model,
    vehicle_class: v.vehicle_class,
    estimated_curb_weight_lb: v.estimated_curb_weight_lb,
    curb_weight_provenance: v.curb_weight_provenance,
    curb_weight_source: v.curb_weight_source ?? null,
    estimated_load_weight_lb: v.estimated_load_weight_lb ?? null,
    load_weight_provenance: v.load_weight_provenance,
    drivetrain: v.drivetrain ?? null,
    tire_width_mm: v.tire_width_mm ?? null,
    ground_clearance_mm: v.ground_clearance_mm ?? null,
    wheelbase_mm: v.wheelbase_mm ?? null,
    classification_provenance: v.classification_provenance,
  };
}

export type MissingField = { id: string; label: string };

export function missingFields(d: Draft): MissingField[] {
  const out: MissingField[] = [];
  if (!d.unit_id) out.push({ id: "unit", label: "Patrol unit" });
  if (!d.vehicle.make_model.trim()) out.push({ id: "make_model", label: "Make and model" });
  if (!d.vehicle.vehicle_class) out.push({ id: "vehicle_class", label: "Vehicle class" });
  if (d.vehicle.estimated_curb_weight_lb === null || d.vehicle.estimated_curb_weight_lb <= 0) {
    out.push({ id: "curb_weight", label: "Curb weight" });
  }
  if (!d.crash.neutral_status) out.push({ id: "neutral_status", label: "Neutral status" });
  if (!d.severity.level) out.push({ id: "severity", label: "Incident severity" });
  if (d.scene.lanes_blocked > d.scene.lanes_total) out.push({ id: "lanes", label: "Lanes blocked (more than total)" });
  return out;
}

/** The API request for a complete draft, or null while a required field is still missing. */
export function toInput(d: Draft): EvaluationInput | null {
  if (missingFields(d).length > 0) return null;
  const v = d.vehicle;
  return {
    unit_id: d.unit_id as string,
    loaded_scenario_id: d.loaded_scenario_id,
    vehicle: {
      make_model: v.make_model.trim(),
      vehicle_class: v.vehicle_class as VehicleClass,
      estimated_curb_weight_lb: v.estimated_curb_weight_lb as number,
      curb_weight_provenance: v.curb_weight_provenance,
      curb_weight_source: v.curb_weight_source,
      estimated_load_weight_lb: v.estimated_load_weight_lb,
      load_weight_provenance: v.load_weight_provenance,
      drivetrain: v.drivetrain,
      tire_width_mm: v.tire_width_mm,
      ground_clearance_mm: v.ground_clearance_mm,
      wheelbase_mm: v.wheelbase_mm,
      classification_provenance: v.classification_provenance,
    },
    crash: { ...d.crash, neutral_status: d.crash.neutral_status as NeutralStatus },
    scene: { ...d.scene },
    severity: { level: d.severity.level as Severity, provenance: d.severity.provenance },
  };
}

/** True when the form no longer matches the scenario it was loaded from. */
export function isEdited(d: Draft, base: EvaluationInput): boolean {
  const current = toInput(d);
  if (!current) return true;
  const strip = (i: EvaluationInput) => JSON.stringify({ ...i, loaded_scenario_id: null }, replacer);
  return strip(current) !== strip(base);
}

// Keys in a stable order, and undefined treated as null, so equal inputs compare equal.
function replacer(_: string, value: unknown) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .map(([k, v]) => [k, v === undefined ? null : v] as const)
        .sort(([a], [b]) => a.localeCompare(b)),
    );
  }
  return value;
}
