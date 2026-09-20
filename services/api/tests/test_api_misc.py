"""Fleet, vehicle specs, scenarios, health, CORS and the OpenAPI schema."""

import json

from app.config_loader import REPO_ROOT
from scripts.export_openapi import OUTPUT, build_schema, render
from tests.conftest import load_scenario


def _keys(value) -> set[str]:
    """Every dict key anywhere inside a JSON value."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_health(api):
    assert api.client.get("/health").json() == {
        "status": "ok", "units": 2, "vehicle_models": 4, "assumptions": 18, "unvalidated_assumptions": 18,
    }


def test_fleet_lists_units_with_the_status_behind_every_rig_number(api):
    fleet = {u["unit"]["unit_id"]: u for u in api.client.get("/v1/fleet").json()}
    assert set(fleet) == {"PATROL-42", "PATROL-17"}
    p42 = fleet["PATROL-42"]
    assert p42["unit"]["rig_capacity_lb"] == 6000 and fleet["PATROL-17"]["unit"]["rig_capacity_lb"] == 5000
    assert p42["operational_status"] == "available" and p42["operational_status_provenance"] == "SIM"
    assert set(p42["rig_assumptions"]) == {
        "rig_capacity_lb", "rig_tire_width_range_mm", "rig_min_ground_clearance_mm", "rig_max_wheelbase_mm",
    }
    for use in p42["rig_assumptions"].values():
        assert use["status"] == "PLACEHOLDER" and use["editable"] is True and use["key"].startswith("unit.patrol_42.")
    assert "box_truck" not in p42["unit"]["compatible_vehicle_classes"]


def test_vehicle_specs_label_every_row_with_a_source(api):
    body = api.client.get("/v1/vehicle-specs").json()
    assert len(body["models"]) == 4
    for row in body["models"]:
        assert row["source"] and row["provenance"] == "ESTIMATED" and row["status"] in {"PLACEHOLDER", "SOURCED", "VALIDATED"}
    assert body["class_defaults_meta"]["provenance"] == "ASSUMED"
    assert "unknown" not in body["class_defaults"]


def test_scenarios_are_listed_and_loadable(api):
    listed = api.client.get("/v1/scenarios").json()
    assert [s["id"] for s in listed] == ["01_green_accord", "02_red_box_truck", "03_yellow_pickup"]
    assert all(s["title"] and s["description"] for s in listed)


def test_loading_a_scenario_returns_its_inputs_and_never_a_verdict(api):
    for scenario in api.client.get("/v1/scenarios").json():
        body = api.client.post(f"/v1/scenarios/{scenario['id']}/load").json()
        assert set(body) == {"id", "title", "description", "input"}
        assert not _keys(body) & {
            "verdict", "status", "reasons", "wrecker", "estimated_clearance_minutes", "recommended_action",
            "confirmation_required_from",
        }
    body = api.client.post("/v1/scenarios/01_green_accord/load").json()
    assert body["input"] == json.loads(load_scenario("01_green_accord").model_dump_json())


def test_loading_a_scenario_logs_nothing(api):
    api.client.post("/v1/scenarios/01_green_accord/load")
    assert api.client.get("/v1/decisions").json()["total"] == 0


def test_unknown_scenario_is_404(api):
    assert api.client.post("/v1/scenarios/nope/load").status_code == 404


def test_the_web_app_origin_is_allowed_by_cors(api):
    response = api.client.options(
        "/v1/towfit/evaluate",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in api.client.options(
        "/v1/towfit/evaluate", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    ).headers


def test_the_openapi_schema_describes_every_v1_endpoint():
    paths = build_schema()["paths"]
    expected = {
        ("/v1/fleet", "get"), ("/v1/vehicle-specs", "get"), ("/v1/towfit/evaluate", "post"),
        ("/v1/decisions", "get"), ("/v1/decisions/{decision_id}", "get"), ("/v1/decisions/{decision_id}/events", "post"),
        ("/v1/assumptions", "get"), ("/v1/assumptions", "put"),
        ("/v1/scenarios", "get"), ("/v1/scenarios/{scenario_id}/load", "post"),
    }
    assert {(p, m) for p, item in paths.items() for m in item} >= expected


def test_the_committed_openapi_file_is_current():
    """Fails when the API changed but docs/openapi.json was not regenerated (run scripts/export_openapi.py)."""
    assert OUTPUT.read_text() == render(build_schema()), "docs/openapi.json is stale"
    assert OUTPUT.parent == REPO_ROOT / "docs"
