from pydantic import BaseModel, model_validator

from app.models.common import AssumptionStatus


class Assumption(BaseModel):
    """One entry of config/assumptions.yaml."""

    key: str
    value: int | float | list[float]
    unit: str
    source: str
    status: AssumptionStatus
    note: str = ""

    @model_validator(mode="after")
    def _range_is_ordered_pair(self) -> "Assumption":
        if isinstance(self.value, list):
            if len(self.value) != 2:
                raise ValueError(f"{self.key}: a range must be [low, high]")
            if self.value[0] > self.value[1]:
                raise ValueError(f"{self.key}: range low exceeds high")
        return self

    @property
    def is_unvalidated(self) -> bool:
        return self.status != AssumptionStatus.VALIDATED
