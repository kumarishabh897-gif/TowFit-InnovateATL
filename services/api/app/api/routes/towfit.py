from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_config, get_session
from app.api.schemas import EvaluationResponse
from app.config_loader import ConfigStore
from app.engine import evaluate
from app.models import RECOMMENDED_ACTION, EvaluationInput
from app.services.assumption_use import describe_used
from app.services.decisions import as_utc, save_evaluation

router = APIRouter(tags=["towfit"])


@router.post("/towfit/evaluate", response_model=EvaluationResponse)
def evaluate_vehicle(
    body: EvaluationInput,
    config: ConfigStore = Depends(get_config),
    session: Session = Depends(get_session),
) -> EvaluationResponse:
    """Run the rule engine on the submitted fields and log a Decision Record.

    TowFit does not replace operator judgment or authorize a move: the response is a recommendation, and the
    operator's actual action is recorded separately with POST /v1/decisions/{id}/events.
    """
    snap = config.snapshot()  # one consistent view of config for the verdict and for the audit snapshot
    unit = snap.fleet.get(body.unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Unknown unit {body.unit_id}")
    verdict = evaluate(body, unit, snap.assumptions, snap.specs)
    used = describe_used(verdict.assumptions_used, snap, body)
    record = save_evaluation(session, body, verdict, used)
    return EvaluationResponse(
        decision_id=record.id,
        evaluated_at=as_utc(record.created_at),
        unit_id=body.unit_id,
        verdict=verdict,
        recommended_action=RECOMMENDED_ACTION[verdict.status],
        assumptions_used=used,
        unvalidated_count=sum(1 for u in used if u.is_unvalidated),
    )
