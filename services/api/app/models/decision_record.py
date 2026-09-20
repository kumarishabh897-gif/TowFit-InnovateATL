from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.models.verdict import VerdictStatus


class OperatorAction(StrEnum):
    DEPLOY = "deploy"
    WAIT_FOR_CONFIRMATION = "wait_for_confirmation"
    DISPATCH_WRECKER = "dispatch_wrecker"


class EventKind(StrEnum):
    OPERATOR_ACTION = "operator_action"
    OUTCOME = "outcome"


# What TowFit recommends for each verdict. The operator may do something else; the log records both.
RECOMMENDED_ACTION: dict[VerdictStatus, OperatorAction] = {
    VerdictStatus.GREEN: OperatorAction.DEPLOY,
    VerdictStatus.YELLOW: OperatorAction.WAIT_FOR_CONFIRMATION,
    VerdictStatus.RED: OperatorAction.DISPATCH_WRECKER,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DecisionRecord(SQLModel, table=True):
    """One TowFit evaluation (brief section 2, rule 6). Insert-only: db.py adds triggers that reject UPDATE and DELETE.

    The operator's action and any outcome are separate DecisionEvent rows, so this row never changes.
    """

    __tablename__ = "decision_record"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    unit_id: str = Field(index=True)
    vehicle_summary: str  # make/model for the log strip
    verdict: str = Field(index=True)  # GREEN | YELLOW | RED
    loaded_scenario_id: str | None = None
    inputs_json: str  # the full EvaluationInput as submitted
    verdict_json: str  # the full Verdict: status, reasons, clearance, wrecker, confirmation, disclaimer
    reasons_json: str  # every reason, in evaluation order
    rules_fired_json: str  # [{rule_id, effect}] in evaluation order
    assumptions_json: str  # snapshot (value, status, source) of every assumption used, since they are editable
    disclaimer: str


class DecisionEvent(SQLModel, table=True):
    """Something that happened after a Decision Record: the operator's action, or an outcome. Insert-only."""

    __tablename__ = "decision_event"

    id: int | None = Field(default=None, primary_key=True)
    decision_id: int = Field(foreign_key="decision_record.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    kind: str  # operator_action | outcome
    action: str | None = None  # deploy | wait_for_confirmation | dispatch_wrecker (for operator_action)
    note: str | None = None
