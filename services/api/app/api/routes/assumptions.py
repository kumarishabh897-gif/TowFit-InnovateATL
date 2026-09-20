from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_config
from app.api.schemas import AssumptionsResponse, AssumptionsUpdateRequest
from app.config_loader import ConfigError, ConfigStore

router = APIRouter(tags=["assumptions"])


def _response(config: ConfigStore) -> AssumptionsResponse:
    items = list(config.assumptions.values())
    return AssumptionsResponse(
        assumptions=items, total=len(items), unvalidated_count=sum(1 for a in items if a.is_unvalidated)
    )


@router.get("/assumptions", response_model=AssumptionsResponse)
def read_assumptions(config: ConfigStore = Depends(get_config)) -> AssumptionsResponse:
    return _response(config)


@router.put("/assumptions", response_model=AssumptionsResponse)
def edit_assumptions(body: AssumptionsUpdateRequest, config: ConfigStore = Depends(get_config)) -> AssumptionsResponse:
    """Edit assumptions.yaml. The next /v1/towfit/evaluate call uses the new values; no restart.

    All edits in one request apply together or not at all. The file's comments are kept.
    Past Decision Records keep the values they were evaluated with.
    """
    try:
        config.update_assumptions([u.model_dump(mode="json", exclude_none=True) for u in body.updates])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown assumption {exc.args[0]}") from exc
    except ConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response(config)
