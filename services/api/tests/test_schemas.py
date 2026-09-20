import pytest
from pydantic import ValidationError

from app.models import (
    DISCLAIMER,
    CrashCondition,
    MinutesEstimate,
    NeutralStatus,
    Reason,
    ReasonEffect,
    Scene,
    Verdict,
    VerdictStatus,
    WreckerClass,
    WreckerRecommendation,
)


def _reason(effect: ReasonEffect) -> Reason:
    return Reason(rule_id="test", effect=effect, text="because")


CLEARANCE = MinutesEstimate(point=4, low=3, high=6)
WRECKER = WreckerRecommendation(wrecker_class=WreckerClass.HEAVY_DUTY, eta_minutes=30)


def test_disclaimer_is_the_exact_brief_string():
    assert DISCLAIMER == (
        "TowFit does not replace operator judgment or authorize a move. "
        "It provides a documented safety recommendation based on vehicle, rig, and scene constraints."
    )


def test_verdict_without_reasons_is_rejected():
    with pytest.raises(ValidationError, match="no reasons"):
        Verdict(status=VerdictStatus.GREEN, reasons=[], estimated_clearance_minutes=CLEARANCE)


def test_green_carries_disclaimer_and_clearance():
    v = Verdict(status=VerdictStatus.GREEN, reasons=[_reason(ReasonEffect.GREEN)], estimated_clearance_minutes=CLEARANCE)
    assert v.disclaimer == DISCLAIMER


def test_green_cannot_carry_a_red_or_yellow_reason():
    for effect in (ReasonEffect.RED, ReasonEffect.YELLOW):
        with pytest.raises(ValidationError):
            Verdict(status=VerdictStatus.GREEN, reasons=[_reason(effect)], estimated_clearance_minutes=CLEARANCE)


def test_green_may_carry_advisories():
    Verdict(
        status=VerdictStatus.GREEN,
        reasons=[_reason(ReasonEffect.GREEN), _reason(ReasonEffect.ADVISORY)],
        estimated_clearance_minutes=CLEARANCE,
    )


def test_red_needs_a_red_reason_and_a_wrecker():
    Verdict(status=VerdictStatus.RED, reasons=[_reason(ReasonEffect.RED)], wrecker=WRECKER)
    with pytest.raises(ValidationError):
        Verdict(status=VerdictStatus.RED, reasons=[_reason(ReasonEffect.RED)])
    with pytest.raises(ValidationError):
        Verdict(status=VerdictStatus.RED, reasons=[_reason(ReasonEffect.GREEN)], wrecker=WRECKER)


def test_yellow_needs_yellow_reason_confirmation_and_clearance():
    kwargs = dict(
        status=VerdictStatus.YELLOW,
        reasons=[_reason(ReasonEffect.YELLOW)],
        estimated_clearance_minutes=CLEARANCE,
        confirmation_required_from="on-scene supervisor",
    )
    Verdict(**kwargs)
    with pytest.raises(ValidationError):
        Verdict(**{**kwargs, "confirmation_required_from": None})
    with pytest.raises(ValidationError):
        Verdict(**{**kwargs, "estimated_clearance_minutes": None})
    with pytest.raises(ValidationError):
        Verdict(**{**kwargs, "reasons": [_reason(ReasonEffect.YELLOW), _reason(ReasonEffect.RED)]})


@pytest.mark.parametrize(
    ("status", "movable"),
    [
        (NeutralStatus.IN_NEUTRAL, True),
        (NeutralStatus.CAN_BE_SHIFTED, True),
        (NeutralStatus.CAN_BE_FORCED, True),
        (NeutralStatus.UNCONFIRMED, False),
        (NeutralStatus.CANNOT, False),
    ],
)
def test_only_the_three_neutral_capable_states_count_as_movable(status, movable):
    assert status.movable is movable


def test_crash_condition_bounds():
    CrashCondition(tires_intact=4, neutral_status=NeutralStatus.IN_NEUTRAL)
    with pytest.raises(ValidationError):
        CrashCondition(tires_intact=5, neutral_status=NeutralStatus.IN_NEUTRAL)
    with pytest.raises(ValidationError):
        CrashCondition(tires_intact=4)  # neutral_status is required: the engine must never guess it


def test_scene_rejects_more_blocked_than_total_lanes():
    with pytest.raises(ValidationError):
        Scene(lanes_total=2, lanes_blocked=3, shoulder_available=True, shoulder_width_ok=True)
