from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.models.common import Provenance


class LiveTrafficRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IncidentSeverity(BaseModel):
    """Brief section 5.5: operator-entered from 911 / camera / officer input, not sensor-derived."""

    level: Severity
    provenance: Provenance = Provenance.OPERATOR


class Scene(BaseModel):
    """Brief section 5.4."""

    lanes_total: int = Field(ge=1)
    lanes_blocked: int = Field(ge=0)
    shoulder_available: bool
    shoulder_width_ok: bool
    grade_or_curve: bool = False
    live_traffic_risk: LiveTrafficRisk = LiveTrafficRisk.LOW
    live_traffic_risk_provenance: Provenance = Provenance.SIM

    @model_validator(mode="after")
    def _blocked_within_total(self) -> "Scene":
        if self.lanes_blocked > self.lanes_total:
            raise ValueError("lanes_blocked cannot exceed lanes_total")
        return self
