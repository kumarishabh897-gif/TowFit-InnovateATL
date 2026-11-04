"""GET / PUT /v1/assumptions: live edits to assumptions.yaml."""

import pytest

from tests.conftest import load_scenario

CAPACITY = "unit.patrol_42.rig_capacity_lb"


def put(api, *updates: dict):
    return api.client.put("/v1/assumptions", json={"updates": list(updates)})


def file_text(api) -> str:
    return (api.config_dir / "assumptions.yaml").read_text()


def verdict_status(api, scenario: str) -> str:
    return api.evaluate(load_scenario(scenario)).json()["verdict"]["status"]


def test_read_lists_every_assumption_with_the_unvalidated_count(api):
    body = api.client.get("/v1/assumptions").json()
    assert body["total"] == 18 == len(body["assumptions"])
    assert body["unvalidated_count"] == 18
    entry = next(a for a in body["assumptions"] if a["key"] == CAPACITY)
    assert entry["value"] == 6000 and entry["status"] == "PLACEHOLDER" and entry["unit"] == "lb" and entry["source"]


def test_an_edit_applies_to_the_next_evaluation_without_a_restart(api):
    assert verdict_status(api, "03_yellow_pickup") == "YELLOW"
    response = put(api, {"key": CAPACITY, "value": 5000})
    assert response.status_code == 200
    assert next(a for a in response.json()["assumptions"] if a["key"] == CAPACITY)["value"] == 5000
    assert verdict_status(api, "03_yellow_pickup") == "RED"
    put(api, {"key": CAPACITY, "value": 8000})
    assert verdict_status(api, "02_red_box_truck") == "RED"  # still RED: class is incompatible whatever the capacity
    assert verdict_status(api, "03_yellow_pickup") == "YELLOW"


def test_the_fleet_endpoint_reflects_an_edit(api):
    put(api, {"key": CAPACITY, "value": 5500})
    unit = next(u for u in api.client.get("/v1/fleet").json() if u["unit"]["unit_id"] == "PATROL-42")
    assert unit["unit"]["rig_capacity_lb"] == 5500
    assert unit["rig_assumptions"]["rig_capacity_lb"]["value"] == 5500


def test_an_edit_changes_only_the_edited_line_and_keeps_every_comment(api):
    before = file_text(api).splitlines()
    put(api, {"key": CAPACITY, "value": 7000})
    after = file_text(api).splitlines()
    assert len(before) == len(after)
    changed = [(b, a) for b, a in zip(before, after) if b != a]
    assert changed == [("    value: 6000", "    value: 7000")]
    assert after[0].startswith("# ClearanceOS assumptions registry")
    assert sum(1 for line in after if line.lstrip().startswith("#")) == sum(1 for line in before if line.lstrip().startswith("#"))


def test_an_edit_that_changes_nothing_leaves_the_file_byte_identical(api):
    before = file_text(api)
    assert put(api, {"key": CAPACITY, "value": 6000}).status_code == 200
    assert file_text(api) == before


def test_ranges_are_edited_as_ranges(api):
    put(api, {"key": "clearance.compatible_vehicle_minutes_range", "value": [2, 9]})
    assert "value: [2, 9]" in file_text(api)
    clearance = api.evaluate(load_scenario("01_green_accord")).json()["verdict"]["estimated_clearance_minutes"]
    assert (clearance["low"], clearance["high"]) == (2, 9)


def test_marking_an_assumption_validated_lowers_the_unvalidated_count(api):
    before = api.evaluate(load_scenario("01_green_accord")).json()["unvalidated_count"]
    body = put(api, {"key": CAPACITY, "status": "VALIDATED", "source": "CAD team, rated load test 2026-09-01", "note": "Confirmed"}).json()
    assert body["unvalidated_count"] == 17
    entry = next(a for a in body["assumptions"] if a["key"] == CAPACITY)
    assert (entry["status"], entry["source"], entry["note"]) == ("VALIDATED", "CAD team, rated load test 2026-09-01", "Confirmed")
    assert api.evaluate(load_scenario("01_green_accord")).json()["unvalidated_count"] == before - 1
    assert api.client.get("/health").json()["unvalidated_assumptions"] == 17


def test_several_edits_in_one_request_apply_together(api):
    put(api, {"key": CAPACITY, "value": 5200}, {"key": "wrecker.avg_response_speed_mph", "value": 30})
    assert api.evaluate(load_scenario("02_red_box_truck")).json()["verdict"]["wrecker"]["eta_minutes"] == 42.0  # 12 + 15/30*60


def _unchanged_after(api, *updates, status):
    before = file_text(api)
    response = put(api, *updates)
    assert response.status_code == status, response.text
    assert file_text(api) == before
    assert not list(api.config_dir.glob(".assumptions*"))  # no temp file left behind
    return response


def test_an_unknown_key_is_404_and_nothing_changes(api):
    response = _unchanged_after(api, {"key": CAPACITY, "value": 5000}, {"key": "no.such.key", "value": 1}, status=404)
    assert "no.such.key" in response.json()["detail"]
    assert verdict_status(api, "03_yellow_pickup") == "YELLOW"  # the valid half of the request was not applied either


@pytest.mark.parametrize(
    "update",
    [
        {"key": CAPACITY, "value": [1, 2]},  # a number cannot become a range
        {"key": "clearance.compatible_vehicle_minutes_range", "value": 4},  # and a range cannot become a number
        {"key": "clearance.compatible_vehicle_minutes_range", "value": [9, 2]},  # low above high
        {"key": "clearance.compatible_vehicle_minutes_range", "value": [1, 2, 3]},
        {"key": "wrecker.avg_response_speed_mph", "value": 0},  # the engine divides by this
        {"key": "wrecker.avg_response_speed_mph", "value": -10},
        {"key": CAPACITY, "value": 0},
        {"key": CAPACITY, "value": -100},
        {"key": "engine.weight_advisory_fraction", "value": 1.5},
        {"key": "engine.weight_advisory_fraction", "value": 0},
        {"key": "backup.minutes_per_mile_of_backup", "value": 0},
    ],
)
def test_values_that_would_break_the_engine_are_rejected_and_the_file_is_untouched(api, update):
    _unchanged_after(api, update, status=422)
    assert verdict_status(api, "01_green_accord") == "GREEN"  # engine still works


@pytest.mark.parametrize(
    "body",
    [
        {"updates": []},
        {"updates": [{"key": CAPACITY}]},  # nothing to change
        {"updates": [{"key": CAPACITY, "status": "SORTA_VALID"}]},
        {"updates": [{"key": CAPACITY, "value": "lots"}]},
        {},
    ],
)
def test_malformed_requests_are_422(api, body):
    before = file_text(api)
    assert api.client.put("/v1/assumptions", json=body).status_code == 422
    assert file_text(api) == before


def test_a_hand_edit_that_breaks_the_file_is_reported_not_silently_ignored(api):
    (api.config_dir / "assumptions.yaml").write_text("assumptions: [oops]\n")
    response = api.evaluate(load_scenario("01_green_accord"))
    assert response.status_code == 500 and "Configuration is invalid" in response.json()["detail"]


def test_a_read_only_deployment_refuses_edits_with_a_clear_message(api, monkeypatch):
    monkeypatch.setenv("TOWFIT_READ_ONLY_CONFIG", "1")
    before = file_text(api)
    response = put(api, {"key": CAPACITY, "value": 5000})
    assert response.status_code == 403 and "read-only" in response.json()["detail"]
    assert file_text(api) == before
    assert api.client.get("/v1/assumptions").status_code == 200  # reading still works
