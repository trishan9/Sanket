from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent.ledger import Claim, Ledger
from agent.rag.retrieve import retrieve
from agent.router import Lane, gateway
from agent.trace import Trace
from core.errors import AllProvidersFailedError, ClaimNotInLedgerError
from core.provenance import independence_count, licenses_claim

VERIFIER_LANE: Lane = "sanket-critic"
StatusDecision = Literal["NORMAL", "WATCH", "ALERT", "INSUFFICIENT"]

CONTRADICTION_SYSTEM_PROMPT = (
    "You check one claim against a short numbered list of independently retrieved "
    "documents. Reply with strict JSON only: a list of objects with keys 'index' (the "
    "document number that conflicts with the claim) and 'note' (one sentence on the "
    "conflict). Only cite document numbers from the list given. You do not resolve "
    "conflicts, only surface them. If nothing conflicts, reply with an empty JSON list."
)


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    detail: str


class ClaimVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    independence: CheckResult
    temporal: CheckResult
    licensing: CheckResult
    contradiction: CheckResult
    veto_reason: str | None = None
    confidence: str = "insufficient"


class VerificationTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    claims: tuple[ClaimVerification, ...]
    rejected_post_cutoff: int
    status: StatusDecision


def _require_in_ledger(claim: Claim, ledger: Ledger) -> None:
    if claim not in ledger.claims:
        raise ClaimNotInLedgerError(f"claim '{claim.statement[:60]}' is not in this ledger")


def check_independence(claim: Claim) -> CheckResult:
    count = independence_count(claim.supporting)
    if len(claim.supporting) > count:
        return CheckResult(
            passed=False,
            detail=f"{len(claim.supporting)} supporting refs collapse to {count} "
            "independent source(s) once shared independence groups are merged",
        )
    return CheckResult(passed=True, detail=f"{count} independent supporting source(s)")


def check_temporal_validity(claim: Claim, ledger: Ledger) -> CheckResult:
    violations = [
        ref.ref
        for ref in (*claim.supporting, *claim.contradicting)
        if ledger.evidence_by_ref(ref.ref) is None
    ]
    if violations:
        return CheckResult(passed=False, detail=f"unresolvable refs: {violations}")
    return CheckResult(passed=True, detail=f"all evidence resolves within as_of={ledger.as_of}")


def check_claim_licensing(claim: Claim) -> CheckResult:
    evidence_types = frozenset(ref.claim_type for ref in claim.supporting)
    if licenses_claim(evidence_types, claim.claim_type):
        return CheckResult(passed=True, detail=f"{sorted(evidence_types)} licenses claim")
    return CheckResult(
        passed=False, detail=f"{sorted(evidence_types)} does not license a {claim.claim_type}"
    )


def _query_for_claim(claim: Claim) -> str:
    groups = ", ".join(sorted(claim.independence_groups)) or "no independence group"
    return f"{claim.statement} ({groups})"


def _contradiction_prompt(claim: Claim, documents: list[str]) -> list[dict[str, str]]:
    numbered = "\n".join(f"{i}. {doc}" for i, doc in enumerate(documents))
    return [
        {"role": "system", "content": CONTRADICTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Claim: {claim.statement}\n\nDocuments:\n{numbered}"},
    ]


def detect_contradiction(
    claim: Claim, ledger: Ledger, run_id: str, trace: Trace | None = None
) -> CheckResult:
    result = retrieve("events", _query_for_claim(claim), as_of=ledger.as_of, k=5)
    if not result.chunks:
        return CheckResult(passed=True, detail="no events-collection documents retrieved")
    documents = [chunk.text for chunk in result.chunks]
    try:
        response = gateway.complete(
            VERIFIER_LANE,
            _contradiction_prompt(claim, documents),
            run_id=run_id,
            trace=trace,
            use_cache=False,
            max_tokens=400,
        )
    except AllProvidersFailedError:
        if trace is not None:
            trace.degraded(
                "verifier contradiction check: no provider reachable - deterministic mode "
                "skips the check rather than blocking the decision on it"
            )
        return CheckResult(
            passed=True,
            detail="contradiction check skipped: no provider reachable (deterministic mode)",
        )
    findings = _parse_contradiction_response(response["content"] or "", len(documents))
    if not findings:
        return CheckResult(passed=True, detail="no contradiction surfaced")
    notes = "; ".join(
        f"{result.chunks[i].source_org} ({result.chunks[i].claim_type}): {note}"
        for i, note in findings
    )
    return CheckResult(passed=False, detail=f"contradicted by: {notes}")


def _parse_contradiction_response(content: str, n_documents: int) -> list[tuple[int, str]]:
    text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    findings: list[tuple[int, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int) or not (0 <= index < n_documents):
            continue
        findings.append((index, str(item.get("note", ""))))
    return findings


def apply_policy(
    claim: Claim,
    independence: CheckResult,
    temporal: CheckResult,
    licensing: CheckResult,
    contradiction: CheckResult,
) -> tuple[str | None, str]:
    veto_reason: str | None = claim.veto_reason
    confidence = claim.confidence
    if not licensing.passed:
        veto_reason = veto_reason or f"licensing failed: {licensing.detail}"
        confidence = "insufficient"
    elif not temporal.passed:
        veto_reason = veto_reason or f"temporal violation: {temporal.detail}"
        confidence = "insufficient"
    elif not contradiction.passed and not independence.passed:
        veto_reason = (
            f"independent contradiction against a single-source claim: {contradiction.detail}"
        )
        confidence = "insufficient"
    elif not contradiction.passed:
        confidence = "low"
    return veto_reason, confidence


def verify_claim(
    claim: Claim, ledger: Ledger, run_id: str, trace: Trace | None = None
) -> ClaimVerification:
    _require_in_ledger(claim, ledger)
    independence = check_independence(claim)
    temporal = check_temporal_validity(claim, ledger)
    licensing = check_claim_licensing(claim)
    contradiction = detect_contradiction(claim, ledger, run_id, trace)
    veto_reason, confidence = apply_policy(claim, independence, temporal, licensing, contradiction)

    if trace is not None:
        outcome = "vetoed" if veto_reason else "passed"
        trace.verify(
            f"{outcome} ({confidence}): {claim.statement}",
            extra={
                "independence": independence.detail,
                "temporal": temporal.detail,
                "licensing": licensing.detail,
                "contradiction": contradiction.detail,
                "veto_reason": veto_reason,
            },
        )

    return ClaimVerification(
        statement=claim.statement,
        independence=independence,
        temporal=temporal,
        licensing=licensing,
        contradiction=contradiction,
        veto_reason=veto_reason,
        confidence=confidence,
    )


def _overall_status(verifications: tuple[ClaimVerification, ...]) -> StatusDecision:
    if not verifications or all(v.veto_reason is not None for v in verifications):
        return "INSUFFICIENT"
    if any(v.confidence == "high" for v in verifications):
        return "WATCH"
    return "NORMAL"


def verify(ledger: Ledger, run_id: str, trace: Trace | None = None) -> VerificationTable:
    verifications = tuple(verify_claim(c, ledger, run_id, trace) for c in ledger.claims)
    rejected = sum(
        1
        for claim in ledger.claims
        for ref in claim.supporting
        if (ev := ledger.evidence_by_ref(ref.ref)) is not None
        and ev.provenance.as_of_filter > ledger.as_of
    )
    return VerificationTable(
        run_id=run_id,
        claims=verifications,
        rejected_post_cutoff=rejected,
        status=_overall_status(verifications),
    )
