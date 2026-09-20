import json
from collections import defaultdict
from datetime import UTC, datetime

from sqlmodel import Session

from app.api.schemas import AssumptionUse, DecisionDetail, DecisionEventOut, DecisionSummary
from app.models import (
    RECOMMENDED_ACTION,
    DecisionEvent,
    DecisionRecord,
    EvaluationInput,
    EventKind,
    OperatorAction,
    Verdict,
    VerdictStatus,
)


def as_utc(value: datetime) -> datetime:
    """SQLite hands datetimes back without a timezone; everything we store is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def to_naive_utc(value: datetime) -> datetime:
    """The form a filter value must take to compare against what SQLite stored."""
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def save_evaluation(
    session: Session, inp: EvaluationInput, verdict: Verdict, used: list[AssumptionUse]
) -> DecisionRecord:
    record = DecisionRecord(
        unit_id=inp.unit_id,
        vehicle_summary=inp.vehicle.make_model,
        verdict=verdict.status.value,
        loaded_scenario_id=inp.loaded_scenario_id,
        inputs_json=inp.model_dump_json(),
        verdict_json=verdict.model_dump_json(),
        reasons_json=json.dumps([r.model_dump(mode="json") for r in verdict.reasons]),
        rules_fired_json=json.dumps([{"rule_id": r.rule_id, "effect": r.effect.value} for r in verdict.reasons]),
        assumptions_json=json.dumps([u.model_dump(mode="json") for u in used]),
        disclaimer=verdict.disclaimer,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _event_out(event: DecisionEvent) -> DecisionEventOut:
    return DecisionEventOut(
        id=event.id,
        created_at=as_utc(event.created_at),
        kind=EventKind(event.kind),
        action=OperatorAction(event.action) if event.action else None,
        note=event.note,
    )


def _summary(record: DecisionRecord, events: list[DecisionEvent]) -> DecisionSummary:
    status = VerdictStatus(record.verdict)
    recommended = RECOMMENDED_ACTION[status]
    actions = [e for e in events if e.kind == EventKind.OPERATOR_ACTION.value]
    outcomes = [e for e in events if e.kind == EventKind.OUTCOME.value]
    latest_action = OperatorAction(actions[-1].action) if actions else None
    return DecisionSummary(
        id=record.id,
        created_at=as_utc(record.created_at),
        unit_id=record.unit_id,
        vehicle_summary=record.vehicle_summary,
        verdict=status,
        loaded_scenario_id=record.loaded_scenario_id,
        recommended_action=recommended,
        operator_action=latest_action,
        followed_recommendation=None if latest_action is None else latest_action == recommended,
        outcome=outcomes[-1].note if outcomes else None,
    )


def summarize_many(records: list[DecisionRecord], events: list[DecisionEvent]) -> list[DecisionSummary]:
    by_decision: dict[int, list[DecisionEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda e: e.id):
        by_decision[event.decision_id].append(event)
    return [_summary(r, by_decision[r.id]) for r in records]


def detail(record: DecisionRecord, events: list[DecisionEvent]) -> DecisionDetail:
    events = sorted(events, key=lambda e: e.id)
    return DecisionDetail(
        **_summary(record, events).model_dump(),
        inputs=EvaluationInput.model_validate_json(record.inputs_json),
        result=Verdict.model_validate_json(record.verdict_json),
        assumptions_used=[AssumptionUse.model_validate(u) for u in json.loads(record.assumptions_json)],
        events=[_event_out(e) for e in events],
    )
