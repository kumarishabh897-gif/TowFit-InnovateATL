from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.models.crash import CrashCondition
from app.models.scene import IncidentSeverity, Scene
from app.models.vehicle import VehicleProfile

# Fixed framing from brief section 1. Shown under every verdict in the UI and in the pitch.
DISCLAIMER = (
    "TowFit does not replace operator judgment or authorize a move. "
    "It provides a documented safety recommendation based on vehicle, rig, and scene constraints."
)


class VerdictStatus(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ReasonEffect(StrEnum):
    RED = "RED"  # a hard trigger that forces RED
    YELLOW = "YELLOW"  # a trigger that needs confirmation
    GREEN = "GREEN"  # a check that passed
    ADVISORY = "ADVISORY"  # shown to the operator but never changes the verdict


class WreckerClass(StrEnum):
    LIGHT_DUTY = "light_duty"  # includes flatbed / dolly for cars that will not roll
    HEAVY_DUTY = "heavy_duty"


class Reason(BaseModel):
    rule_id: str
    effect: ReasonEffect
    text: str = Field(min_length=1)
    assumption_keys: list[str] = Field(default_factory=list)  # unvalidated inputs this reason relied on


class MinutesEstimate(BaseModel):
    point: float
    low: float
    high: float


class WreckerRecommendation(BaseModel):
    wrecker_class: WreckerClass
    eta_minutes: float


class EvaluationInput(BaseModel):
    """Body of POST /v1/towfit/evaluate (brief section 8)."""

    unit_id: str
    vehicle: VehicleProfile
    crash: CrashCondition
    scene: Scene
    severity: IncidentSeverity
    loaded_scenario_id: str | None = None  # recorded in the Decision Record; never used to pick a verdict


class Verdict(BaseModel):
    """Output contract from brief section 6.4."""

    status: VerdictStatus
    reasons: list[Reason]
    estimated_clearance_minutes: MinutesEstimate | None = None
    wrecker: WreckerRecommendation | None = None
    confirmation_required_from: str | None = None
    assumptions_used: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER

    @model_validator(mode="after")
    def _shape_matches_status(self) -> "Verdict":
        effects = {r.effect for r in self.reasons}
        if not self.reasons:
            raise ValueError("a verdict with no reasons is a bug")
        if self.status == VerdictStatus.RED:
            if ReasonEffect.RED not in effects:
                raise ValueError("RED verdict needs at least one RED reason")
            if self.wrecker is None:
                raise ValueError("RED verdict needs a recommended wrecker and ETA")
        elif self.status == VerdictStatus.YELLOW:
            if ReasonEffect.RED in effects or ReasonEffect.YELLOW not in effects:
                raise ValueError("YELLOW verdict needs a YELLOW reason and no RED reason")
            if not self.confirmation_required_from:
                raise ValueError("YELLOW verdict needs confirmation_required_from")
        else:
            if effects & {ReasonEffect.RED, ReasonEffect.YELLOW}:
                raise ValueError("GREEN verdict cannot carry RED or YELLOW reasons")
        if self.status != VerdictStatus.RED and self.estimated_clearance_minutes is None:
            raise ValueError("GREEN/YELLOW verdict needs an estimated clearance time")
        return self
