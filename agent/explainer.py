from __future__ import annotations

from dataclasses import dataclass

from agent.decision import (
    Confidence,
    Decision,
    DecisionInputs,
    decide,
    flip_points,
)
from agent.ledger import Ledger
from agent.router import Lane, gateway
from agent.verifier import VerificationTable
from analysis.exposure.leadtime import lead_time_for
from analysis.hydro.scenarios import ScenarioKey
from core.board import Level
from core.errors import AllProvidersFailedError

EXPLAIN_LANE: Lane = "sanket-explain"

STATUS_NEPALI: dict[Level, str] = {
    "NORMAL": "सामान्य",
    "WATCH": "निगरानी",
    "ALERT": "चेतावनी",
    "INSUFFICIENT": "अपर्याप्त प्रमाण",
}

STATUS_ACTION_NEPALI: dict[Level, str] = {
    "NORMAL": "अहिले कुनै कारबाही आवश्यक छैन।",
    "WATCH": "स्थिति निगरानीमा छ। तयार रहनुहोस्।",
    "ALERT": "तुरुन्त सुरक्षित स्थानमा सर्नुहोस्।",
    "INSUFFICIENT": "हामीसँग प्रमाण अपर्याप्त छ; कुनै निष्कर्ष निकालिएको छैन।",
}

CONTEXT_SYSTEM_PROMPT = (
    "You write one short additional sentence of plain-language context for a public "
    "flood-hazard note. You are given exact facts already stated; do not repeat numbers, "
    "do not invent any number, do not add certainty the facts do not support. One "
    "sentence only, in the requested language."
)


@dataclass(frozen=True)
class Counterfactual:
    change: str
    new_status: Level
    new_lead_time_minutes: float | None


@dataclass(frozen=True)
class EvidencePack:
    status: Level
    score: float
    contributions: tuple[str, ...]
    counterfactuals: tuple[Counterfactual, ...]
    flip_point_summary: tuple[str, ...]
    what_would_change_my_mind: tuple[str, ...]
    provenance_links: tuple[str, ...]


@dataclass(frozen=True)
class PublicNote:
    english: str
    nepali: str


@dataclass(frozen=True)
class ResidentScript:
    settlement: str
    nepali_text: str


@dataclass(frozen=True)
class ExplainerOutput:
    decision: Decision
    vetoed: bool
    evidence_pack: EvidencePack
    public_note: PublicNote
    scripts: tuple[ResidentScript, ...]


def decision_inputs_from_ledger(
    ledger: Ledger, table: VerificationTable, confidence: Confidence
) -> DecisionInputs:
    z = 0.0
    lead_time: float | None = None
    exposure = 0
    for evidence in ledger.evidence:
        if "z" in evidence.value and evidence.value["z"] is not None:
            z = max(z, abs(float(evidence.value["z"])))
        if "fastest_arrival_minutes" in evidence.value:
            candidate = evidence.value["fastest_arrival_minutes"]
            if candidate is not None:
                lead_time = candidate if lead_time is None else min(lead_time, float(candidate))
        if "population" in evidence.value:
            exposure = max(exposure, int(evidence.value["population"]))
    vetoed = table.status == "INSUFFICIENT"
    return DecisionInputs(z, lead_time, exposure, confidence, vetoed)


def _fmt_contribution(term: str, raw: str, contribution: float) -> str:
    return f"{term} {raw} contribution {contribution:+.3f}"


def _format_flip(name: str, value: float | None) -> str:
    if value is None:
        return f"{name}: no reachable flip within the search range"
    return f"{name}: flips at {value:.2f}"


def counterfactuals_from_grid(
    inputs: DecisionInputs, base_key: ScenarioKey, settlement: str, chainage_m: float
) -> tuple[Counterfactual, ...]:
    results = []
    for volume in (base_key.volume_mm3 - 1.0, base_key.volume_mm3 + 1.0):
        if volume <= 0:
            continue
        key = ScenarioKey(round(volume, 1), base_key.duration_s, base_key.mode)
        try:
            lead = lead_time_for(settlement, chainage_m, key)
        except FileNotFoundError:
            continue
        new_inputs = DecisionInputs(
            inputs.change_magnitude_z,
            lead.lead_time_minutes,
            inputs.exposure_count,
            inputs.confidence,
            inputs.vetoed,
        )
        new_decision = decide(new_inputs)
        results.append(
            Counterfactual(
                change=f"impounded volume {volume:.1f} Mm3 instead of {base_key.volume_mm3:.1f}",
                new_status=new_decision.status,
                new_lead_time_minutes=lead.lead_time_minutes,
            )
        )
    return tuple(results)


def _what_would_change_my_mind(table: VerificationTable) -> tuple[str, ...]:
    notes: list[str] = []
    for claim in table.claims:
        if claim.veto_reason:
            notes.append(f"vetoed: {claim.statement[:80]} - {claim.veto_reason}")
        elif not claim.contradiction.passed:
            notes.append(
                f"unresolved contradiction on '{claim.statement[:60]}': "
                f"{claim.contradiction.detail}"
            )
        elif not claim.independence.passed:
            notes.append(
                f"a second independent source for '{claim.statement[:60]}' would raise "
                "confidence"
            )
    if not notes:
        notes.append("no open evidence gaps recorded against this ledger")
    return tuple(notes)


def build_evidence_pack(
    ledger: Ledger,
    table: VerificationTable,
    decision: Decision,
    counterfactuals: tuple[Counterfactual, ...],
) -> EvidencePack:
    inputs_flip = flip_points(decision_inputs_from_ledger(ledger, table, "medium"))
    return EvidencePack(
        status=decision.status,
        score=decision.score,
        contributions=tuple(
            _fmt_contribution(c.term, c.raw_value, c.contribution) for c in decision.contributions
        ),
        counterfactuals=counterfactuals,
        flip_point_summary=tuple(_format_flip(k, v) for k, v in inputs_flip.items()),
        what_would_change_my_mind=_what_would_change_my_mind(table),
        provenance_links=tuple(e.ref for e in ledger.evidence),
    )


def _context_sentence(status: Level, vetoed: bool, run_id: str, language: str) -> str:
    prompt = (
        f"Status: {status}. Verifier vetoed the cause claim: {vetoed}. "
        f"Write the one context sentence in {language}."
    )
    try:
        response = gateway.complete(
            EXPLAIN_LANE,
            [
                {"role": "system", "content": CONTEXT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            run_id=run_id,
            use_cache=True,
            max_tokens=80,
        )
        return (response["content"] or "").strip()
    except AllProvidersFailedError:
        return ""


def render_public_note(decision: Decision, vetoed: bool, run_id: str) -> PublicNote:
    status_en = decision.status
    status_np = STATUS_NEPALI[decision.status]
    veto_en = " The system could not confirm the cause and issued no claim." if vetoed else ""
    veto_np = " प्रणालीले कारण पुष्टि गर्न सकेन र कुनै दाबी जारी गरेन।" if vetoed else ""
    facts_en = f"Status: {status_en}.{veto_en}"
    facts_np = f"स्थिति: {status_np}।{veto_np}"
    context_en = _context_sentence(decision.status, vetoed, run_id, "English")
    context_np = _context_sentence(decision.status, vetoed, run_id, "Nepali")
    return PublicNote(
        english=f"{facts_en} {context_en}".strip(),
        nepali=f"{facts_np} {context_np}".strip(),
    )


def render_resident_scripts(
    decision: Decision, settlements: tuple[str, ...]
) -> tuple[ResidentScript, ...]:
    status_np = STATUS_NEPALI[decision.status]
    action_np = STATUS_ACTION_NEPALI[decision.status]
    return tuple(
        ResidentScript(
            settlement=name,
            nepali_text=f"{name}: स्थिति {status_np}। {action_np}",
        )
        for name in settlements
    )


def explain(
    ledger: Ledger,
    table: VerificationTable,
    confidence: Confidence,
    settlements: tuple[str, ...],
    run_id: str,
    *,
    scenario: tuple[ScenarioKey, str, float] | None = None,
) -> ExplainerOutput:
    inputs = decision_inputs_from_ledger(ledger, table, confidence)
    decision = decide(inputs)
    vetoed = table.status == "INSUFFICIENT"
    counterfactuals: tuple[Counterfactual, ...] = ()
    if scenario is not None:
        key, settlement, chainage = scenario
        counterfactuals = counterfactuals_from_grid(inputs, key, settlement, chainage)
    pack = build_evidence_pack(ledger, table, decision, counterfactuals)
    note = render_public_note(decision, vetoed, run_id)
    scripts = render_resident_scripts(decision, settlements)
    return ExplainerOutput(decision, vetoed, pack, note, scripts)
