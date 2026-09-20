from fastapi import APIRouter

from app.api.routes import assumptions, decisions, fleet, scenarios, towfit

router = APIRouter(prefix="/v1")
router.include_router(fleet.router)
router.include_router(scenarios.router)
router.include_router(towfit.router)
router.include_router(decisions.router)
router.include_router(assumptions.router)
