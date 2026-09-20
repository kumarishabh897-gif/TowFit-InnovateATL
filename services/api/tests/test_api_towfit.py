"""POST /v1/towfit/evaluate: the verdict is computed from the submitted fields and logged as a Decision Record."""

import json

import pytest
from sqlmodel import select

from app.models import DISCLAIMER, DecisionRecord, EvaluationInput
from tests.conftest import edit, load_scenario


def load_via_api(api, scenario_id: str) -> EvaluationInput:
    response = api.client.post(f"/v1/scenarios/{scenario_id}/load")
    assert response.status_code == 200
    return EvaluationInput.model_validate(response.json()["input"])


@pytest.mark.parametrize(
    ("scenario_id", "status", "action"),
    [
        ("01_green_accord", "GREEN", "deploy"),
        ("02_red_box_truck", "RED", "dispatch_wrecker"),
        ("03_yellow_pickup", "YELLOW", "wait_for_confirmation"),
    ],
)
def test_each_scenario_runs_end_to_end_through_the_api(api, scenario_id, status, action):
    response = api.evaluate(load_via_api(api, scenario_id))
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["status"] == status
    assert body["recommended_action"] == action
    assert body["verdict"]["disclaimer"] == DISCLAIMER
    assert body["verdict"]["reasons"]
    assert isinstance(body["decision_id"], int)


def test_response_lists_every_unvalidated_number_the_verdict_used(api):
    body = api.evaluate(load_scenario("01_green_accord")).json()
    used = {u["key"]: u for u in body["assumptions_used"]}
    capacity = used["unit.patrol_42.rig_capacity_lb"]
    assert capacity["kind"] == "assumption" and capacity["editable"] is True
    assert capacity["value"] == 6000 and capacity["status"] == "PLACEHOLDER" and capacity["provenance"] == "ASSUMED"
    assert used["vehicle_specs.class_defaults.passenger_car"]["kind"] == "class_default"
    assert body["unvalidated_count"] == len(body["assumptions_used"]) > 0
    assert all(u["source"] and u["status"] for u in body["assumptions_used"])


def test_assumed_incident_weights_are_reported_as_inputs(api):
    used = {u["key"]: u for u in api.evaluate(load_scenario("02_red_box_truck")).json()["assumptions_used"]}
    assert used["input.vehicle.curb_weight"]["kind"] == "input" and used["input.vehicle.curb_weight"]["value"] == 8000
    assert used["input.vehicle.load_weight"]["provenance"] == "ASSUMED"
    assert used["input.vehicle.load_weight"]["editable"] is False


def test_red_response_carries_a_wrecker_and_no_clearance_estimate(api):
    verdict = api.evaluate(load_scenario("02_red_box_truck")).json()["verdict"]
    assert verdict["wrecker"] == {"wrecker_class": "heavy_duty", "eta_minutes": 32.0}
    assert verdict["estimated_clearance_minutes"] is None


def test_decision_record_stores_inputs_verdict_rules_and_assumptions(api):
    inp = load_scenario("03_yellow_pickup")
    body = api.evaluate(inp).json()
    with api.session() as s:
        record = s.get(DecisionRecord, body["decision_id"])
        assert record.unit_id == "PATROL-42" and record.verdict == "YELLOW"
        assert record.vehicle_summary == "2022 Ford F-150 SuperCrew 4x4"
        assert record.loaded_scenario_id == "03_yellow_pickup"
        assert EvaluationInput.model_validate_json(record.inputs_json) == inp
        assert json.loads(record.verdict_json) == body["verdict"]
        assert [r["rule_id"] for r in json.loads(record.reasons_json)] == [r["rule_id"] for r in body["verdict"]["reasons"]]
        fired = json.loads(record.rules_fired_json)
        assert {"rule_id": "R-NEUTRAL-UNCONFIRMED", "effect": "YELLOW"} in fired
        assert {"rule_id": "R-AIRBAGS", "effect": "ADVISORY"} in fired
        snapshot = {u["key"]: u for u in json.loads(record.assumptions_json)}
        assert snapshot["unit.patrol_42.rig_capacity_lb"]["value"] == 6000
        assert record.disclaimer == DISCLAIMER
        assert record.created_at is not None


def test_every_evaluation_is_logged_including_repeats(api):
    inp = load_scenario("01_green_accord")
    ids = [api.evaluate(inp).json()["decision_id"] for _ in range(3)]
    assert len(set(ids)) == 3
    with api.session() as s:
        assert len(s.exec(select(DecisionRecord)).all()) == 3


def test_unknown_unit_is_404_and_logs_nothing(api):
    response = api.evaluate(edit(load_scenario("01_green_accord"), unit_id="PATROL-99"))
    assert response.status_code == 404 and "PATROL-99" in response.json()["detail"]
    with api.session() as s:
        assert s.exec(select(DecisionRecord)).all() == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["crash"].update(tires_intact=9),
        lambda d: d["crash"].pop("neutral_status"),
        lambda d: d["crash"].update(neutral_status="maybe"),
        lambda d: d["scene"].update(lanes_blocked=99),
        lambda d: d["vehicle"].update(vehicle_class="hovercraft"),
        lambda d: d["vehicle"].update(estimated_curb_weight_lb=-5),
        lambda d: d.pop("severity"),
    ],
)
def test_invalid_bodies_are_rejected_and_never_guessed_at(api, mutate):
    data = load_scenario("01_green_accord").model_dump(mode="json")
    mutate(data)
    assert api.client.post("/v1/towfit/evaluate", json=data).status_code == 422
    with api.session() as s:
        assert s.exec(select(DecisionRecord)).all() == []


def test_judge_edits_one_field_at_a_time_and_the_verdict_follows(api):
    """The live rehearsal: start at the YELLOW scenario, change one input, watch the verdict change."""
    inp = load_via_api(api, "03_yellow_pickup")
    statuses = []
    for step in (
        inp,
        edit(inp, crash={"neutral_status": "can_be_forced"}),  # fixes one YELLOW reason
        edit(inp, crash={"neutral_status": "can_be_forced"}, scene={"shoulder_width_ok": True}),  # fixes both
        edit(inp, crash={"neutral_status": "can_be_forced"}, scene={"shoulder_width_ok": True}, vehicle={"estimated_curb_weight_lb": 6100}),
        edit(inp, crash={"fire_or_fuel_leak": True}),
    ):
        statuses.append(api.evaluate(step).json()["verdict"]["status"])
    assert statuses == ["YELLOW", "YELLOW", "GREEN", "RED", "RED"]


def test_loading_a_scenario_label_does_not_lock_in_its_verdict(api):
    """A form loaded from the GREEN scenario but edited into a box truck is RED, whatever the label says."""
    inp = edit(load_via_api(api, "01_green_accord"), vehicle={"vehicle_class": "box_truck"})
    assert inp.loaded_scenario_id == "01_green_accord"
    assert api.evaluate(inp).json()["verdict"]["status"] == "RED"


def test_a_second_unit_changes_the_verdict_for_the_same_vehicle(api):
    pickup = load_scenario("03_yellow_pickup")
    assert api.evaluate(pickup).json()["verdict"]["status"] == "YELLOW"
    assert api.evaluate(edit(pickup, unit_id="PATROL-17")).json()["verdict"]["status"] == "RED"
