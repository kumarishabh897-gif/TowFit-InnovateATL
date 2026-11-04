import type { components } from "./schema";

type S = components["schemas"];

export type EvaluationInput = S["EvaluationInput"];
export type EvaluationResponse = S["EvaluationResponse"];
export type VehicleProfile = S["VehicleProfile"];
export type CrashCondition = S["CrashCondition"];
export type Scene = S["Scene"];
export type IncidentSeverity = S["IncidentSeverity"];
export type Verdict = S["Verdict"];
export type Reason = S["Reason"];
export type AssumptionUse = S["AssumptionUse"];
export type FleetUnit = S["FleetUnit"];
export type ScenarioSummary = S["ScenarioSummary"];
export type ScenarioLoad = S["ScenarioLoad"];
export type DecisionSummary = S["DecisionSummary"];
export type DecisionDetail = S["DecisionDetail"];
export type DecisionEventOut = S["DecisionEventOut"];
export type CameraFrame = S["CameraFrame"];
export type CameraClassification = S["CameraClassification"];
export type VehicleSpecs = S["VehicleSpecs"];
export type VehicleSpec = S["VehicleSpec"];

export type VehicleClass = S["VehicleClass"];
export type NeutralStatus = S["NeutralStatus"];
export type Orientation = S["Orientation"];
export type LiveTrafficRisk = S["LiveTrafficRisk"];
export type Severity = S["Severity"];
export type Provenance = S["Provenance"];
export type VerdictStatus = S["VerdictStatus"];
export type ReasonEffect = S["ReasonEffect"];
export type OperatorAction = S["OperatorAction"];
