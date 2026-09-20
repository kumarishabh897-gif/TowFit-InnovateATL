from enum import StrEnum


class Provenance(StrEnum):
    """Label shown next to every number on screen (brief section 2, rule 1)."""

    LIVE = "LIVE"  # real feed
    SIM = "SIM"  # simulator or demo fixture
    ESTIMATED = "ESTIMATED"  # public spec, with its source
    ASSUMED = "ASSUMED"  # invented for the demo, no source yet
    OPERATOR = "OPERATOR"  # typed in by the operator (e.g. severity, neutral status); not sensor-derived


class AssumptionStatus(StrEnum):
    PLACEHOLDER = "PLACEHOLDER"
    SOURCED = "SOURCED"
    VALIDATED = "VALIDATED"


class VehicleClass(StrEnum):
    PASSENGER_CAR = "passenger_car"
    SUV = "suv"
    PICKUP = "pickup"
    VAN = "van"
    BOX_TRUCK = "box_truck"
    TRACTOR_TRAILER = "tractor_trailer"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    UNKNOWN = "unknown"
