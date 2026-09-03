from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from actions.levels import RiskLevel, requires_approval

Stage = Literal[
    "quiet",
    "early_advisory",
    "corroborated",
    "verified",
    "stand_down",
]

STAGE_ORDER: dict[Stage, int] = {
    "quiet": 0,
    "stand_down": 1,
    "early_advisory": 2,
    "corroborated": 3,
    "verified": 4,
}

STAGE_LEVEL: dict[Stage, RiskLevel] = {
    "quiet": "GREEN",
    "stand_down": "GREEN",
    "early_advisory": "GREY",
    "corroborated": "ORANGE",
    "verified": "RED",
}

CORROBORATION_MIN_INDICATORS = 2
CORROBORATION_MIN_PROBABILITY = 0.25
VERIFICATION_MIN_PROBABILITY = 0.60
STAND_DOWN_MAX_PROBABILITY = 0.05

STAGE_HEADLINE: dict[Stage, str] = {
    "quiet": "No change detected",
    "early_advisory": "Unverified change detected",
    "corroborated": "Change corroborated by independent evidence",
    "verified": "Verified hazard, action required",
    "stand_down": "Stood down, evidence no longer supports a hazard",
}

STAGE_HEADLINE_NE: dict[Stage, str] = {
    "quiet": "कुनै परिवर्तन छैन",
    "early_advisory": "अपुष्ट परिवर्तन देखियो",
    "corroborated": "स्वतन्त्र प्रमाणले पुष्टि गरेको परिवर्तन",
    "verified": "पुष्टि भएको खतरा, कारबाही आवश्यक",
    "stand_down": "खतरा हटेको, अवस्था सामान्य",
}

STAGE_MEANING: dict[Stage, str] = {
    "early_advisory": (
        "Something measurably changed and we cannot yet say what it is. This goes out "
        "immediately and without a human, because it asks for attention rather than action."
    ),
    "corroborated": (
        "Two or more independent lines of evidence now agree, or the hazard estimate crossed "
        "the corroboration threshold. This asks a district officer to approve before it is sent."
    ),
    "verified": (
        "The Verifier accepted the claim and the Explainer produced a decision. This is the only "
        "stage that tells people to move, and it never leaves without recorded approval."
    ),
    "stand_down": (
        "The evidence that raised this no longer supports a hazard. Standing down is published "
        "as loudly as escalating, because an alert that is never withdrawn cannot be trusted."
    ),
}


@dataclass(frozen=True)
class EscalationInput:
    indicators_present: int
    hazard_probability: float
    verifier_passed: bool
    verifier_vetoed: bool
    observation_stale_hours: float = 0.0


@dataclass(frozen=True)
class EscalationDecision:
    stage: Stage
    level: RiskLevel
    previous_stage: Stage | None
    autonomous: bool
    headline: str
    headline_nepali: str
    meaning: str
    reason: str
    at: datetime

    @property
    def escalated(self) -> bool:
        if self.previous_stage is None:
            return self.stage != "quiet"
        return STAGE_ORDER[self.stage] > STAGE_ORDER[self.previous_stage]

    @property
    def changed(self) -> bool:
        return self.stage != self.previous_stage

    def rendered(self) -> str:
        arrow = f"{self.previous_stage or 'none'} -> {self.stage}"
        route = "sent autonomously" if self.autonomous else "held at the gate for approval"
        return f"{arrow} ({self.level}): {self.reason}. {route}."


def classify_stage(signal: EscalationInput) -> tuple[Stage, str]:
    if signal.verifier_vetoed:
        return (
            "early_advisory",
            "the Verifier vetoed the cause claim, so the change is reported without a conclusion",
        )
    if signal.verifier_passed and signal.hazard_probability >= VERIFICATION_MIN_PROBABILITY:
        return (
            "verified",
            f"verifier accepted the claim and the hazard estimate is "
            f"{signal.hazard_probability * 100:.0f}%, at or above the "
            f"{VERIFICATION_MIN_PROBABILITY * 100:.0f}% verification threshold",
        )
    corroborated = (
        signal.indicators_present >= CORROBORATION_MIN_INDICATORS
        or signal.hazard_probability >= CORROBORATION_MIN_PROBABILITY
    )
    if corroborated:
        return (
            "corroborated",
            f"{signal.indicators_present} independent indicator(s) present and the hazard "
            f"estimate is {signal.hazard_probability * 100:.0f}%",
        )
    if signal.indicators_present >= 1:
        return (
            "early_advisory",
            f"{signal.indicators_present} indicator present but nothing corroborates it yet",
        )
    if signal.hazard_probability <= STAND_DOWN_MAX_PROBABILITY:
        return (
            "stand_down",
            f"no indicator present and the hazard estimate has fallen to "
            f"{signal.hazard_probability * 100:.1f}%",
        )
    return ("quiet", "no indicator present and nothing above the detection threshold")


def decide(signal: EscalationInput, previous: Stage | None = None) -> EscalationDecision:
    stage, reason = classify_stage(signal)
    if (
        previous is not None
        and stage == "quiet"
        and STAGE_ORDER[previous] >= STAGE_ORDER["early_advisory"]
    ):
        stage = "stand_down"
        reason = "the evidence that raised this alert is no longer present"
    level = STAGE_LEVEL[stage]
    return EscalationDecision(
        stage=stage,
        level=level,
        previous_stage=previous,
        autonomous=not requires_approval(level),
        headline=STAGE_HEADLINE[stage],
        headline_nepali=STAGE_HEADLINE_NE[stage],
        meaning=STAGE_MEANING.get(stage, ""),
        reason=reason,
        at=datetime.now(UTC),
    )


LADDER_ORDER: tuple[Stage, ...] = (
    "quiet",
    "early_advisory",
    "corroborated",
    "verified",
    "stand_down",
)


def ladder() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "stage": stage,
            "level": STAGE_LEVEL[stage],
            "order": STAGE_ORDER[stage],
            "headline": STAGE_HEADLINE[stage],
            "headline_nepali": STAGE_HEADLINE_NE[stage],
            "meaning": STAGE_MEANING.get(stage, ""),
            "autonomous": not requires_approval(STAGE_LEVEL[stage]),
        }
        for stage in LADDER_ORDER
    )
