from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import get_session
from app.api.schemas import DecisionDetail, DecisionList, DecisionSummary, EventCreate
from app.models import DecisionEvent, DecisionRecord, VerdictStatus
from app.services.decisions import detail, summarize_many, to_naive_utc

router = APIRouter(tags=["decisions"])


def _events_for(session: Session, ids: list[int]) -> list[DecisionEvent]:
    if not ids:
        return []
    return list(session.exec(select(DecisionEvent).where(DecisionEvent.decision_id.in_(ids))))  # type: ignore[attr-defined]


@router.get("/decisions", response_model=DecisionList)
def list_decisions(
    unit_id: str | None = None,
    verdict: VerdictStatus | None = None,
    since: datetime | None = Query(default=None, description="Only records at or after this time (ISO 8601; naive means UTC)"),
    until: datetime | None = Query(default=None, description="Only records before this time (ISO 8601; naive means UTC)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DecisionList:
    """The Decision Record log, newest first."""
    conditions = []
    if unit_id:
        conditions.append(DecisionRecord.unit_id == unit_id)
    if verdict:
        conditions.append(DecisionRecord.verdict == verdict.value)
    if since:
        conditions.append(DecisionRecord.created_at >= to_naive_utc(since))
    if until:
        conditions.append(DecisionRecord.created_at < to_naive_utc(until))
    total = session.exec(select(func.count()).select_from(DecisionRecord).where(*conditions)).one()
    records = list(
        session.exec(
            select(DecisionRecord)
            .where(*conditions)
            .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())  # type: ignore[attr-defined]
            .offset(offset)
            .limit(limit)
        )
    )
    events = _events_for(session, [r.id for r in records])
    return DecisionList(items=summarize_many(records, events), total=total, limit=limit, offset=offset)


@router.get("/decisions/{decision_id}", response_model=DecisionDetail)
def get_decision(decision_id: int, session: Session = Depends(get_session)) -> DecisionDetail:
    """One Decision Record in full: inputs as submitted, the verdict and reasons, the assumptions it used, and its events."""
    record = session.get(DecisionRecord, decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No decision {decision_id}")
    return detail(record, _events_for(session, [decision_id]))


@router.post("/decisions/{decision_id}/events", response_model=DecisionSummary, status_code=201)
def record_event(decision_id: int, body: EventCreate, session: Session = Depends(get_session)) -> DecisionSummary:
    """Record what the operator actually did (deploy / wait for confirmation / dispatch wrecker), or an outcome.

    Events are appended, never edited: the Decision Record and its events are an audit trail. The operator may act
    differently from the recommendation; the summary reports whether they followed it.
    """
    record = session.get(DecisionRecord, decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No decision {decision_id}")
    session.add(
        DecisionEvent(
            decision_id=decision_id,
            kind=body.kind.value,
            action=body.action.value if body.action else None,
            note=body.note,
        )
    )
    session.commit()
    return summarize_many([record], _events_for(session, [decision_id]))[0]
