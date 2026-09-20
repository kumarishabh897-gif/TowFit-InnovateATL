from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_scenarios
from app.api.schemas import ScenarioLoad, ScenarioSummary
from app.services.scenarios import ScenarioStore

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios(scenarios: ScenarioStore = Depends(get_scenarios)) -> list[ScenarioSummary]:
    return scenarios.list()


@router.post("/scenarios/{scenario_id}/load", response_model=ScenarioLoad)
def load_scenario(scenario_id: str, scenarios: ScenarioStore = Depends(get_scenarios)) -> ScenarioLoad:
    """Returns a scenario's inputs to fill the form. It never returns a verdict; POST /v1/towfit/evaluate computes that."""
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario_id}")
    return scenario
