from collections.abc import Iterable

from app.api.schemas import AssumptionUse
from app.config_loader import ConfigSnapshot
from app.models import AssumptionStatus, EvaluationInput, Provenance, VehicleClass


def describe_used(
    keys: Iterable[str], snap: ConfigSnapshot, inp: EvaluationInput | None = None
) -> list[AssumptionUse]:
    """Turn the engine's `assumptions_used` keys into full records (value, source, status) for the UI and the audit log.

    `inp` is only needed for `input.*` keys, which describe numbers entered for one incident.
    """
    out: list[AssumptionUse] = []
    for key in keys:
        if key in snap.assumptions:
            a = snap.assumptions[key]
            out.append(
                AssumptionUse(
                    key=key,
                    kind="assumption",
                    value=a.value,
                    unit=a.unit,
                    source=a.source,
                    status=a.status,
                    # a placeholder is invented; anything else has a source behind it
                    provenance=Provenance.ASSUMED if a.status == AssumptionStatus.PLACEHOLDER else Provenance.ESTIMATED,
                    note=a.note,
                    editable=True,
                )
            )
        elif key.startswith("vehicle_specs.class_defaults."):
            vehicle_class = VehicleClass(key.rsplit(".", 1)[1])
            meta = snap.specs.class_defaults_meta
            out.append(
                AssumptionUse(
                    key=key,
                    kind="class_default",
                    value=snap.specs.class_defaults[vehicle_class].model_dump(),
                    source=meta.source,
                    status=meta.status,
                    provenance=meta.provenance,
                    note=meta.note,
                )
            )
        elif key == "input.vehicle.curb_weight" and inp is not None:
            v = inp.vehicle
            out.append(_input_weight(key, v.estimated_curb_weight_lb, v.curb_weight_source, "curb weight"))
        elif key == "input.vehicle.load_weight" and inp is not None:
            out.append(_input_weight(key, inp.vehicle.estimated_load_weight_lb, None, "load weight"))
        else:
            raise ValueError(f"engine reported an assumption key this service cannot describe: {key}")
    return out


def _input_weight(key: str, value: float | None, source: str | None, label: str) -> AssumptionUse:
    return AssumptionUse(
        key=key,
        kind="input",
        value=value,
        unit="lb",
        source=source or f"Entered by the operator or guessed from the vehicle class; no {label} source",
        status=AssumptionStatus.PLACEHOLDER,
        provenance=Provenance.ASSUMED,
        note=f"The {label} for this incident is marked ASSUMED, so the verdict rests on an unverified number.",
    )
