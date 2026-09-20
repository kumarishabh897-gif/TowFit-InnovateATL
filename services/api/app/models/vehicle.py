from typing import Literal

from pydantic import BaseModel, Field

from app.models.common import Provenance, VehicleClass


class VehicleProfile(BaseModel):
    """The disabled vehicle (brief section 5.2)."""

    make_model: str
    vehicle_class: VehicleClass
    estimated_curb_weight_lb: float = Field(gt=0)
    # ESTIMATED when it comes from config/vehicle_specs.yaml, ASSUMED for a manual entry or class-midpoint guess.
    curb_weight_provenance: Provenance = Provenance.ASSUMED
    curb_weight_source: str | None = None
    estimated_load_weight_lb: float | None = Field(default=None, ge=0)
    load_weight_provenance: Provenance = Provenance.ASSUMED
    drivetrain: str | None = None  # informational only in v0

    # Optional measured dimensions; when missing, the engine uses class-typical values and flags them ASSUMED.
    tire_width_mm: float | None = Field(default=None, gt=0)
    ground_clearance_mm: float | None = Field(default=None, gt=0)
    wheelbase_mm: float | None = Field(default=None, gt=0)

    # OPERATOR for hand entry; SIM when filled by the camera stub (brief section 5.6, not a live model).
    classification_provenance: Literal[Provenance.OPERATOR, Provenance.SIM] = Provenance.OPERATOR
