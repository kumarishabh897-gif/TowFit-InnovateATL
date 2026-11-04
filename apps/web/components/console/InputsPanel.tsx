"use client";

import { Camera } from "@phosphor-icons/react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { NumberInput } from "@/components/ui/NumberInput";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";
import { Segmented } from "@/components/ui/Segmented";
import { SelectField } from "@/components/ui/SelectField";
import { SwitchRow } from "@/components/ui/SwitchRow";
import { TextInput } from "@/components/ui/TextInput";
import { useVehicleSpecs } from "@/lib/api/hooks";
import type { LiveTrafficRisk, Orientation } from "@/lib/api/types";
import { missingFields } from "@/lib/draft";
import { CLASS_OPTIONS, NEUTRAL_OPTIONS, ORIENTATION_OPTIONS, SEVERITY_OPTIONS } from "@/lib/labels";
import { useConsole } from "@/lib/store";
import { CameraPanel, SIM_LABEL } from "./CameraPanel";

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border-b border-line px-4 py-4 last:border-b-0">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {aside}
      </div>
      <div className="space-y-3.5">{children}</div>
    </section>
  );
}

const COUNT_OPTIONS = [0, 1, 2, 3, 4].map((n) => ({ value: n, label: String(n) }));
const TRAFFIC_OPTIONS: { value: LiveTrafficRisk; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export function InputsPanel() {
  const draft = useConsole((s) => s.draft);
  const patchVehicle = useConsole((s) => s.patchVehicle);
  const patchCrash = useConsole((s) => s.patchCrash);
  const patchScene = useConsole((s) => s.patchScene);
  const setSeverity = useConsole((s) => s.setSeverity);
  const specs = useVehicleSpecs();
  const [cameraOpen, setCameraOpen] = useState(false);
  const [showDimensions, setShowDimensions] = useState(false);

  if (!draft) return null;
  const { vehicle: v, crash: c, scene: s } = draft;
  const missing = new Set(missingFields(draft).map((m) => m.id));

  function onMakeModel(text: string) {
    // An exact match with a known model fills its class and weight from the spec table (ESTIMATED, with its source).
    const spec = specs.data?.models.find((m) => m.make_model.toLowerCase() === text.trim().toLowerCase());
    if (spec) {
      patchVehicle({
        make_model: spec.make_model,
        vehicle_class: spec.vehicle_class,
        ...(spec.curb_weight_lb !== null && spec.curb_weight_lb !== undefined
          ? { estimated_curb_weight_lb: spec.curb_weight_lb, curb_weight_provenance: "ESTIMATED" as const, curb_weight_source: spec.source }
          : {}),
        wheelbase_mm: spec.wheelbase_mm ?? null,
        classification_provenance: "OPERATOR",
      });
    } else {
      patchVehicle({ make_model: text, classification_provenance: "OPERATOR" }, "typing");
    }
  }

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-panel border border-line bg-surface">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Section
          title="Vehicle"
          aside={
            <Button size="sm" variant="secondary" aria-expanded={cameraOpen} onClick={() => setCameraOpen((o) => !o)}>
              <Camera size={14} weight="bold" aria-hidden />
              Classify from camera
            </Button>
          }
        >
          {cameraOpen && <CameraPanel onDone={() => setCameraOpen(false)} />}

          <Field
            label="Make and model"
            htmlFor="field-make_model"
            required
            invalid={missing.has("make_model")}
            chip={v.classification_provenance === "SIM" ? <ProvenanceChip provenance="SIM" /> : undefined}
            hint={v.classification_provenance === "SIM" ? SIM_LABEL : "Pick a known model to fill its class and weight, or type your own."}
          >
            <TextInput
              id="field-make_model"
              list="vehicle-models"
              value={v.make_model}
              invalid={missing.has("make_model")}
              placeholder="e.g. 2022 Honda Accord"
              onChange={(e) => onMakeModel(e.target.value)}
              autoComplete="off"
            />
            <datalist id="vehicle-models">
              {specs.data?.models.map((m) => (
                <option key={m.id} value={m.make_model} />
              ))}
            </datalist>
          </Field>

          <Field label="Vehicle class" htmlFor="field-vehicle_class" required invalid={missing.has("vehicle_class")}>
            <SelectField
              id="field-vehicle_class"
              value={v.vehicle_class}
              placeholder="Choose a class"
              invalid={missing.has("vehicle_class")}
              options={CLASS_OPTIONS}
              onChange={(value) => patchVehicle({ vehicle_class: value as NonNullable<typeof v.vehicle_class> })}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Curb weight"
              htmlFor="field-curb_weight"
              required
              invalid={missing.has("curb_weight")}
              chip={v.estimated_curb_weight_lb !== null ? <ProvenanceChip provenance={v.curb_weight_provenance} /> : undefined}
            >
              <NumberInput
                id="field-curb_weight"
                unit="lb"
                value={v.estimated_curb_weight_lb}
                invalid={missing.has("curb_weight")}
                placeholder="Required"
                onChange={(n) =>
                  patchVehicle({ estimated_curb_weight_lb: n, curb_weight_provenance: "ASSUMED", curb_weight_source: null }, "typing")
                }
              />
            </Field>
            <Field
              label="Load weight"
              htmlFor="field-load_weight"
              chip={v.estimated_load_weight_lb ? <ProvenanceChip provenance={v.load_weight_provenance} /> : undefined}
            >
              <NumberInput
                id="field-load_weight"
                unit="lb"
                value={v.estimated_load_weight_lb}
                placeholder="None"
                onChange={(n) => patchVehicle({ estimated_load_weight_lb: n, load_weight_provenance: "ASSUMED" }, "typing")}
              />
            </Field>
          </div>
          {v.curb_weight_source && <p className="-mt-2 text-xs leading-5 text-ink-3">Weight source: {v.curb_weight_source}</p>}

          <div>
            <button
              type="button"
              aria-expanded={showDimensions}
              onClick={() => setShowDimensions((o) => !o)}
              className="press text-xs font-medium text-accent underline underline-offset-2"
            >
              {showDimensions ? "Hide dimensions" : "Enter dimensions (optional)"}
            </button>
            {showDimensions && (
              <div className="mt-2.5 grid grid-cols-3 gap-3">
                <Field label="Tire width" htmlFor="field-tire_width">
                  <NumberInput id="field-tire_width" unit="mm" value={v.tire_width_mm} placeholder="Class" onChange={(n) => patchVehicle({ tire_width_mm: n }, "typing")} />
                </Field>
                <Field label="Clearance" htmlFor="field-clearance">
                  <NumberInput id="field-clearance" unit="mm" value={v.ground_clearance_mm} placeholder="Class" onChange={(n) => patchVehicle({ ground_clearance_mm: n }, "typing")} />
                </Field>
                <Field label="Wheelbase" htmlFor="field-wheelbase">
                  <NumberInput id="field-wheelbase" unit="mm" value={v.wheelbase_mm} placeholder="Class" onChange={(n) => patchVehicle({ wheelbase_mm: n }, "typing")} />
                </Field>
                <p className="col-span-3 -mt-1 text-xs text-ink-3">
                  Left blank, class-typical values are used and labeled <ProvenanceChip provenance="ASSUMED" />.
                </p>
              </div>
            )}
          </div>
        </Section>

        <Section title="Crash condition">
          <Field
            label="Can it be put in neutral?"
            required
            invalid={missing.has("neutral_status")}
            chip={<ProvenanceChip provenance="OPERATOR" />}
          >
            <Segmented
              label="Neutral status"
              value={c.neutral_status}
              invalid={missing.has("neutral_status")}
              options={NEUTRAL_OPTIONS}
              columns={6}
              spans={[2, 2, 2, 3, 3]}
              size="lg"
              onChange={(value) => patchCrash({ neutral_status: value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tires intact">
              <Segmented label="Tires intact" value={c.tires_intact} options={COUNT_OPTIONS} onChange={(value) => patchCrash({ tires_intact: value })} />
            </Field>
            <Field label="Wheels locked or damaged">
              <Segmented
                label="Wheels locked or damaged"
                value={c.wheels_locked_or_damaged}
                options={COUNT_OPTIONS}
                onChange={(value) => patchCrash({ wheels_locked_or_damaged: value })}
              />
            </Field>
          </div>
          <Field label="Orientation">
            <Segmented
              label="Orientation"
              value={c.orientation}
              options={ORIENTATION_OPTIONS}
              onChange={(value: Orientation) => patchCrash({ orientation: value })}
            />
          </Field>
          <div className="divide-y divide-line">
            <SwitchRow id="sw-fire" label="Fire or fuel leak" danger checked={c.fire_or_fuel_leak} onChange={(checked) => patchCrash({ fire_or_fuel_leak: checked })} />
            <SwitchRow id="sw-axle" label="Axle damage" danger checked={c.axle_damage} onChange={(checked) => patchCrash({ axle_damage: checked })} />
            <SwitchRow id="sw-airbags" label="Airbags deployed" checked={c.airbags_deployed} onChange={(checked) => patchCrash({ airbags_deployed: checked })} />
          </div>
        </Section>

        <Section title="Scene">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Lanes total">
              <Segmented
                label="Lanes total"
                value={s.lanes_total}
                options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: n, label: String(n) }))}
                onChange={(value) => patchScene({ lanes_total: value, lanes_blocked: Math.min(s.lanes_blocked, value) })}
              />
            </Field>
            <Field label="Lanes blocked" invalid={missing.has("lanes")}>
              <Segmented
                label="Lanes blocked"
                value={s.lanes_blocked}
                options={Array.from({ length: s.lanes_total + 1 }, (_, n) => ({ value: n, label: String(n) }))}
                onChange={(value) => patchScene({ lanes_blocked: value })}
              />
            </Field>
          </div>
          <div className="divide-y divide-line">
            <SwitchRow id="sw-shoulder" label="Shoulder available" checked={s.shoulder_available} onChange={(checked) => patchScene({ shoulder_available: checked })} />
            <SwitchRow id="sw-shoulder-width" label="Shoulder wide enough to park" checked={s.shoulder_width_ok} onChange={(checked) => patchScene({ shoulder_width_ok: checked })} />
            <SwitchRow id="sw-grade" label="On a grade or curve" checked={s.grade_or_curve} onChange={(checked) => patchScene({ grade_or_curve: checked })} />
          </div>
          <Field label="Live traffic risk" chip={<ProvenanceChip provenance={s.live_traffic_risk_provenance} />}>
            <Segmented
              label="Live traffic risk"
              value={s.live_traffic_risk}
              options={TRAFFIC_OPTIONS}
              onChange={(value) => patchScene({ live_traffic_risk: value })}
            />
          </Field>
        </Section>

        <Section title="Incident">
          <Field label="Severity" required invalid={missing.has("severity")} chip={<ProvenanceChip provenance="OPERATOR" />} hint="From 911, camera or officer input. Entered by hand, not read from a sensor.">
            <Segmented label="Severity" value={draft.severity.level} invalid={missing.has("severity")} options={SEVERITY_OPTIONS} onChange={setSeverity} />
          </Field>
        </Section>
      </div>
    </div>
  );
}
