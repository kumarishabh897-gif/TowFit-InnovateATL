"""GET /v1/decisions and the events that record what the operator actually did."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import edit, load_scenario


def evaluate(api, scenario: str, **edits) -> dict:
    inp = load_scenario(scenario)
    if edits:
        inp = edit(inp, **edits)
    return api.evaluate(inp).json()


@pytest.fixture()
def three_decisions(api):
    green = evaluate(api, "01_green_accord")
    red = evaluate(api, "02_red_box_truck")
    yellow = evaluate(api, "03_yellow_pickup")
    return green["decision_id"], red["decision_id"], yellow["decision_id"]


def test_log_is_newest_first_with_a_summary_per_row(api, three_decisions):
    green, red, yellow = three_decisions
    body = api.client.get("/v1/decisions").json()
    assert [d["id"] for d in body["items"]] == [yellow, red, green]
    assert body["total"] == 3
    row = body["items"][0]
    assert row["unit_id"] == "PATROL-42" and row["verdict"] == "YELLOW"
    assert row["vehicle_summary"] == "2022 Ford F-150 SuperCrew 4x4"
    assert row["recommended_action"] == "wait_for_confirmation"
    assert row["operator_action"] is None and row["followed_recommendation"] is None and row["outcome"] is None
    assert row["created_at"].endswith("Z") or "+00:00" in row["created_at"]


def test_filter_by_verdict_and_unit(api, three_decisions):
    green, red, yellow = three_decisions
    only_red = api.client.get("/v1/decisions", params={"verdict": "RED"}).json()
    assert [d["id"] for d in only_red["items"]] == [red] and only_red["total"] == 1
    evaluate(api, "03_yellow_pickup", unit_id="PATROL-17")
    p17 = api.client.get("/v1/decisions", params={"unit_id": "PATROL-17"}).json()
    assert p17["total"] == 1 and p17["items"][0]["verdict"] == "RED"
    both = api.client.get("/v1/decisions", params={"unit_id": "PATROL-42", "verdict": "GREEN"}).json()
    assert [d["id"] for d in both["items"]] == [green]


def test_filter_by_date(api, three_decisions):
    now = datetime.now(UTC)
    day = timedelta(days=1)
    fmt = lambda t: t.isoformat().replace("+00:00", "Z")  # noqa: E731
    assert api.client.get("/v1/decisions", params={"since": fmt(now - day)}).json()["total"] == 3
    assert api.client.get("/v1/decisions", params={"since": fmt(now + day)}).json()["total"] == 0
    assert api.client.get("/v1/decisions", params={"until": fmt(now + day)}).json()["total"] == 3
    assert api.client.get("/v1/decisions", params={"until": fmt(now - day)}).json()["total"] == 0
    window = {"since": fmt(now - day), "until": fmt(now + day)}
    assert api.client.get("/v1/decisions", params=window).json()["total"] == 3


def test_pagination(api, three_decisions):
    page = api.client.get("/v1/decisions", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert [d["id"] for d in page["items"]] == list(three_decisions[:2])[::-1]
    assert api.client.get("/v1/decisions", params={"limit": 0}).status_code == 422
    assert api.client.get("/v1/decisions", params={"limit": 500}).status_code == 422


def test_bad_filter_values_are_rejected(api):
    assert api.client.get("/v1/decisions", params={"verdict": "PURPLE"}).status_code == 422
    assert api.client.get("/v1/decisions", params={"since": "yesterday"}).status_code == 422


def test_empty_log_is_an_empty_list(api):
    assert api.client.get("/v1/decisions").json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


# ---------------------------------------------------------------- what the operator actually did


def post_event(api, decision_id: int, **body):
    return api.client.post(f"/v1/decisions/{decision_id}/events", json=body)


def test_operator_following_the_recommendation_is_recorded(api, three_decisions):
    green = three_decisions[0]
    response = post_event(api, green, kind="operator_action", action="deploy", note="Deployed at 14:02")
    assert response.status_code == 201
    row = response.json()
    assert row["operator_action"] == "deploy" and row["followed_recommendation"] is True


def test_operator_overriding_the_recommendation_is_recorded_as_such(api, three_decisions):
    _, red, _ = three_decisions
    row = post_event(api, red, kind="operator_action", action="deploy").json()
    assert row["recommended_action"] == "dispatch_wrecker"
    assert row["operator_action"] == "deploy" and row["followed_recommendation"] is False


def test_later_actions_and_outcomes_are_appended_and_the_latest_wins(api, three_decisions):
    yellow = three_decisions[2]
    post_event(api, yellow, kind="operator_action", action="wait_for_confirmation")
    post_event(api, yellow, kind="operator_action", action="deploy", note="Supervisor confirmed neutral")
    row = post_event(api, yellow, kind="outcome", note="Cleared in 6 minutes").json()
    assert row["operator_action"] == "deploy" and row["followed_recommendation"] is False
    assert row["outcome"] == "Cleared in 6 minutes"
    events = api.client.get(f"/v1/decisions/{yellow}").json()["events"]
    assert [(e["kind"], e["action"]) for e in events] == [
        ("operator_action", "wait_for_confirmation"),
        ("operator_action", "deploy"),
        ("outcome", None),
    ]
    assert events[1]["note"] == "Supervisor confirmed neutral"


def test_the_log_shows_the_recorded_action(api, three_decisions):
    green = three_decisions[0]
    post_event(api, green, kind="operator_action", action="deploy")
    rows = {d["id"]: d for d in api.client.get("/v1/decisions").json()["items"]}
    assert rows[green]["operator_action"] == "deploy"
    assert rows[three_decisions[1]]["operator_action"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "operator_action"},
        {"kind": "operator_action", "action": "yolo"},
        {"kind": "outcome", "note": "x", "action": "deploy"},
        {"kind": "outcome"},
        {"kind": "shrug", "note": "x"},
        {"kind": "outcome", "note": "x" * 501},
    ],
)
def test_malformed_events_are_rejected(api, three_decisions, body):
    assert post_event(api, three_decisions[0], **body).status_code == 422
    assert api.client.get(f"/v1/decisions/{three_decisions[0]}").json()["events"] == []


def test_unknown_decision_is_404(api):
    assert api.client.get("/v1/decisions/999").status_code == 404
    assert post_event(api, 999, kind="outcome", note="x").status_code == 404


def test_detail_has_inputs_verdict_assumptions_and_events(api, three_decisions):
    green = three_decisions[0]
    detail = api.client.get(f"/v1/decisions/{green}").json()
    assert detail["inputs"]["vehicle"]["make_model"] == "2022 Honda Accord"
    assert detail["result"]["status"] == "GREEN" and detail["result"]["reasons"]
    assert detail["result"]["disclaimer"].startswith("TowFit does not replace operator judgment")
    assert any(u["key"] == "unit.patrol_42.rig_capacity_lb" for u in detail["assumptions_used"])
    assert detail["events"] == []


# ---------------------------------------------------------------- audit trail cannot be rewritten


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_records_and_events_cannot_be_changed_or_deleted_through_the_api(api, three_decisions, method):
    green = three_decisions[0]
    assert getattr(api.client, method)(f"/v1/decisions/{green}").status_code == 405
    assert getattr(api.client, method)(f"/v1/decisions/{green}/events").status_code == 405
    assert getattr(api.client, method)("/v1/decisions").status_code == 405


def test_editing_an_assumption_later_does_not_rewrite_a_past_record(api):
    body = evaluate(api, "03_yellow_pickup")
    decision = body["decision_id"]
    assert api.client.put("/v1/assumptions", json={"updates": [{"key": "unit.patrol_42.rig_capacity_lb", "value": 5000}]}).status_code == 200
    detail = api.client.get(f"/v1/decisions/{decision}").json()
    capacity = next(u for u in detail["assumptions_used"] if u["key"] == "unit.patrol_42.rig_capacity_lb")
    assert capacity["value"] == 6000  # what it was when the verdict was made
    assert detail["result"]["status"] == "YELLOW"
    assert evaluate(api, "03_yellow_pickup")["verdict"]["status"] == "RED"  # but a new evaluation sees the edit
