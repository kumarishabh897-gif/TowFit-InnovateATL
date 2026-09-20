from pydantic import BaseModel, Field, model_validator

from app.models.common import AssumptionStatus, Provenance, VehicleClass


class VehicleSpec(BaseModel):
    """One real make/model row of config/vehicle_specs.yaml. A null field means "no source yet"."""

    id: str
    make_model: str
    vehicle_class: VehicleClass
    curb_weight_lb: float | None = None
    curb_weight_lb_range: tuple[float, float] | None = None
    wheelbase_mm: float | None = None
    tire_width_mm_range: tuple[float, float] | None = None
    ground_clearance_mm: float | None = None
    gross_vehicle_weight_rating_lb: float | None = None
    provenance: Provenance
    status: AssumptionStatus
    source: str = Field(min_length=1)
    note: str = ""

    @model_validator(mode="after")
    def _point_inside_range(self) -> "VehicleSpec":
        if self.curb_weight_lb is not None and self.curb_weight_lb_range is not None:
            lo, hi = self.curb_weight_lb_range
            if not lo <= self.curb_weight_lb <= hi:
                raise ValueError(f"{self.id}: curb_weight_lb {self.curb_weight_lb} is outside its sourced range")
        return self


class ClassDefaults(BaseModel):
    """Class-typical fallback values. Always ASSUMED (see ClassDefaultsMeta)."""

    typical_curb_weight_lb: float = Field(gt=0)
    tire_width_mm: float = Field(gt=0)
    ground_clearance_mm: float = Field(gt=0)
    wheelbase_mm: float = Field(gt=0)


class ClassDefaultsMeta(BaseModel):
    provenance: Provenance
    status: AssumptionStatus
    source: str
    note: str = ""


class VehicleSpecs(BaseModel):
    models: list[VehicleSpec]
    class_defaults: dict[VehicleClass, ClassDefaults]
    class_defaults_meta: ClassDefaultsMeta

    @model_validator(mode="after")
    def _unique_ids_and_no_unknown_defaults(self) -> "VehicleSpecs":
        ids = [m.id for m in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate vehicle spec id")
        if VehicleClass.UNKNOWN in self.class_defaults:
            raise ValueError("`unknown` must not have class defaults; the engine cannot check dimensions for it")
        return self
