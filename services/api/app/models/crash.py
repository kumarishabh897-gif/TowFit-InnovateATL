from enum import StrEnum

from pydantic import BaseModel, Field


class Orientation(StrEnum):
    UPRIGHT = "upright"
    ON_SIDE = "on_side"
    ROOF = "roof"


class NeutralStatus(StrEnum):
    """Can the car be put in neutral so it can be moved? Operator-entered, not sensor-derived."""

    IN_NEUTRAL = "in_neutral"  # already in neutral
    CAN_BE_SHIFTED = "can_be_shifted"  # operator can shift it into neutral
    CAN_BE_FORCED = "can_be_forced"  # can be forced into neutral (e.g. shift-lock override)
    UNCONFIRMED = "unconfirmed"  # nobody has tried yet, or the shifter is unresponsive
    CANNOT = "cannot"  # will not go into neutral (seized drivetrain, locked wheels)

    @property
    def movable(self) -> bool:
        return self in (NeutralStatus.IN_NEUTRAL, NeutralStatus.CAN_BE_SHIFTED, NeutralStatus.CAN_BE_FORCED)


class CrashCondition(BaseModel):
    """Brief section 5.3, plus neutral_status."""

    tires_intact: int = Field(ge=0, le=4)
    wheels_locked_or_damaged: int = Field(default=0, ge=0, le=4)
    axle_damage: bool = False
    airbags_deployed: bool = False
    orientation: Orientation = Orientation.UPRIGHT
    fire_or_fuel_leak: bool = False
    neutral_status: NeutralStatus
    # tires_intact and wheels_locked_or_damaged overlap on purpose (a tire can be intact on a locked wheel);
    # the engine reads them independently.
