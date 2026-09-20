"""Loads config/*.yaml and re-reads a file whenever its mtime changes, so edits apply without a restart."""

import os
import threading
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models import Assumption, UnitProfile, VehicleSpecs

REPO_ROOT = Path(__file__).resolve().parents[3]

# fleet.yaml fields that are `ref: <assumption key>` pointers
_REF_FIELDS = (
    "rig_capacity_lb",
    "rig_tire_width_range_mm",
    "rig_min_ground_clearance_mm",
    "rig_max_wheelbase_mm",
)


class ConfigError(ValueError):
    """A config file is malformed, or points at something that does not exist."""


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: expected a mapping at the top level")
    return data


def parse_assumptions(path: Path) -> dict[str, Assumption]:
    raw = _read_yaml(path).get("assumptions", [])
    out: dict[str, Assumption] = {}
    for entry in raw:
        try:
            item = Assumption.model_validate(entry)
        except ValidationError as exc:
            raise ConfigError(f"{path.name}: {entry.get('key', '?')}: {exc}") from exc
        if item.key in out:
            raise ConfigError(f"{path.name}: duplicate key {item.key}")
        out[item.key] = item
    return out


def parse_fleet(path: Path, assumptions: dict[str, Assumption]) -> dict[str, UnitProfile]:
    out: dict[str, UnitProfile] = {}
    for entry in _read_yaml(path).get("units", []):
        entry = dict(entry)
        keys: dict[str, str] = {}
        for field in _REF_FIELDS:
            ref = entry.get(field)
            if not (isinstance(ref, dict) and "ref" in ref):
                raise ConfigError(f"{path.name}: {entry.get('unit_id', '?')}.{field} must be `ref: <assumption key>`")
            key = ref["ref"]
            if key not in assumptions:
                raise ConfigError(f"{path.name}: {entry.get('unit_id', '?')}.{field} refers to unknown assumption {key}")
            entry[field] = assumptions[key].value
            keys[field] = key
        entry["assumption_keys"] = keys
        try:
            unit = UnitProfile.model_validate(entry)
        except ValidationError as exc:
            raise ConfigError(f"{path.name}: {entry.get('unit_id', '?')}: {exc}") from exc
        if unit.unit_id in out:
            raise ConfigError(f"{path.name}: duplicate unit_id {unit.unit_id}")
        out[unit.unit_id] = unit
    return out


def parse_vehicle_specs(path: Path) -> VehicleSpecs:
    try:
        return VehicleSpecs.model_validate(_read_yaml(path))
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: {exc}") from exc


class ConfigStore:
    """Thread-safe view of the three config files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir or os.environ.get("CONFIG_DIR") or REPO_ROOT / "config")
        if not self.config_dir.is_absolute():
            self.config_dir = REPO_ROOT / self.config_dir
        self._lock = threading.Lock()
        self._mtimes: dict[str, float] = {}
        self._assumptions: dict[str, Assumption] = {}
        self._fleet: dict[str, UnitProfile] = {}
        self._specs: VehicleSpecs | None = None
        self._refresh()

    def _mtime(self, name: str) -> float:
        return (self.config_dir / name).stat().st_mtime_ns

    def _refresh(self) -> None:
        with self._lock:
            current = {n: self._mtime(n) for n in ("assumptions.yaml", "fleet.yaml", "vehicle_specs.yaml")}
            if current == self._mtimes:
                return
            assumptions = parse_assumptions(self.config_dir / "assumptions.yaml")
            fleet = parse_fleet(self.config_dir / "fleet.yaml", assumptions)
            specs = parse_vehicle_specs(self.config_dir / "vehicle_specs.yaml")
            # Swap only after all three parsed, so a bad edit never leaves a half-loaded state.
            self._assumptions, self._fleet, self._specs = assumptions, fleet, specs
            self._mtimes = current

    @property
    def assumptions(self) -> dict[str, Assumption]:
        self._refresh()
        return self._assumptions

    @property
    def fleet(self) -> dict[str, UnitProfile]:
        self._refresh()
        return self._fleet

    @property
    def vehicle_specs(self) -> VehicleSpecs:
        self._refresh()
        assert self._specs is not None
        return self._specs

    def unvalidated_assumption_count(self) -> int:
        return sum(1 for a in self.assumptions.values() if a.is_unvalidated)
