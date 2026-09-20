"""TowFit rule engine (brief section 6, revised so neutral status drives GREEN).

Not ML: a plain, ordered list of rules. Each rule either fires or stays quiet, and every firing
becomes a plain-language Reason. The verdict is derived only from the reasons:

    any RED reason      -> RED
    else any YELLOW     -> YELLOW
    else                -> GREEN   (ADVISORY reasons never change the verdict)

Nothing here looks at a scenario name. The engine reads the input fields, the unit's rig profile
and the assumptions, so changing any of them changes the verdict.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.config_loader import ConfigStore
from app.models import (
    Assumption,
    CrashCondition,
    EvaluationInput,
    LiveTrafficRisk,
    MinutesEstimate,
    NeutralStatus,
    Orientation,
    Provenance,
    Reason,
    ReasonEffect,
    Severity,
    UnitProfile,
    VehicleClass,
    VehicleProfile,
    VehicleSpecs,
    Verdict,
    VerdictStatus,
    WreckerClass,
    WreckerRecommendation,
)

# Classes no rig of ours will lift, whatever the unit's own compatible list says (brief section 6.1).
EXCLUDED_CLASSES = frozenset({VehicleClass.MOTORCYCLE, VehicleClass.BUS, VehicleClass.TRACTOR_TRAILER})

# Classes that need a heavy-duty wrecker. `unknown` is here on purpose: we cannot rule out a heavy vehicle.
HEAVY_WRECKER_CLASSES = frozenset(
    {VehicleClass.BOX_TRUCK, VehicleClass.BUS, VehicleClass.TRACTOR_TRAILER, VehicleClass.UNKNOWN}
)

# Every rule id, in the order the engine evaluates them (which is the order reasons are listed).
RULE_IDS: tuple[str, ...] = (
    # 1. Fit: can this rig carry or move it?
    "R-CLASS-EXCLUDED",
    "R-CLASS-INCOMPATIBLE",
    "R-CLASS-OK",
    "R-WEIGHT-OVER",
    "R-WEIGHT-OK",
    "R-WEIGHT-MARGIN",
    "R-DIM-TIRE-WIDTH",
    "R-DIM-CLEARANCE",
    "R-DIM-WHEELBASE",
    "R-DIM-UNVERIFIED",
    "R-DIM-OK",
    # 2. Grip: are the tires and wheels usable?
    "R-TIRES-FEW",
    "R-WHEELS-MANY",
    "R-GRIP-PARTIAL",
    "R-GRIP-OK",
    # 3. Damage: is it safe to move after this crash?
    "R-ORIENTATION",
    "R-FIRE",
    "R-AXLE",
    "R-STRUCTURE-OK",
    "R-AIRBAGS",
    "R-SEVERITY-HIGH",
    "R-NEUTRAL-NO",
    "R-NEUTRAL-UNCONFIRMED",
    "R-NEUTRAL-OK",
    # 4. Scene: is a quick move safer than waiting?
    "R-SHOULDER-NONE",
    "R-SHOULDER-NARROW",
    "R-SHOULDER-OK",
    "R-GRADE-TRAFFIC",
)


class UnknownUnitError(KeyError):
    """The requested unit_id is not in fleet.yaml."""


@dataclass(frozen=True)
class _Finding:
    reason: Reason
    confirm: str | None = None  # who must confirm, for YELLOW findings


@dataclass
class _Ctx:
    inp: EvaluationInput
    unit: UnitProfile
    assumptions: Mapping[str, Assumption]
    specs: VehicleSpecs
    findings: list[_Finding] = field(default_factory=list)

    @property
    def vehicle(self) -> VehicleProfile:
        return self.inp.vehicle

    @property
    def crash(self) -> CrashCondition:
        return self.inp.crash

    def add(
        self,
        rule_id: str,
        effect: ReasonEffect,
        text: str,
        keys: tuple[str, ...] = (),
        confirm: str | None = None,
    ) -> None:
        assert rule_id in RULE_IDS, rule_id
        self.findings.append(_Finding(Reason(rule_id=rule_id, effect=effect, text=text, assumption_keys=list(keys)), confirm))


def _num(assumptions: Mapping[str, Assumption], key: str) -> float:
    value = _assumption(assumptions, key).value
    if isinstance(value, list):
        raise ValueError(f"assumption {key} is a range, expected a single value")
    return float(value)


def _range(assumptions: Mapping[str, Assumption], key: str) -> tuple[float, float]:
    value = _assumption(assumptions, key).value
    if not isinstance(value, list):
        raise ValueError(f"assumption {key} is a single value, expected a [low, high] range")
    return float(value[0]), float(value[1])


def _assumption(assumptions: Mapping[str, Assumption], key: str) -> Assumption:
    try:
        return assumptions[key]
    except KeyError:
        raise KeyError(f"assumptions.yaml has no entry {key!r}") from None


def _lb(value: float) -> str:
    return f"{value:,.0f} lb"


def _mm(value: float) -> str:
    return f"{value:,.0f} mm"


# ---------------------------------------------------------------- 1. Fit


def _rule_class(ctx: _Ctx) -> None:
    vc = ctx.vehicle.vehicle_class
    label = vc.value.replace("_", " ")
    if vc in EXCLUDED_CLASSES:
        ctx.add("R-CLASS-EXCLUDED", ReasonEffect.RED, f"Vehicle class {label} is never moved with this rig type.")
    elif vc not in ctx.unit.compatible_vehicle_classes:
        if vc == VehicleClass.UNKNOWN:
            text = f"Vehicle class is unknown, so it cannot be confirmed compatible with {ctx.unit.unit_id}'s rig."
        else:
            text = f"Vehicle class {label} is not in {ctx.unit.unit_id}'s compatible classes."
        ctx.add("R-CLASS-INCOMPATIBLE", ReasonEffect.RED, text)
    else:
        ctx.add("R-CLASS-OK", ReasonEffect.GREEN, f"Vehicle class {label} is compatible with {ctx.unit.unit_id}'s rig.")


def _rule_weight(ctx: _Ctx) -> None:
    v, unit = ctx.vehicle, ctx.unit
    total = v.estimated_curb_weight_lb + (v.estimated_load_weight_lb or 0.0)
    capacity = unit.rig_capacity_lb
    cap_key = unit.assumption_keys["rig_capacity_lb"]
    keys = [cap_key]
    if v.curb_weight_provenance == Provenance.ASSUMED:
        keys.append("input.vehicle.curb_weight")
    if v.estimated_load_weight_lb and v.load_weight_provenance == Provenance.ASSUMED:
        keys.append("input.vehicle.load_weight")
    if v.estimated_load_weight_lb:
        detail = (
            f"{_lb(v.estimated_curb_weight_lb)} curb, {v.curb_weight_provenance.value} + "
            f"{_lb(v.estimated_load_weight_lb)} load, {v.load_weight_provenance.value}"
        )
    else:
        detail = v.curb_weight_provenance.value
    label = f"Estimated weight {_lb(total)} ({detail})"

    if total > capacity:
        ctx.add(
            "R-WEIGHT-OVER",
            ReasonEffect.RED,
            f"{label} exceeds {unit.unit_id}'s {_lb(capacity)} rated capacity.",
            tuple(keys),
        )
        return
    ctx.add(
        "R-WEIGHT-OK",
        ReasonEffect.GREEN,
        f"{label} is within {unit.unit_id}'s {_lb(capacity)} rated capacity.",
        tuple(keys),
    )
    fraction = _num(ctx.assumptions, "engine.weight_advisory_fraction")
    if total > capacity * fraction:
        ctx.add(
            "R-WEIGHT-MARGIN",
            ReasonEffect.ADVISORY,
            f"Weight is {total / capacity:.0%} of rated capacity, above the {fraction:.0%} advisory margin. "
            "Advisory only; it does not change the verdict.",
            (*keys, "engine.weight_advisory_fraction"),
        )


def _rule_dimensions(ctx: _Ctx) -> None:
    v, unit = ctx.vehicle, ctx.unit
    defaults = ctx.specs.class_defaults.get(v.vehicle_class)
    lo, hi = unit.rig_tire_width_range_mm
    checks = (
        # (rule id, label, entered value, class default, fits the rig?, how a miss reads, unit field it depends on)
        ("R-DIM-TIRE-WIDTH", "Tire width", v.tire_width_mm, defaults and defaults.tire_width_mm,
         lambda x: lo <= x <= hi, f"outside the rig's {_mm(lo)}-{_mm(hi)} grip range", "rig_tire_width_range_mm"),
        ("R-DIM-CLEARANCE", "Ground clearance", v.ground_clearance_mm, defaults and defaults.ground_clearance_mm,
         lambda x: x >= unit.rig_min_ground_clearance_mm,
         f"below the rig's {_mm(unit.rig_min_ground_clearance_mm)} minimum", "rig_min_ground_clearance_mm"),
        ("R-DIM-WHEELBASE", "Wheelbase", v.wheelbase_mm, defaults and defaults.wheelbase_mm,
         lambda x: x <= unit.rig_max_wheelbase_mm,
         f"above the rig's {_mm(unit.rig_max_wheelbase_mm)} maximum", "rig_max_wheelbase_mm"),
    )
    passed: list[str] = []
    passed_keys: list[str] = []
    fired = False
    for rule_id, label, entered, default, fits, miss, unit_field in checks:
        value = entered if entered is not None else default
        if value is None:
            fired = True
            ctx.add(
                "R-DIM-UNVERIFIED",
                ReasonEffect.YELLOW,
                f"{label} was not entered and this vehicle class has no typical value, so it could not be checked.",
                confirm="on-scene supervisor: confirm the vehicle fits the rig",
            )
            continue
        source = "entered" if entered is not None else "class-typical, ASSUMED"
        keys = [unit.assumption_keys[unit_field]]
        if entered is None:
            keys.append(f"vehicle_specs.class_defaults.{v.vehicle_class.value}")
        if fits(value):
            passed.append(f"{label.lower()} {_mm(value)} ({source})")
            passed_keys.extend(keys)
        else:
            fired = True
            ctx.add(rule_id, ReasonEffect.RED, f"{label} {_mm(value)} ({source}) is {miss}.", tuple(keys))
    if passed and not fired:
        ctx.add(
            "R-DIM-OK",
            ReasonEffect.GREEN,
            "Vehicle dimensions fit the rig: " + ", ".join(passed) + ".",
            tuple(dict.fromkeys(passed_keys)),
        )


# ---------------------------------------------------------------- 2. Grip


def _rule_grip(ctx: _Ctx) -> None:
    c = ctx.crash
    red = False
    if c.tires_intact < 2:
        red = True
        ctx.add("R-TIRES-FEW", ReasonEffect.RED, f"Only {c.tires_intact} of 4 tires are intact; the rig needs at least 2 to grip.")
    if c.wheels_locked_or_damaged > 1:
        red = True
        ctx.add(
            "R-WHEELS-MANY",
            ReasonEffect.RED,
            f"{c.wheels_locked_or_damaged} wheels are locked or damaged; the rig cannot move more than one.",
        )
    if red:
        return
    if c.wheels_locked_or_damaged == 1 or c.tires_intact < 4:
        bits = []
        if c.tires_intact < 4:
            bits.append(f"only {c.tires_intact} of 4 tires are intact")
        if c.wheels_locked_or_damaged == 1:
            bits.append("one wheel is locked or damaged")
        ctx.add(
            "R-GRIP-PARTIAL",
            ReasonEffect.YELLOW,
            "Grip is reduced: " + " and ".join(bits) + ".",
            confirm="on-scene supervisor or a second unit: confirm the rig can grip the remaining tires",
        )
    else:
        ctx.add("R-GRIP-OK", ReasonEffect.GREEN, "All 4 tires are intact and no wheel is locked or damaged.")


# ---------------------------------------------------------------- 3. Damage and neutral


def _rule_damage(ctx: _Ctx) -> None:
    c = ctx.crash
    fired = False
    if c.orientation != Orientation.UPRIGHT:
        fired = True
        ctx.add("R-ORIENTATION", ReasonEffect.RED, f"Vehicle is {c.orientation.value.replace('_', ' ')}, not upright.")
    if c.fire_or_fuel_leak:
        fired = True
        ctx.add("R-FIRE", ReasonEffect.RED, "Fire or fuel leak reported at the vehicle.")
    if c.axle_damage:
        fired = True
        ctx.add("R-AXLE", ReasonEffect.RED, "Axle damage reported; the vehicle cannot be rolled safely.")
    if not fired:
        ctx.add("R-STRUCTURE-OK", ReasonEffect.GREEN, "Vehicle is upright with no fire, fuel leak or axle damage.")
    if c.airbags_deployed:
        ctx.add(
            "R-AIRBAGS",
            ReasonEffect.ADVISORY,
            "Airbags deployed, so crash severity may be higher than it looks. Advisory only; it does not change the verdict.",
        )
    if ctx.inp.severity.level == Severity.HIGH:
        ctx.add(
            "R-SEVERITY-HIGH",
            ReasonEffect.ADVISORY,
            "Incident severity is high (operator-entered). Advisory only; it does not change the verdict.",
        )


def _rule_neutral(ctx: _Ctx) -> None:
    status = ctx.crash.neutral_status
    if status == NeutralStatus.CANNOT:
        ctx.add(
            "R-NEUTRAL-NO",
            ReasonEffect.RED,
            "Vehicle cannot be put into neutral (operator-entered), so it cannot be moved with the rig.",
        )
    elif status == NeutralStatus.UNCONFIRMED:
        ctx.add(
            "R-NEUTRAL-UNCONFIRMED",
            ReasonEffect.YELLOW,
            "Neutral has not been confirmed (operator-entered): nobody has tried yet, or the shifter is unresponsive.",
            confirm="on-scene supervisor: attempt to put the vehicle in neutral",
        )
    else:
        how = {
            NeutralStatus.IN_NEUTRAL: "is already in neutral",
            NeutralStatus.CAN_BE_SHIFTED: "can be shifted into neutral",
            NeutralStatus.CAN_BE_FORCED: "can be forced into neutral",
        }[status]
        ctx.add("R-NEUTRAL-OK", ReasonEffect.GREEN, f"Vehicle {how} (operator-entered), so it can roll.")


# ---------------------------------------------------------------- 4. Scene


def _rule_scene(ctx: _Ctx) -> None:
    s = ctx.inp.scene
    if not s.shoulder_available:
        ctx.add(
            "R-SHOULDER-NONE",
            ReasonEffect.YELLOW,
            "No shoulder is available, so there is no obvious safe place to move the vehicle.",
            confirm="on-scene supervisor: designate a safe place to move the vehicle",
        )
    elif not s.shoulder_width_ok:
        ctx.add(
            "R-SHOULDER-NARROW",
            ReasonEffect.YELLOW,
            "The shoulder is too narrow to park the vehicle clear of traffic.",
            confirm="on-scene supervisor: confirm the shoulder is safe to use",
        )
    else:
        ctx.add("R-SHOULDER-OK", ReasonEffect.GREEN, "A shoulder wide enough to park the vehicle is available.")
    if s.grade_or_curve and s.live_traffic_risk in (LiveTrafficRisk.MEDIUM, LiveTrafficRisk.HIGH):
        ctx.add(
            "R-GRADE-TRAFFIC",
            ReasonEffect.ADVISORY,
            f"The scene is on a grade or curve with {s.live_traffic_risk.value} live-traffic risk "
            f"({s.live_traffic_risk_provenance.value}). Advisory only; it does not change the verdict.",
        )


# ---------------------------------------------------------------- outputs


def wrecker_class_for(vehicle_class: VehicleClass) -> WreckerClass:
    return WreckerClass.HEAVY_DUTY if vehicle_class in HEAVY_WRECKER_CLASSES else WreckerClass.LIGHT_DUTY


def wrecker_eta_minutes(wrecker_class: WreckerClass, assumptions: Mapping[str, Assumption]) -> tuple[float, list[str]]:
    """Dispatch delay plus travel time (distance / speed). A simple estimate, not a routing model."""
    delay_key = f"wrecker.{wrecker_class.value}.dispatch_delay_minutes"
    distance_key = f"wrecker.{wrecker_class.value}.distance_miles"
    speed_key = "wrecker.avg_response_speed_mph"
    eta = _num(assumptions, delay_key) + _num(assumptions, distance_key) / _num(assumptions, speed_key) * 60.0
    return eta, [delay_key, distance_key, speed_key]


def _clearance(assumptions: Mapping[str, Assumption], with_confirmation: bool) -> tuple[MinutesEstimate, list[str]]:
    point = _num(assumptions, "clearance.compatible_vehicle_minutes_point")
    low, high = _range(assumptions, "clearance.compatible_vehicle_minutes_range")
    keys = ["clearance.compatible_vehicle_minutes_point", "clearance.compatible_vehicle_minutes_range"]
    if with_confirmation:
        d_low, d_high = _range(assumptions, "clearance.supervisor_confirmation_delay_minutes_range")
        point, low, high = point + (d_low + d_high) / 2, low + d_low, high + d_high
        keys.append("clearance.supervisor_confirmation_delay_minutes_range")
    return MinutesEstimate(point=round(point, 1), low=round(low, 1), high=round(high, 1)), keys


def evaluate(
    inp: EvaluationInput,
    unit: UnitProfile,
    assumptions: Mapping[str, Assumption],
    specs: VehicleSpecs,
) -> Verdict:
    """Evaluate one disabled vehicle against one unit. Pure: same inputs, same verdict."""
    ctx = _Ctx(inp=inp, unit=unit, assumptions=assumptions, specs=specs)
    _rule_class(ctx)
    _rule_weight(ctx)
    _rule_dimensions(ctx)
    _rule_grip(ctx)
    _rule_damage(ctx)
    _rule_neutral(ctx)
    _rule_scene(ctx)

    # Stable sort: reasons always read in RULE_IDS order, even when one rule function emits several ids.
    ctx.findings.sort(key=lambda f: RULE_IDS.index(f.reason.rule_id))
    reasons = [f.reason for f in ctx.findings]
    effects = {r.effect for r in reasons}
    used: list[str] = [k for r in reasons for k in r.assumption_keys]

    if ReasonEffect.RED in effects:
        wrecker_class = wrecker_class_for(inp.vehicle.vehicle_class)
        eta, eta_keys = wrecker_eta_minutes(wrecker_class, assumptions)
        return Verdict(
            status=VerdictStatus.RED,
            reasons=reasons,
            wrecker=WreckerRecommendation(wrecker_class=wrecker_class, eta_minutes=round(eta, 1)),
            assumptions_used=list(dict.fromkeys([*used, *eta_keys])),
        )

    if ReasonEffect.YELLOW in effects:
        clearance, clearance_keys = _clearance(assumptions, with_confirmation=True)
        confirmations = list(dict.fromkeys(f.confirm for f in ctx.findings if f.confirm))
        return Verdict(
            status=VerdictStatus.YELLOW,
            reasons=reasons,
            estimated_clearance_minutes=clearance,
            confirmation_required_from="; ".join(confirmations),
            assumptions_used=list(dict.fromkeys([*used, *clearance_keys])),
        )

    clearance, clearance_keys = _clearance(assumptions, with_confirmation=False)
    return Verdict(
        status=VerdictStatus.GREEN,
        reasons=reasons,
        estimated_clearance_minutes=clearance,
        assumptions_used=list(dict.fromkeys([*used, *clearance_keys])),
    )


def evaluate_with_config(inp: EvaluationInput, config: ConfigStore) -> Verdict:
    """Look up the unit and current assumptions, so edits to config/ apply on the next call."""
    try:
        unit = config.fleet[inp.unit_id]
    except KeyError:
        raise UnknownUnitError(inp.unit_id) from None
    return evaluate(inp, unit, config.assumptions, config.vehicle_specs)
