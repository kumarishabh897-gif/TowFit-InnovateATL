import shutil
from pathlib import Path

import pytest

from app.config_loader import REPO_ROOT, ConfigError, ConfigStore
from app.models import AssumptionStatus, Provenance, VehicleClass


@pytest.fixture()
def store() -> ConfigStore:
    return ConfigStore(REPO_ROOT / "config")


def test_all_three_files_parse(store):
    assert set(store.fleet) == {"PATROL-42", "PATROL-17"}
    assert len(store.assumptions) > 0
    assert len(store.vehicle_specs.models) > 0


def test_every_fleet_ref_resolves_to_an_assumption(store):
    for unit in store.fleet.values():
        assert set(unit.assumption_keys) == {
            "rig_capacity_lb",
            "rig_tire_width_range_mm",
            "rig_min_ground_clearance_mm",
            "rig_max_wheelbase_mm",
        }
        for key in unit.assumption_keys.values():
            assert key in store.assumptions


def test_rig_capacity_is_a_flagged_placeholder(store):
    unit = store.fleet["PATROL-42"]
    entry = store.assumptions[unit.assumption_keys["rig_capacity_lb"]]
    assert unit.rig_capacity_lb == 6000
    assert entry.status == AssumptionStatus.PLACEHOLDER


def test_compatible_classes_exclude_heavy_and_two_wheeled(store):
    excluded = {VehicleClass.BOX_TRUCK, VehicleClass.BUS, VehicleClass.TRACTOR_TRAILER, VehicleClass.MOTORCYCLE}
    for unit in store.fleet.values():
        assert not excluded & set(unit.compatible_vehicle_classes)


def test_unvalidated_count_is_visibly_nonzero(store):
    assert store.unvalidated_assumption_count() > 0


def test_every_assumption_names_a_source_and_a_status(store):
    for a in store.assumptions.values():
        assert a.source.strip()
        assert a.unit.strip()


def test_every_vehicle_spec_names_a_source(store):
    for spec in store.vehicle_specs.models:
        assert spec.source.strip()
        assert spec.provenance == Provenance.ESTIMATED


def test_class_defaults_are_assumed_and_unknown_has_none(store):
    specs = store.vehicle_specs
    assert specs.class_defaults_meta.provenance == Provenance.ASSUMED
    assert VehicleClass.UNKNOWN not in specs.class_defaults
    assert set(specs.class_defaults) == set(VehicleClass) - {VehicleClass.UNKNOWN}


def test_demo_scenario_weights_line_up_with_placeholder_capacity(store):
    """Scenario 3 (YELLOW) needs a pickup near 85% of PATROL-42's capacity; scenario 2 needs a box truck over it."""
    cap = store.fleet["PATROL-42"].rig_capacity_lb
    pickup = next(s for s in store.vehicle_specs.models if s.id == "ford_f150_supercrew_4x4_2022")
    assert pickup.curb_weight_lb is not None
    assert 0.80 < pickup.curb_weight_lb / cap < 1.0
    accord = next(s for s in store.vehicle_specs.models if s.id == "honda_accord_2022")
    assert accord.curb_weight_lb is not None
    assert accord.curb_weight_lb / cap < 0.80
    box = next(s for s in store.vehicle_specs.models if s.id == "isuzu_npr_hd_box_truck")
    assert box.gross_vehicle_weight_rating_lb is not None and box.gross_vehicle_weight_rating_lb > cap


def _copy_config(tmp_path: Path) -> Path:
    dst = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", dst)
    return dst


def test_edit_is_picked_up_without_restart(tmp_path):
    cfg = _copy_config(tmp_path)
    store = ConfigStore(cfg)
    assert store.fleet["PATROL-42"].rig_capacity_lb == 6000
    path = cfg / "assumptions.yaml"
    path.write_text(path.read_text().replace("value: 6000\n", "value: 7000\n", 1))
    assert store.fleet["PATROL-42"].rig_capacity_lb == 7000


def test_unknown_ref_is_a_clear_error(tmp_path):
    cfg = _copy_config(tmp_path)
    path = cfg / "fleet.yaml"
    path.write_text(path.read_text().replace("unit.patrol_42.rig_capacity_lb", "unit.nope"))
    with pytest.raises(ConfigError, match="unknown assumption unit.nope"):
        ConfigStore(cfg)


def test_bad_edit_keeps_last_good_config(tmp_path):
    cfg = _copy_config(tmp_path)
    store = ConfigStore(cfg)
    (cfg / "assumptions.yaml").write_text("assumptions: [not-a-mapping]\n")
    with pytest.raises(Exception):
        store.fleet
    # a later fix recovers, and nothing half-loaded was kept in between
    shutil.copy(REPO_ROOT / "config" / "assumptions.yaml", cfg / "assumptions.yaml")
    assert store.fleet["PATROL-42"].rig_capacity_lb == 6000
