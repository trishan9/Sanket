from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.errors import ClaimNotInLedgerError, StepLimitReachedError
from core.provenance import ClaimType, Evidence, EvidenceRef, independence_count, licenses_claim

Confidence = Literal["high", "medium", "low", "insufficient"]


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    claim_type: ClaimType
    supporting: tuple[EvidenceRef, ...] = ()
    contradicting: tuple[EvidenceRef, ...] = ()
    independence_groups: frozenset[str] = frozenset()
    confidence: Confidence = "insufficient"
    veto_reason: str | None = None

    @property
    def vetoed(self) -> bool:
        return self.veto_reason is not None


class LedgerOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    concluded: bool
    escalated: bool
    summary: str | None = None
    escalation_reason: str | None = None


class Ledger:
    def __init__(self, run_id: str, as_of: date) -> None:
        self.run_id = run_id
        self.as_of = as_of
        self.evidence: list[Evidence] = []
        self.claims: list[Claim] = []
        self._outcome: LedgerOutcome | None = None
        self.started_at = datetime.now(UTC)

    def add(self, evidence: Evidence) -> Evidence:
        self.evidence.append(evidence)
        return evidence

    def evidence_by_ref(self, ref: str) -> Evidence | None:
        return next((e for e in self.evidence if e.ref == ref), None)

    def known_statements(self) -> frozenset[str]:
        return frozenset(e.value.get("statement", "") for e in self.evidence) | frozenset(
            c.statement for c in self.claims
        )

    def propose_claim(
        self,
        statement: str,
        claim_type: ClaimType,
        supporting_refs: list[str],
        *,
        contradicting_refs: list[str] | None = None,
    ) -> Claim:
        supporting = tuple(self._resolve_ref(ref) for ref in supporting_refs)
        contradicting = tuple(self._resolve_ref(ref) for ref in contradicting_refs or [])
        evidence_types = frozenset(ref.claim_type for ref in supporting)
        if not licenses_claim(evidence_types, claim_type):
            claim = Claim(
                statement=statement,
                claim_type=claim_type,
                supporting=supporting,
                contradicting=contradicting,
                confidence="insufficient",
                veto_reason=f"evidence types {sorted(evidence_types)} do not license a "
                f"{claim_type} claim",
            )
        else:
            claim = Claim(
                statement=statement,
                claim_type=claim_type,
                supporting=supporting,
                contradicting=contradicting,
                independence_groups=frozenset(
                    ref.independence_group for ref in supporting if ref.independence_group
                ),
                confidence="medium",
            )
        self.claims.append(claim)
        return claim

    def _resolve_ref(self, ref: str) -> EvidenceRef:
        evidence = self.evidence_by_ref(ref)
        if evidence is None:
            raise ClaimNotInLedgerError(f"evidence ref {ref} is not in this ledger")
        return EvidenceRef(
            ref=evidence.ref,
            source=evidence.provenance.source,
            independence_group=evidence.provenance.independence_group,
            claim_type=evidence.claim_type,
        )

    def conclude(self, summary: str | None) -> LedgerOutcome:
        self._outcome = LedgerOutcome(concluded=True, escalated=False, summary=summary)
        return self._outcome

    def escalate(self, _call: object, reason: str) -> LedgerOutcome:
        self._outcome = LedgerOutcome(concluded=False, escalated=True, escalation_reason=reason)
        return self._outcome

    @property
    def outcome(self) -> LedgerOutcome:
        if self._outcome is None:
            raise StepLimitReachedError("ledger has no outcome yet")
        return self._outcome

    def independence_summary(self) -> dict[str, int]:
        return {claim.statement[:40]: independence_count(claim.supporting) for claim in self.claims}
