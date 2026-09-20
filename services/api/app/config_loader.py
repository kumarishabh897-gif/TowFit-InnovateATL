"""Loads config/*.yaml and re-reads a file whenever its mtime changes, so edits apply without a restart."""

import io
import os
import threading
from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from app.models import Assumption, AssumptionStatus, UnitProfile, VehicleSpecs

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


def _check_semantics(path: Path, item: Assumption) -> None:
    """Values the engine divides by or compares against must make sense, so a live edit cannot break an evaluation."""
    numbers = item.value if isinstance(item.value, list) else [item.value]
    if min(numbers) < 0:
        raise ConfigError(f"{path.name}: {item.key} must not be negative")
    must_be_positive = item.key in ("wrecker.avg_response_speed_mph", "backup.minutes_per_mile_of_backup")
    if (must_be_positive or item.key.endswith("rig_capacity_lb")) and min(numbers) <= 0:
        raise ConfigError(f"{path.name}: {item.key} must be greater than zero")
    if item.key == "engine.weight_advisory_fraction" and not all(0 < n <= 1 for n in numbers):
        raise ConfigError(f"{path.name}: {item.key} must be between 0 and 1")


def parse_assumptions(path: Path) -> dict[str, Assumption]:
    raw = _read_yaml(path).get("assumptions", [])
    out: dict[str, Assumption] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"{path.name}: every assumption must be a mapping with a key, got {entry!r}")
        try:
            item = Assumption.model_validate(entry)
        except ValidationError as exc:
            raise ConfigError(f"{path.name}: {entry.get('key', '?')}: {exc}") from exc
        if item.key in out:
            raise ConfigError(f"{path.name}: duplicate key {item.key}")
        _check_semantics(path, item)
        out[item.key] = item
    return out


def parse_fleet(path: Path, assumptions: dict[str, Assumption]) -> dict[str, UnitProfile]:
    out: dict[str, UnitProfile] = {}
    for entry in _read_yaml(path).get("units", []):
        if not isinstance(entry, dict):
            raise ConfigError(f"{path.name}: every unit must be a mapping, got {entry!r}")
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


class ConfigSnapshot(NamedTuple):
    """The three config files as of one instant, so one evaluation never mixes old and new values."""

    fleet: dict[str, UnitProfile]
    assumptions: dict[str, Assumption]
    specs: VehicleSpecs


class ConfigStore:
    """Thread-safe view of the three config files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir or os.environ.get("CONFIG_DIR") or REPO_ROOT / "config")
        if not self.config_dir.is_absolute():
            self.config_dir = REPO_ROOT / self.config_dir
        self._lock = threading.RLock()
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

    def snapshot(self) -> ConfigSnapshot:
        with self._lock:
            self._refresh()
            assert self._specs is not None
            return ConfigSnapshot(self._fleet, self._assumptions, self._specs)

    def unvalidated_assumption_count(self) -> int:
        return sum(1 for a in self.assumptions.values() if a.is_unvalidated)

    def update_assumptions(self, updates: list[dict]) -> dict[str, Assumption]:
        """Apply edits to assumptions.yaml, keeping its comments and layout.

        Each update is {"key": ..., and any of "value", "status", "source", "note"}. The edited file is
        validated (including that every fleet ref still resolves) before it replaces the real one, so a bad
        edit leaves the file untouched. Raises KeyError for an unknown key and ConfigError for a bad value.
        """
        path = self.config_dir / "assumptions.yaml"
        with self._lock:
            yaml_rt = YAML()
            yaml_rt.preserve_quotes = True
            yaml_rt.width = 4096
            yaml_rt.indent(mapping=2, sequence=4, offset=2)
            data = yaml_rt.load(path.read_text())
            entries = {e["key"]: e for e in data["assumptions"]}
            current = self.assumptions
            for update in updates:
                key = update["key"]
                if key not in entries:
                    raise KeyError(key)
                entry = entries[key]
                if update.get("value") is not None:
                    new = update["value"]
                    if isinstance(new, list) != isinstance(current[key].value, list):
                        kind = "a [low, high] range" if isinstance(current[key].value, list) else "a single number"
                        raise ConfigError(f"{key} takes {kind}")
                    if isinstance(new, list):
                        seq = CommentedSeq(new)
                        seq.fa.set_flow_style()
                        new = seq
                    entry["value"] = new
                if update.get("status") is not None:
                    entry["status"] = AssumptionStatus(update["status"]).value
                if update.get("source") is not None:
                    entry["source"] = update["source"]
                if update.get("note") is not None:
                    entry["note"] = update["note"]

            buffer = io.StringIO()
            yaml_rt.dump(data, buffer)
            candidate = path.with_name(".assumptions.yaml.tmp")
            candidate.write_text(buffer.getvalue())
            try:
                parse_fleet(self.config_dir / "fleet.yaml", parse_assumptions(candidate))
                os.replace(candidate, path)
            finally:
                candidate.unlink(missing_ok=True)
            self._mtimes = {}  # force a reload even if the filesystem's mtime did not move
            return self.assumptions
