import json
from dataclasses import dataclass
from pathlib import Path

from app.models import Provenance, VehicleProfile, VehicleSpecs


@dataclass(frozen=True)
class _Frame:
    id: str
    file: str
    caption: str
    spec_id: str
    vehicle_class: str


class CameraStore:
    """Canned camera frames for the demo (brief section 5.6). Each frame is mapped by hand to a vehicle spec row.

    This is a fixture lookup, not computer vision: nothing here looks at pixels.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _frames(self) -> dict[str, _Frame]:
        raw = json.loads((self.directory / "manifest.json").read_text())["frames"]
        return {f["id"]: _Frame(**f) for f in raw}

    def list(self) -> list[_Frame]:
        return list(self._frames().values())

    def image_path(self, frame_id: str) -> Path | None:
        frame = self._frames().get(frame_id)
        return self.directory / frame.file if frame else None

    def classify(self, frame_id: str, specs: VehicleSpecs) -> VehicleProfile | None:
        frame = self._frames().get(frame_id)
        if frame is None:
            return None
        spec = next((m for m in specs.models if m.id == frame.spec_id), None)
        if spec is None:
            raise ValueError(f"camera frame {frame_id} points at unknown vehicle spec {frame.spec_id}")
        if spec.curb_weight_lb is not None:
            weight, provenance, source = spec.curb_weight_lb, Provenance.ESTIMATED, spec.source
        else:  # no model weight sourced: fall back to the class-typical guess and say so
            weight = specs.class_defaults[spec.vehicle_class].typical_curb_weight_lb
            provenance = Provenance.ASSUMED
            source = "Class-typical guess; no curb weight sourced for this model"
        return VehicleProfile(
            make_model=spec.make_model,
            vehicle_class=spec.vehicle_class,
            estimated_curb_weight_lb=weight,
            curb_weight_provenance=provenance,
            curb_weight_source=source,
            wheelbase_mm=spec.wheelbase_mm,
            classification_provenance=Provenance.SIM,
        )
