"""Request and response bodies for /v1 (brief section 8)."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.models import (
    Assumption,
    AssumptionStatus,
    EvaluationInput,
    EventKind,
    OperatorAction,
    Provenance,
    UnitProfile,
    Verdict,
    VerdictStatus,
)


class AssumptionUse(BaseModel):
    """One unvalidated or estimated number a verdict rested on, with where it came from."""

    key: str
    # assumption: an entry in assumptions.yaml (editable via PUT /v1/assumptions)
    # class_default: a class-typical value from vehicle_specs.yaml, used because a dimension was not entered
    # input: a weight the operator entered or guessed for this incident
    kind: Literal["assumption", "class_default", "input"]
    value: int | float | list[float] | dict[str, float] | None
    unit: str | None = None
    source: str
    status: AssumptionStatus
    provenance: Provenance
    note: str = ""
    editable: bool = False

    @property
    def is_unvalidated(self) -> bool:
        return self.status != AssumptionStatus.VALIDATED


class FleetUnit(BaseModel):
    unit: UnitProfile
    operational_status: str = "available"
    operational_status_provenance: Provenance = Provenance.SIM
    rig_assumptions: dict[str, AssumptionUse]  # rig field -> the assumption behind it


class ScenarioSummary(BaseModel):
    id: str
    title: str
    description: str


class ScenarioLoad(ScenarioSummary):
    """A scenario's inputs, ready to fill the form. Deliberately has no verdict: the engine computes it."""

    input: EvaluationInput


class EvaluationResponse(BaseModel):
    decision_id: int
    evaluated_at: datetime
    unit_id: str
    verdict: Verdict
    recommended_action: OperatorAction
    assumptions_used: list[AssumptionUse]
    unvalidated_count: int


class EventCreate(BaseModel):
    kind: EventKind
    action: OperatorAction | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _shape_matches_kind(self) -> Self:
        if self.kind == EventKind.OPERATOR_ACTION and self.action is None:
            raise ValueError("an operator_action event needs an action")
        if self.kind == EventKind.OUTCOME and (self.action is not None or not self.note):
            raise ValueError("an outcome event takes a note and no action")
        return self


class DecisionEventOut(BaseModel):
    id: int
    created_at: datetime
    kind: EventKind
    action: OperatorAction | None
    note: str | None


class DecisionSummary(BaseModel):
    id: int
    created_at: datetime
    unit_id: str
    vehicle_summary: str
    verdict: VerdictStatus
    loaded_scenario_id: str | None
    recommended_action: OperatorAction
    operator_action: OperatorAction | None  # the operator's most recent recorded action
    followed_recommendation: bool | None  # None until the operator records an action
    outcome: str | None  # the most recent outcome note


class DecisionDetail(DecisionSummary):
    inputs: EvaluationInput
    result: Verdict
    assumptions_used: list[AssumptionUse]
    events: list[DecisionEventOut]


class DecisionList(BaseModel):
    items: list[DecisionSummary]
    total: int
    limit: int
    offset: int


class AssumptionUpdate(BaseModel):
    key: str
    value: int | float | list[int | float] | None = None  # ints stay ints, so the YAML reads [2, 9] not [2.0, 9.0]
    status: AssumptionStatus | None = None
    source: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if all(v is None for v in (self.value, self.status, self.source, self.note)):
            raise ValueError(f"{self.key}: give at least one of value, status, source, note")
        return self


class AssumptionsUpdateRequest(BaseModel):
    updates: list[AssumptionUpdate] = Field(min_length=1)


class AssumptionsResponse(BaseModel):
    assumptions: list[Assumption]
    total: int
    unvalidated_count: int
