"""The camera stub: canned frames mapped to vehicle profiles, always labeled SIM."""

import pytest

from app.models import EvaluationInput
from tests.conftest import edit, load_scenario

FRAMES = {
    "frame_sedan": ("2022 Honda Accord", "passenger_car", 3300, "ESTIMATED"),
    "frame_suv": ("2022 Toyota RAV4", "suv", 3490, "ESTIMATED"),
    "frame_pickup": ("2022 Ford F-150 SuperCrew 4x4", "pickup", 5100, "ESTIMATED"),
    "frame_box_truck": ("Isuzu NPR-HD box truck", "box_truck", 8000, "ASSUMED"),
}


def test_frames_are_listed_with_captions_and_image_urls(api):
    frames = api.client.get("/v1/camera/frames").json()
    assert [f["id"] for f in frames] == list(FRAMES)
    for frame in frames:
        assert frame["caption"].startswith("Demo frame")
        assert frame["image_url"] == f"/v1/camera/frames/{frame['id']}/image"


@pytest.mark.parametrize("frame_id", FRAMES)
def test_every_frame_has_a_servable_image(api, frame_id):
    response = api.client.get(f"/v1/camera/frames/{frame_id}/image")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"not a live camera" in response.content


@pytest.mark.parametrize("frame_id", FRAMES)
def test_classification_fills_the_profile_and_is_labeled_sim(api, frame_id):
    make_model, vehicle_class, weight, weight_provenance = FRAMES[frame_id]
    body = api.client.post(f"/v1/camera/frames/{frame_id}/classify").json()
    assert body["provenance"] == "SIM"
    assert body["label"] == "SIM classification (demo fixture, not a live model)"
    vehicle = body["vehicle"]
    assert vehicle["classification_provenance"] == "SIM"
    assert (vehicle["make_model"], vehicle["vehicle_class"]) == (make_model, vehicle_class)
    assert vehicle["estimated_curb_weight_lb"] == weight
    assert vehicle["curb_weight_provenance"] == weight_provenance and vehicle["curb_weight_source"]


def test_a_model_with_no_sourced_weight_falls_back_to_an_assumed_class_guess(api):
    vehicle = api.client.post("/v1/camera/frames/frame_box_truck/classify").json()["vehicle"]
    assert vehicle["curb_weight_provenance"] == "ASSUMED" and "Class-typical guess" in vehicle["curb_weight_source"]
    assert vehicle["estimated_load_weight_lb"] is None  # the stub never invents a load


def test_classifying_logs_nothing_and_never_returns_a_verdict(api):
    body = api.client.post("/v1/camera/frames/frame_sedan/classify").json()
    assert set(body) == {"frame_id", "provenance", "label", "vehicle"}
    assert api.client.get("/v1/decisions").json()["total"] == 0


def test_unknown_frame_is_404(api):
    assert api.client.post("/v1/camera/frames/nope/classify").status_code == 404
    assert api.client.get("/v1/camera/frames/nope/image").status_code == 404


def test_a_classified_vehicle_can_be_evaluated_once_the_operator_adds_the_crash_details(api):
    vehicle = api.client.post("/v1/camera/frames/frame_sedan/classify").json()["vehicle"]
    base = load_scenario("01_green_accord").model_dump(mode="json")
    base["vehicle"] = vehicle
    inp = EvaluationInput.model_validate(base)
    assert api.evaluate(inp).json()["verdict"]["status"] == "GREEN"
    assert api.evaluate(edit(inp, crash={"neutral_status": "cannot"})).json()["verdict"]["status"] == "RED"


def test_every_frame_points_at_a_real_spec_row(config):
    from app.config_loader import REPO_ROOT
    from app.services.camera import CameraStore

    store = CameraStore(REPO_ROOT / "fixtures" / "camera")
    for frame in store.list():
        assert store.classify(frame.id, config.vehicle_specs) is not None
        assert store.image_path(frame.id).exists()
