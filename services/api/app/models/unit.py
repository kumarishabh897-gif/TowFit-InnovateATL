from pydantic import BaseModel, Field

from app.models.common import Provenance, VehicleClass


class Position(BaseModel):
    lat: float
    lon: float
    provenance: Provenance = Provenance.SIM


class UnitProfile(BaseModel):
    """A patrol car with the rig mounted (config/fleet.yaml, brief section 5.1)."""

    unit_id: str
    vehicle_platform: str
    rig_attachment_type: str
    rig_capacity_lb: float = Field(gt=0)
    rig_tire_width_range_mm: tuple[float, float]
    rig_min_ground_clearance_mm: float = Field(gt=0)
    rig_max_wheelbase_mm: float = Field(gt=0)
    compatible_vehicle_classes: list[VehicleClass]
    current_position: Position
    # field name -> assumptions.yaml key, so the UI can show which unvalidated numbers a verdict rests on
    assumption_keys: dict[str, str] = Field(default_factory=dict)
