from fastapi import APIRouter, Depends

from app.api.deps import get_config
from app.api.schemas import FleetUnit
from app.config_loader import ConfigStore
from app.models import VehicleSpecs
from app.services.assumption_use import describe_used

router = APIRouter(tags=["fleet"])


@router.get("/fleet", response_model=list[FleetUnit])
def list_fleet(config: ConfigStore = Depends(get_config)) -> list[FleetUnit]:
    """Unit roster with rig capacities. Every rig number carries the status of the assumption behind it."""
    snap = config.snapshot()
    roster = []
    for unit in snap.fleet.values():
        described = {u.key: u for u in describe_used(unit.assumption_keys.values(), snap)}
        roster.append(
            FleetUnit(unit=unit, rig_assumptions={field: described[key] for field, key in unit.assumption_keys.items()})
        )
    return roster


@router.get("/vehicle-specs", response_model=VehicleSpecs)
def vehicle_specs(config: ConfigStore = Depends(get_config)) -> VehicleSpecs:
    """Curb-weight and dimension lookup. Each row names its source and status; class defaults are labeled ASSUMED."""
    return config.snapshot().specs
