"""Property tests for the rule engine (brief section 6.4 and section 10).

Random inputs, real config. These check what must hold for *every* input, which example tests cannot.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.config_loader import REPO_ROOT, ConfigStore
from app.engine import RULE_IDS, evaluate_with_config
from app.models import EvaluationInput, ReasonEffect, VerdictStatus
from tests.conftest import edit
from tests.test_engine import RED_TRIGGERS, YELLOW_TRIGGERS

CONFIG = ConfigStore(REPO_ROOT / "config")
SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])

CLASSES = ["passenger_car", "suv", "pickup", "van", "box_truck", "tractor_trailer", "bus", "motorcycle", "unknown"]
COMPATIBLE = ["passenger_car", "suv", "pickup", "van"]
NEUTRAL_ALL = ["in_neutral", "can_be_shifted", "can_be_forced", "unconfirmed", "cannot"]
NEUTRAL_MOVABLE = ["in_neutral", "can_be_shifted", "can_be_forced"]


def _optional(strategy):
    return st.one_of(st.none(), strategy)


@st.composite
def any_input(draw) -> EvaluationInput:
    """Anything the API would accept: every field varies, including the hard-RED ones."""
    total = draw(st.integers(1, 5))
    return EvaluationInput.model_validate(
        {
            "unit_id": draw(st.sampled_from(["PATROL-42", "PATROL-17"])),
            "loaded_scenario_id": draw(_optional(st.text(min_size=1, max_size=8))),
            "vehicle": {
                "make_model": "random",
                "vehicle_class": draw(st.sampled_from(CLASSES)),
                "estimated_curb_weight_lb": draw(st.floats(500, 20000)),
                "curb_weight_provenance": draw(st.sampled_from(["ESTIMATED", "ASSUMED"])),
                "estimated_load_weight_lb": draw(_optional(st.floats(0, 8000))),
                "tire_width_mm": draw(_optional(st.floats(100, 450))),
                "ground_clearance_mm": draw(_optional(st.floats(40, 400))),
                "wheelbase_mm": draw(_optional(st.floats(1000, 7000))),
            },
            "crash": {
                "tires_intact": draw(st.integers(0, 4)),
                "wheels_locked_or_damaged": draw(st.integers(0, 4)),
                "axle_damage": draw(st.booleans()),
                "airbags_deployed": draw(st.booleans()),
                "orientation": draw(st.sampled_from(["upright", "on_side", "roof"])),
                "fire_or_fuel_leak": draw(st.booleans()),
                "neutral_status": draw(st.sampled_from(NEUTRAL_ALL)),
            },
            "scene": {
                "lanes_total": total,
                "lanes_blocked": draw(st.integers(0, total)),
                "shoulder_available": draw(st.booleans()),
                "shoulder_width_ok": draw(st.booleans()),
                "grade_or_curve": draw(st.booleans()),
                "live_traffic_risk": draw(st.sampled_from(["low", "medium", "high"])),
            },
            "severity": {"level": draw(st.sampled_from(["low", "medium", "high"]))},
        }
    )


@st.composite
def neutral_capable_clean_input(draw) -> EvaluationInput:
    """No hard-RED trigger, can be put in neutral, a safe place to go, all tires good.

    Airbags, severity, traffic, grade and weight (up to the rig's limit) are free to vary: none may change GREEN.
    """
    unit = draw(st.sampled_from(["PATROL-42", "PATROL-17"]))
    capacity = CONFIG.fleet[unit].rig_capacity_lb
    total = draw(st.integers(1, 5))
    return EvaluationInput.model_validate(
        {
            "unit_id": unit,
            "vehicle": {
                "make_model": "random",
                "vehicle_class": draw(st.sampled_from(COMPATIBLE)),
                "estimated_curb_weight_lb": draw(st.floats(500, capacity)),
                "tire_width_mm": draw(_optional(st.floats(155, 315))),
                "ground_clearance_mm": draw(_optional(st.floats(90, 400))),
                "wheelbase_mm": draw(_optional(st.floats(1500, 4000))),
            },
            "crash": {
                "tires_intact": 4,
                "wheels_locked_or_damaged": 0,
                "axle_damage": False,
                "airbags_deployed": draw(st.booleans()),
                "orientation": "upright",
                "fire_or_fuel_leak": False,
                "neutral_status": draw(st.sampled_from(NEUTRAL_MOVABLE)),
            },
            "scene": {
                "lanes_total": total,
                "lanes_blocked": draw(st.integers(0, total)),
                "shoulder_available": True,
                "shoulder_width_ok": True,
                "grade_or_curve": draw(st.booleans()),
                "live_traffic_risk": draw(st.sampled_from(["low", "medium", "high"])),
            },
            "severity": {"level": draw(st.sampled_from(["low", "medium", "high"]))},
        }
    )


def run(inp: EvaluationInput):
    return evaluate_with_config(inp, CONFIG)


def _rule_ids(verdict, effect=None):
    return [r.rule_id for r in verdict.reasons if effect is None or r.effect == effect]


# Hard-RED mutations that are safe to apply to any input (they only touch the field being made bad).
# The weight one reads the unit's capacity, so it works on both units.
def _make_overweight(inp: EvaluationInput) -> EvaluationInput:
    capacity = CONFIG.fleet[inp.unit_id].rig_capacity_lb
    return edit(inp, vehicle={"estimated_curb_weight_lb": capacity + 1, "estimated_load_weight_lb": None})


RED_MUTATIONS = {name: mutate for name, (mutate, _) in RED_TRIGGERS.items() if name != "over_capacity"}
RED_MUTATIONS["over_capacity"] = _make_overweight
EXPECTED_RULE = {name: rule for name, (_, rule) in RED_TRIGGERS.items()}
red_mutation_names = st.sampled_from(sorted(RED_MUTATIONS))


@SETTINGS
@given(neutral_capable_clean_input())
def test_neutral_capable_with_no_hard_red_and_a_safe_place_is_always_green(inp):
    """The product rule: a car that can be put or forced into neutral is a GREEN case."""
    verdict = run(inp)
    assert verdict.status == VerdictStatus.GREEN, [(r.rule_id, r.text) for r in verdict.reasons]


@SETTINGS
@given(neutral_capable_clean_input(), red_mutation_names)
def test_adding_any_hard_red_condition_to_a_green_input_never_gives_green_or_yellow(inp, name):
    assert run(inp).status == VerdictStatus.GREEN
    verdict = run(RED_MUTATIONS[name](inp))
    assert verdict.status == VerdictStatus.RED
    assert EXPECTED_RULE[name] in _rule_ids(verdict, ReasonEffect.RED)


@SETTINGS
@given(any_input(), red_mutation_names)
def test_a_hard_red_condition_is_red_whatever_else_is_true(inp, name):
    verdict = run(RED_MUTATIONS[name](inp))
    assert verdict.status == VerdictStatus.RED
    assert EXPECTED_RULE[name] in _rule_ids(verdict, ReasonEffect.RED)


@SETTINGS
@given(neutral_capable_clean_input(), st.sampled_from(sorted(YELLOW_TRIGGERS)))
def test_a_yellow_condition_on_a_green_input_is_yellow_never_green_or_red(inp, name):
    mutate, expected_rule = YELLOW_TRIGGERS[name]
    verdict = run(mutate(inp))
    assert verdict.status == VerdictStatus.YELLOW
    assert expected_rule in _rule_ids(verdict, ReasonEffect.YELLOW)


@SETTINGS
@given(any_input())
def test_every_verdict_has_reasons_and_a_shape_that_matches_its_status(inp):
    verdict = run(inp)  # Verdict's own validator already rejects an empty reason list or a mismatched shape
    assert verdict.reasons
    effects = {r.effect for r in verdict.reasons}
    if verdict.status == VerdictStatus.RED:
        assert ReasonEffect.RED in effects
        assert verdict.wrecker is not None and verdict.wrecker.eta_minutes > 0
        assert verdict.estimated_clearance_minutes is None
    elif verdict.status == VerdictStatus.YELLOW:
        assert ReasonEffect.RED not in effects and ReasonEffect.YELLOW in effects
        assert verdict.confirmation_required_from
        assert verdict.estimated_clearance_minutes is not None and verdict.wrecker is None
    else:
        assert not effects & {ReasonEffect.RED, ReasonEffect.YELLOW}
        assert verdict.estimated_clearance_minutes is not None
        assert verdict.wrecker is None and verdict.confirmation_required_from is None
    minutes = verdict.estimated_clearance_minutes
    if minutes:
        assert 0 < minutes.low <= minutes.point <= minutes.high


@SETTINGS
@given(any_input())
def test_reasons_are_in_declared_order_and_are_known_rules(inp):
    positions = [RULE_IDS.index(r.rule_id) for r in run(inp).reasons]
    assert positions == sorted(positions)


@SETTINGS
@given(any_input())
def test_status_is_exactly_the_worst_reason_present(inp):
    verdict = run(inp)
    effects = {r.effect for r in verdict.reasons}
    expected = (
        VerdictStatus.RED if ReasonEffect.RED in effects
        else VerdictStatus.YELLOW if ReasonEffect.YELLOW in effects
        else VerdictStatus.GREEN
    )
    assert verdict.status == expected


@SETTINGS
@given(any_input())
def test_same_input_same_verdict_and_the_loaded_scenario_label_is_irrelevant(inp):
    assert run(inp) == run(inp)
    assert run(inp) == run(edit(inp, loaded_scenario_id="anything"))
