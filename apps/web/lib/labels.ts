import type { NeutralStatus, OperatorAction, Orientation, ReasonEffect, Severity, VehicleClass, VerdictStatus } from "./api/types";

export const CLASS_OPTIONS: { value: VehicleClass; label: string }[] = [
  { value: "passenger_car", label: "Passenger car" },
  { value: "suv", label: "SUV" },
  { value: "pickup", label: "Pickup" },
  { value: "van", label: "Van" },
  { value: "box_truck", label: "Box truck" },
  { value: "tractor_trailer", label: "Tractor-trailer" },
  { value: "bus", label: "Bus" },
  { value: "motorcycle", label: "Motorcycle" },
  { value: "unknown", label: "Unknown" },
];

export const NEUTRAL_OPTIONS: { value: NeutralStatus; label: string; description: string }[] = [
  { value: "in_neutral", label: "In neutral", description: "Already there" },
  { value: "can_be_shifted", label: "Can shift", description: "Operator shifts it" },
  { value: "can_be_forced", label: "Can force", description: "Override or tow mode" },
  { value: "unconfirmed", label: "Unconfirmed", description: "Not tried yet" },
  { value: "cannot", label: "Cannot", description: "Will not go in" },
];

export const ORIENTATION_OPTIONS: { value: Orientation; label: string }[] = [
  { value: "upright", label: "Upright" },
  { value: "on_side", label: "On its side" },
  { value: "roof", label: "On its roof" },
];

export const SEVERITY_OPTIONS: { value: Severity; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export const VERDICT_WORD: Record<VerdictStatus, string> = { GREEN: "GREEN", YELLOW: "YELLOW", RED: "RED" };

/** What the operator does next, in the words of the brief's verdict table. */
export const VERDICT_ACTION: Record<VerdictStatus, string> = {
  GREEN: "Deploy the attachment",
  YELLOW: "Confirm before deployment",
  RED: "Dispatch the correct wrecker now",
};

export const EFFECT_LABEL: Record<ReasonEffect, string> = {
  RED: "Rules it out",
  YELLOW: "Needs confirmation",
  GREEN: "Passed",
  ADVISORY: "Advisory",
};

export const ACTION_LABEL: Record<OperatorAction, string> = {
  deploy: "Deploy attachment",
  wait_for_confirmation: "Wait for confirmation",
  dispatch_wrecker: "Dispatch wrecker",
};

/** Past tense, for the log. */
export const ACTION_DONE: Record<OperatorAction, string> = {
  deploy: "Deployed",
  wait_for_confirmation: "Waited for confirmation",
  dispatch_wrecker: "Dispatched wrecker",
};

export const WRECKER_LABEL: Record<string, string> = { light_duty: "Light-duty wrecker or flatbed", heavy_duty: "Heavy-duty wrecker" };

export const SCENARIO_SHORT: Record<string, string> = {
  "01_green_accord": "1",
  "02_red_box_truck": "2",
  "03_yellow_pickup": "3",
};

/** The fixed framing from the brief. The API sends the same string with every verdict; this is for screens with no verdict yet. */
export const DISCLAIMER =
  "TowFit does not replace operator judgment or authorize a move. It provides a documented safety recommendation based on vehicle, rig, and scene constraints.";
