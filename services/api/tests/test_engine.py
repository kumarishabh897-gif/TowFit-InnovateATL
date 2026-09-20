"""Rule engine tests. Written first, before any endpoint or UI, so the logic is proven on its own.

Layout: every RED trigger alone, every YELLOW trigger alone, advisories that must not change a GREEN,
boundaries, combinations, unit-specific behaviour, then the three demo scenarios.
"""

import ast
import re
import shutil
from pathlib import Path

import pytest

from app.config_loader import REPO_ROOT, ConfigStore
from app.engine import RULE_IDS, UnknownUnitError, evaluate, evaluate_with_config, wrecker_eta_minutes
from app.models import DISCLAIMER, EvaluationInput, ReasonEffect, VerdictStatus, WreckerClass
from tests.conftest import edit, load_scenario

RED, YELLOW, GREEN = VerdictStatus.RED, VerdictStatus.YELLOW, VerdictStatus.GREEN


def rule_ids(verdict, effect: ReasonEffect | None = None) -> list[str]:
    return [r.rule_id for r in verdict.reasons if effect is None or r.effect == effect]


# ------------------------------------------------------------------ RED triggers, one at a time

RED_TRIGGERS = {
    "motorcycle": (lambda i: edit(i, vehicle={"vehicle_class": "motorcycle"}), "R-CLASS-EXCLUDED"),
    "bus": (lambda i: edit(i, vehicle={"vehicle_class": "bus"}), "R-CLASS-EXCLUDED"),
    "tractor_trailer": (lambda i: edit(i, vehicle={"vehicle_class": "tractor_trailer"}), "R-CLASS-EXCLUDED"),
    "box_truck_not_in_compatible_list": (lambda i: edit(i, vehicle={"vehicle_class": "box_truck"}), "R-CLASS-INCOMPATIBLE"),
    "unknown_class": (lambda i: edit(i, vehicle={"vehicle_class": "unknown"}), "R-CLASS-INCOMPATIBLE"),
    "over_capacity": (lambda i: edit(i, vehicle={"estimated_curb_weight_lb": 6001}), "R-WEIGHT-OVER"),
    "curb_plus_load_over_capacity": (
        lambda i: edit(i, vehicle={"estimated_curb_weight_lb": 4000, "estimated_load_weight_lb": 2001}),
        "R-WEIGHT-OVER",
    ),
    "on_side": (lambda i: edit(i, crash={"orientation": "on_side"}), "R-ORIENTATION"),
    "on_roof": (lambda i: edit(i, crash={"orientation": "roof"}), "R-ORIENTATION"),
    "fire_or_fuel_leak": (lambda i: edit(i, crash={"fire_or_fuel_leak": True}), "R-FIRE"),
    "axle_damage": (lambda i: edit(i, crash={"axle_damage": True}), "R-AXLE"),
    "one_tire_intact": (lambda i: edit(i, crash={"tires_intact": 1}), "R-TIRES-FEW"),
    "no_tires_intact": (lambda i: edit(i, crash={"tires_intact": 0}), "R-TIRES-FEW"),
    "two_wheels_locked": (lambda i: edit(i, crash={"wheels_locked_or_damaged": 2}), "R-WHEELS-MANY"),
    "four_wheels_locked": (lambda i: edit(i, crash={"wheels_locked_or_damaged": 4}), "R-WHEELS-MANY"),
    "tire_too_wide": (lambda i: edit(i, vehicle={"tire_width_mm": 316}), "R-DIM-TIRE-WIDTH"),
    "tire_too_narrow": (lambda i: edit(i, vehicle={"tire_width_mm": 154}), "R-DIM-TIRE-WIDTH"),
    "clearance_too_low": (lambda i: edit(i, vehicle={"ground_clearance_mm": 89}), "R-DIM-CLEARANCE"),
    "wheelbase_too_long": (lambda i: edit(i, vehicle={"wheelbase_mm": 4001}), "R-DIM-WHEELBASE"),
    "cannot_be_put_in_neutral": (lambda i: edit(i, crash={"neutral_status": "cannot"}), "R-NEUTRAL-NO"),
}


@pytest.mark.parametrize("name", RED_TRIGGERS)
def test_each_red_trigger_alone_makes_red_with_its_reason(name, green_input, run):
    mutate, expected_rule = RED_TRIGGERS[name]
    verdict = run(mutate(green_input))
    assert verdict.status == RED
    assert expected_rule in rule_ids(verdict, ReasonEffect.RED)
    assert verdict.wrecker is not None and verdict.wrecker.eta_minutes > 0


def test_red_triggers_cover_every_hard_red_rule():
    covered = {rule for _, rule in RED_TRIGGERS.values()}
    red_rules = {"R-CLASS-EXCLUDED", "R-CLASS-INCOMPATIBLE", "R-WEIGHT-OVER", "R-ORIENTATION", "R-FIRE", "R-AXLE",
                 "R-TIRES-FEW", "R-WHEELS-MANY", "R-DIM-TIRE-WIDTH", "R-DIM-CLEARANCE", "R-DIM-WHEELBASE", "R-NEUTRAL-NO"}
    assert covered == red_rules


def test_dimensions_left_blank_fall_back_to_class_typical_values(green_input, run):
    # nothing entered for a pickup: the class-typical 275 mm tire, 210 mm clearance and 3,600 mm wheelbase all fit
    inp = edit(green_input, vehicle={"vehicle_class": "pickup", "tire_width_mm": None, "wheelbase_mm": None})
    verdict = run(inp)
    assert verdict.status == GREEN
    assert "class-typical, ASSUMED" in next(r.text for r in verdict.reasons if r.rule_id == "R-DIM-OK")


# ------------------------------------------------------------------ YELLOW triggers, one at a time

YELLOW_TRIGGERS = {
    "neutral_unconfirmed": (lambda i: edit(i, crash={"neutral_status": "unconfirmed"}), "R-NEUTRAL-UNCONFIRMED"),
    "no_shoulder": (
        lambda i: edit(i, scene={"shoulder_available": False, "shoulder_width_ok": False}),
        "R-SHOULDER-NONE",
    ),
    "narrow_shoulder": (lambda i: edit(i, scene={"shoulder_width_ok": False}), "R-SHOULDER-NARROW"),
    "one_wheel_locked": (lambda i: edit(i, crash={"wheels_locked_or_damaged": 1}), "R-GRIP-PARTIAL"),
    "three_tires_intact": (lambda i: edit(i, crash={"tires_intact": 3}), "R-GRIP-PARTIAL"),
    "two_tires_intact": (lambda i: edit(i, crash={"tires_intact": 2}), "R-GRIP-PARTIAL"),
}


@pytest.mark.parametrize("name", YELLOW_TRIGGERS)
def test_each_yellow_trigger_alone_makes_yellow_with_its_reason(name, green_input, run):
    mutate, expected_rule = YELLOW_TRIGGERS[name]
    verdict = run(mutate(green_input))
    assert verdict.status == YELLOW
    assert expected_rule in rule_ids(verdict, ReasonEffect.YELLOW)
    assert verdict.confirmation_required_from
    assert verdict.estimated_clearance_minutes is not None
    assert verdict.wrecker is None


def test_yellow_names_who_must_confirm_for_every_yellow_reason(green_input, run):
    inp = edit(green_input, crash={"neutral_status": "unconfirmed"}, scene={"shoulder_width_ok": False})
    verdict = run(inp)
    assert "attempt to put the vehicle in neutral" in verdict.confirmation_required_from
    assert "shoulder" in verdict.confirmation_required_from


def test_yellow_clearance_adds_the_confirmation_delay(green_input, run):
    green = run(green_input).estimated_clearance_minutes
    yellow = run(edit(green_input, crash={"neutral_status": "unconfirmed"})).estimated_clearance_minutes
    assert (green.point, green.low, green.high) == (4, 3, 6)
    assert (yellow.point, yellow.low, yellow.high) == (7.5, 5, 11)


# ------------------------------------------------------------------ neutral drives GREEN; advisories never change it


@pytest.mark.parametrize("status", ["in_neutral", "can_be_shifted", "can_be_forced"])
def test_any_neutral_capable_status_is_green_on_a_clean_scene(status, green_input, run):
    verdict = run(edit(green_input, crash={"neutral_status": status}))
    assert verdict.status == GREEN
    assert "R-NEUTRAL-OK" in rule_ids(verdict, ReasonEffect.GREEN)


ADVISORY_TRIGGERS = {
    "airbags": (lambda i: edit(i, crash={"airbags_deployed": True}), "R-AIRBAGS"),
    "high_severity": (lambda i: edit(i, severity={"level": "high"}), "R-SEVERITY-HIGH"),
    "weight_85_percent": (lambda i: edit(i, vehicle={"estimated_curb_weight_lb": 5100}), "R-WEIGHT-MARGIN"),
    "grade_with_high_traffic": (
        lambda i: edit(i, scene={"grade_or_curve": True, "live_traffic_risk": "high"}),
        "R-GRADE-TRAFFIC",
    ),
    "grade_with_medium_traffic": (
        lambda i: edit(i, scene={"grade_or_curve": True, "live_traffic_risk": "medium"}),
        "R-GRADE-TRAFFIC",
    ),
}


@pytest.mark.parametrize("name", ADVISORY_TRIGGERS)
def test_advisory_shows_up_but_does_not_leave_green(name, green_input, run):
    mutate, expected_rule = ADVISORY_TRIGGERS[name]
    verdict = run(mutate(green_input))
    assert verdict.status == GREEN
    assert expected_rule in rule_ids(verdict, ReasonEffect.ADVISORY)


def test_all_advisories_together_still_green(green_input, run):
    inp = green_input
    for mutate, _ in ADVISORY_TRIGGERS.values():
        inp = EvaluationInput.model_validate(mutate(inp).model_dump())
    verdict = run(inp)
    assert verdict.status == GREEN
    assert set(rule_ids(verdict, ReasonEffect.ADVISORY)) == {
        "R-AIRBAGS", "R-SEVERITY-HIGH", "R-WEIGHT-MARGIN", "R-GRADE-TRAFFIC",
    }


def test_grade_alone_or_low_traffic_alone_is_not_even_an_advisory(green_input, run):
    for scene in ({"grade_or_curve": True, "live_traffic_risk": "low"}, {"grade_or_curve": False, "live_traffic_risk": "high"}):
        assert "R-GRADE-TRAFFIC" not in rule_ids(run(edit(green_input, scene=scene)))


# ------------------------------------------------------------------ boundaries


def test_weight_exactly_at_capacity_is_allowed_one_pound_over_is_red(green_input, run):
    assert run(edit(green_input, vehicle={"estimated_curb_weight_lb": 6000})).status == GREEN
    assert run(edit(green_input, vehicle={"estimated_curb_weight_lb": 6001})).status == RED


def test_advisory_margin_starts_strictly_above_80_percent(green_input, run):
    assert "R-WEIGHT-MARGIN" not in rule_ids(run(edit(green_input, vehicle={"estimated_curb_weight_lb": 4800})))
    assert "R-WEIGHT-MARGIN" in rule_ids(run(edit(green_input, vehicle={"estimated_curb_weight_lb": 4801})))


def test_dimension_limits_are_inclusive(green_input, run):
    inp = edit(green_input, vehicle={"tire_width_mm": 315, "ground_clearance_mm": 90, "wheelbase_mm": 4000})
    assert run(inp).status == GREEN
    assert run(edit(inp, vehicle={"tire_width_mm": 155})).status == GREEN


# ------------------------------------------------------------------ combinations and precedence


def test_every_red_trigger_that_applies_is_listed_not_just_the_first(green_input, run):
    inp = edit(green_input, crash={"fire_or_fuel_leak": True, "axle_damage": True, "orientation": "roof", "neutral_status": "cannot"})
    assert set(rule_ids(run(inp), ReasonEffect.RED)) == {"R-FIRE", "R-AXLE", "R-ORIENTATION", "R-NEUTRAL-NO"}


def test_red_beats_yellow_and_the_yellow_reason_is_still_shown(green_input, run):
    verdict = run(edit(green_input, crash={"fire_or_fuel_leak": True, "neutral_status": "unconfirmed"}))
    assert verdict.status == RED
    assert "R-FIRE" in rule_ids(verdict, ReasonEffect.RED)
    assert "R-NEUTRAL-UNCONFIRMED" in rule_ids(verdict, ReasonEffect.YELLOW)
    assert verdict.estimated_clearance_minutes is None


def test_neutral_never_rescues_a_red(green_input, run):
    for status in ("in_neutral", "can_be_shifted", "can_be_forced"):
        verdict = run(edit(green_input, vehicle={"vehicle_class": "bus"}, crash={"neutral_status": status}))
        assert verdict.status == RED


def test_two_bad_tires_and_one_wheel_locked_reports_both_grip_reasons(green_input, run):
    verdict = run(edit(green_input, crash={"tires_intact": 1, "wheels_locked_or_damaged": 2}))
    assert {"R-TIRES-FEW", "R-WHEELS-MANY"} <= set(rule_ids(verdict, ReasonEffect.RED))


# ------------------------------------------------------------------ reasons: always present, ordered, readable


def test_green_reasons_are_the_passing_checks_in_question_order(green_input, run):
    assert rule_ids(run(green_input)) == [
        "R-CLASS-OK", "R-WEIGHT-OK", "R-DIM-OK", "R-GRIP-OK", "R-STRUCTURE-OK", "R-NEUTRAL-OK", "R-SHOULDER-OK",
    ]


def test_reasons_follow_the_engines_declared_rule_order(green_input, run):
    inp = edit(
        green_input,
        vehicle={"vehicle_class": "box_truck", "estimated_curb_weight_lb": 8000, "estimated_load_weight_lb": 6000},
        crash={"tires_intact": 1, "fire_or_fuel_leak": True, "airbags_deployed": True, "neutral_status": "cannot"},
        scene={"shoulder_available": False, "shoulder_width_ok": False},
    )
    positions = [RULE_IDS.index(r) for r in rule_ids(run(inp))]
    assert positions == sorted(positions)


def test_every_reason_is_plain_language_naming_no_internal_ids(green_input, run):
    for mutate, _ in [*RED_TRIGGERS.values(), *YELLOW_TRIGGERS.values(), *ADVISORY_TRIGGERS.values()]:
        for reason in run(mutate(green_input)).reasons:
            assert len(reason.text) > 15
            assert not re.search(r"R-[A-Z]+-", reason.text)


def test_every_verdict_carries_the_exact_disclaimer(green_input, run):
    for mutate, _ in [*RED_TRIGGERS.values(), *YELLOW_TRIGGERS.values()]:
        assert run(mutate(green_input)).disclaimer == DISCLAIMER
    assert run(green_input).disclaimer == DISCLAIMER


def test_every_rule_id_is_reachable(green_input, run):
    seen: set[str] = set()
    for mutate, _ in [*RED_TRIGGERS.values(), *YELLOW_TRIGGERS.values(), *ADVISORY_TRIGGERS.values()]:
        seen |= set(rule_ids(run(mutate(green_input))))
    seen |= set(rule_ids(run(green_input)))
    seen |= set(rule_ids(run(load_scenario("02_red_box_truck"))))
    assert set(RULE_IDS) - seen == set()


# ------------------------------------------------------------------ unit-specific, assumption-driven, no hidden answers


def test_same_vehicle_gets_a_different_verdict_on_a_different_unit(config):
    pickup = load_scenario("03_yellow_pickup")
    assert evaluate_with_config(pickup, config).status == YELLOW  # 5,100 lb on PATROL-42 (6,000 lb rig)
    on_smaller_rig = evaluate_with_config(edit(pickup, unit_id="PATROL-17"), config)  # 5,000 lb rig
    assert on_smaller_rig.status == RED
    assert "R-WEIGHT-OVER" in rule_ids(on_smaller_rig, ReasonEffect.RED)
    assert "PATROL-17" in next(r.text for r in on_smaller_rig.reasons if r.rule_id == "R-WEIGHT-OVER")


def test_unknown_unit_is_an_error_not_a_default(config, green_input):
    with pytest.raises(UnknownUnitError):
        evaluate_with_config(edit(green_input, unit_id="PATROL-99"), config)


def test_editing_an_assumption_changes_the_next_verdict(tmp_path):
    cfg = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", cfg)
    store = ConfigStore(cfg)
    pickup = load_scenario("03_yellow_pickup")
    assert evaluate_with_config(pickup, store).status == YELLOW
    path = cfg / "assumptions.yaml"
    path.write_text(path.read_text().replace("value: 6000\n", "value: 5000\n", 1))  # PATROL-42 capacity
    assert evaluate_with_config(pickup, store).status == RED


def test_verdict_does_not_depend_on_which_scenario_was_loaded(green_input, run):
    assert run(green_input) == run(edit(green_input, loaded_scenario_id="something-else"))
    assert run(green_input) == run(edit(green_input, loaded_scenario_id=None))


def test_engine_code_never_mentions_a_scenario():
    """Guard for brief rule 3: no per-scenario answers. Checks names and string literals, not docstrings."""
    tree = ast.parse(Path(REPO_ROOT / "services/api/app/engine/towfit.py").read_text())
    docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            text = node.id
        elif isinstance(node, ast.Attribute):
            text = node.attr
        elif isinstance(node, ast.arg):
            text = node.arg
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            text = node.value
        else:
            continue
        if "scenario" in text.lower():
            offenders.append(text)
    assert offenders == []


def test_unknown_class_is_red_and_also_says_its_dimensions_could_not_be_checked(green_input, run):
    verdict = run(edit(green_input, vehicle={"vehicle_class": "unknown"}))
    assert verdict.status == RED
    assert "R-DIM-UNVERIFIED" in rule_ids(verdict, ReasonEffect.YELLOW)


def test_engine_is_deterministic(green_input, run):
    assert run(green_input) == run(green_input)


def test_unvalidated_inputs_are_reported(green_input, run):
    verdict = run(green_input)
    assert "unit.patrol_42.rig_capacity_lb" in verdict.assumptions_used  # PLACEHOLDER capacity
    assert "vehicle_specs.class_defaults.passenger_car" in verdict.assumptions_used  # clearance fell back to a class default
    assert "clearance.compatible_vehicle_minutes_point" in verdict.assumptions_used
    box = run(load_scenario("02_red_box_truck"))
    assert {"input.vehicle.curb_weight", "input.vehicle.load_weight"} <= set(box.assumptions_used)
    assert "wrecker.heavy_duty.distance_miles" in box.assumptions_used


def test_provenance_is_named_in_the_weight_reason(green_input, run):
    text = next(r.text for r in run(green_input).reasons if r.rule_id == "R-WEIGHT-OK")
    assert "ESTIMATED" in text and "3,300 lb" in text and "6,000 lb" in text
    assumed = run(edit(green_input, vehicle={"curb_weight_provenance": "ASSUMED"}))
    assert "ASSUMED" in next(r.text for r in assumed.reasons if r.rule_id == "R-WEIGHT-OK")


def test_class_typical_dimensions_are_flagged_assumed(green_input, run):
    text = next(r.text for r in run(green_input).reasons if r.rule_id == "R-DIM-OK")
    assert "ground clearance 130 mm (class-typical, ASSUMED)" in text
    assert "tire width 225 mm (entered)" in text


def test_dimensions_that_cannot_be_checked_are_yellow_not_silently_passed(config, green_input):
    specs = config.vehicle_specs
    no_defaults = specs.model_copy(update={"class_defaults": {}})
    inp = edit(green_input, vehicle={"tire_width_mm": None, "wheelbase_mm": None})
    verdict = evaluate(inp, config.fleet["PATROL-42"], config.assumptions, no_defaults)
    assert verdict.status == YELLOW
    assert "R-DIM-UNVERIFIED" in rule_ids(verdict, ReasonEffect.YELLOW)


# ------------------------------------------------------------------ wrecker and clearance numbers come from assumptions


def test_wrecker_eta_is_dispatch_delay_plus_distance_over_speed(config):
    heavy, keys = wrecker_eta_minutes(WreckerClass.HEAVY_DUTY, config.assumptions)
    assert heavy == pytest.approx(12 + 15 / 45 * 60)
    light, _ = wrecker_eta_minutes(WreckerClass.LIGHT_DUTY, config.assumptions)
    assert light == pytest.approx(5 + 8 / 45 * 60)
    assert set(keys) == {"wrecker.heavy_duty.dispatch_delay_minutes", "wrecker.heavy_duty.distance_miles", "wrecker.avg_response_speed_mph"}


def test_wrecker_eta_follows_edited_assumptions(config):
    edited = dict(config.assumptions)
    edited["wrecker.avg_response_speed_mph"] = edited["wrecker.avg_response_speed_mph"].model_copy(update={"value": 30})
    slower, _ = wrecker_eta_minutes(WreckerClass.HEAVY_DUTY, edited)
    assert slower == pytest.approx(12 + 15 / 30 * 60)


@pytest.mark.parametrize(
    ("vehicle_class", "expected"),
    [("motorcycle", WreckerClass.LIGHT_DUTY), ("box_truck", WreckerClass.HEAVY_DUTY), ("bus", WreckerClass.HEAVY_DUTY),
     ("tractor_trailer", WreckerClass.HEAVY_DUTY), ("unknown", WreckerClass.HEAVY_DUTY)],
)
def test_wrecker_class_follows_vehicle_class(vehicle_class, expected, green_input, run):
    assert run(edit(green_input, vehicle={"vehicle_class": vehicle_class})).wrecker.wrecker_class == expected


def test_a_car_that_will_not_go_into_neutral_gets_a_light_duty_wrecker(green_input, run):
    verdict = run(edit(green_input, crash={"neutral_status": "cannot"}))
    assert verdict.wrecker.wrecker_class == WreckerClass.LIGHT_DUTY
    assert verdict.wrecker.eta_minutes == pytest.approx(15.7, abs=0.05)


# ------------------------------------------------------------------ the three demo scenarios (inputs from fixtures, verdicts computed)


def test_scenario_1_green_accord(run):
    verdict = run(load_scenario("01_green_accord"))
    assert verdict.status == GREEN
    assert verdict.estimated_clearance_minutes.point == 4
    assert (verdict.estimated_clearance_minutes.low, verdict.estimated_clearance_minutes.high) == (3, 6)
    assert verdict.wrecker is None and verdict.confirmation_required_from is None
    text = " ".join(r.text for r in verdict.reasons)
    assert "3,300 lb" in text and "6,000 lb" in text and "shifted into neutral" in text


def test_scenario_2_red_box_truck_shows_both_independent_grounds(run):
    verdict = run(load_scenario("02_red_box_truck"))
    assert verdict.status == RED
    assert {"R-CLASS-INCOMPATIBLE", "R-WEIGHT-OVER"} <= set(rule_ids(verdict, ReasonEffect.RED))
    weight_text = next(r.text for r in verdict.reasons if r.rule_id == "R-WEIGHT-OVER")
    assert "14,000 lb" in weight_text and "6,000 lb" in weight_text
    assert verdict.wrecker.wrecker_class == WreckerClass.HEAVY_DUTY
    assert verdict.wrecker.eta_minutes == pytest.approx(32.0)
    assert verdict.estimated_clearance_minutes is None
    assert "R-NEUTRAL-OK" in rule_ids(verdict)  # it was in neutral, and that did not save it


def test_scenario_3_yellow_pickup_names_each_factor(run):
    verdict = run(load_scenario("03_yellow_pickup"))
    assert verdict.status == YELLOW
    assert set(rule_ids(verdict, ReasonEffect.YELLOW)) == {"R-NEUTRAL-UNCONFIRMED", "R-SHOULDER-NARROW"}
    assert set(rule_ids(verdict, ReasonEffect.ADVISORY)) == {"R-WEIGHT-MARGIN", "R-AIRBAGS", "R-GRADE-TRAFFIC"}
    assert "85%" in next(r.text for r in verdict.reasons if r.rule_id == "R-WEIGHT-MARGIN")
    assert "on-scene supervisor" in verdict.confirmation_required_from
    assert verdict.estimated_clearance_minutes is not None


def test_scenario_3_verdict_flips_only_when_the_right_fields_change(run):
    pickup = load_scenario("03_yellow_pickup")
    # one input at a time: each fix alone leaves the other YELLOW reason, so it stays YELLOW
    forced = run(edit(pickup, crash={"neutral_status": "can_be_forced"}))
    assert forced.status == YELLOW and rule_ids(forced, ReasonEffect.YELLOW) == ["R-SHOULDER-NARROW"]
    wider = run(edit(pickup, scene={"shoulder_width_ok": True}))
    assert wider.status == YELLOW and rule_ids(wider, ReasonEffect.YELLOW) == ["R-NEUTRAL-UNCONFIRMED"]
    # both fixed: GREEN, and the airbags / weight / grade advisories are still shown
    both = run(edit(pickup, crash={"neutral_status": "can_be_forced"}, scene={"shoulder_width_ok": True}))
    assert both.status == GREEN and len(rule_ids(both, ReasonEffect.ADVISORY)) == 3
    # and a hard trigger sends it to RED
    assert run(edit(pickup, crash={"neutral_status": "cannot"})).status == RED
    assert run(edit(pickup, vehicle={"estimated_curb_weight_lb": 6100})).status == RED
