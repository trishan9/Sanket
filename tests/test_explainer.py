from __future__ import annotations

import re
from datetime import date

import pytest

from agent.decision import DecisionInputs, decide
from agent.explainer import (
    STATUS_NEPALI,
    build_evidence_pack,
    counterfactuals_from_grid,
    decision_inputs_from_ledger,
    explain,
)
from agent.ledger import Ledger
from agent.verifier import verify
from analysis.exposure.leadtime import lead_time_for
from analysis.hydro.scenarios import ScenarioKey
from core.provenance import Evidence, Provenance

CORRIDOR_CHAINAGE_M = 20000.0
SETTLEMENT = "Timure"


def _contested_ledger() -> Ledger:
    ledger = Ledger("test_explainer", date(2026, 9, 3))
    dhm = ledger.add(
        Evidence(
            value={"cause": "supraglacial lake outburst"},
            provenance=Provenance(
                source="DHM",
                method="satellite imagery review",
                as_of_filter=ledger.as_of,
                independence_group="dhm_icimod_imagery",
            ),
            claim_type="observation",
        )
    )
    icimod = ledger.add(
        Evidence(
            value={"cause": "supraglacial lake outburst"},
            provenance=Provenance(
                source="ICIMOD",
                method="satellite imagery cross-check",
                as_of_filter=ledger.as_of,
                independence_group="dhm_icimod_imagery",
            ),
            claim_type="observation",
        )
    )
    ledger.propose_claim(
        "The 26 August 2026 Lhende event was a supraglacial lake outburst flood.",
        "observation",
        [dhm.ref, icimod.ref],
    )
    return ledger


def _clean_ledger_with_scenario() -> tuple[Ledger, ScenarioKey]:
    ledger = Ledger("test_explainer_clean", date(2026, 9, 3))
    key = ScenarioKey(2.0, 30 * 60.0, "full")
    lead = lead_time_for(SETTLEMENT, CORRIDOR_CHAINAGE_M, key)
    ledger.add(
        Evidence(
            value={"z": 3.4},
            provenance=Provenance(
                source="OPERA DSWx-S1", method="z-score", as_of_filter=ledger.as_of
            ),
            claim_type="observation",
        )
    )
    ledger.add(
        Evidence(
            value={"fastest_arrival_minutes": lead.lead_time_minutes},
            provenance=Provenance(
                source="scenario grid", method="lookup", as_of_filter=ledger.as_of
            ),
            claim_type="scenario",
        )
    )
    ledger.add(
        Evidence(
            value={"population": 916},
            provenance=Provenance(source="WorldPop", method="mask sum", as_of_filter=ledger.as_of),
            claim_type="model_output",
        )
    )
    ledger.propose_claim("water observed above baseline", "observation", [ledger.evidence[0].ref])
    return ledger, key


def test_decision_inputs_extracted_from_ledger_evidence() -> None:
    from agent.verifier import VerificationTable

    ledger, _ = _clean_ledger_with_scenario()
    table = VerificationTable(run_id="x", claims=(), rejected_post_cutoff=0, status="WATCH")
    inputs = decision_inputs_from_ledger(ledger, table, "medium")
    assert inputs.change_magnitude_z == 3.4
    assert inputs.exposure_count == 916
    assert inputs.min_lead_time_minutes is not None


@pytest.mark.network
def test_attribution_matches_direct_decision_computation() -> None:
    ledger, key = _clean_ledger_with_scenario()
    table = verify(ledger, "test_explainer_clean")
    output = explain(ledger, table, "medium", (SETTLEMENT,), "test_explainer_clean")
    inputs = decision_inputs_from_ledger(ledger, table, "medium")
    direct = decide(inputs)
    assert output.decision.status == direct.status
    assert abs(output.decision.score - direct.score) < 1e-9
    formatted = {c.split(" contribution ")[0] for c in output.evidence_pack.contributions}
    assert formatted == {c.term + " " + c.raw_value for c in direct.contributions}


def test_counterfactuals_match_a_direct_grid_lookup() -> None:
    inputs = DecisionInputs(3.4, 20.0, 916, "medium", False)
    key = ScenarioKey(2.0, 30 * 60.0, "full")
    counterfactuals = counterfactuals_from_grid(inputs, key, SETTLEMENT, CORRIDOR_CHAINAGE_M)
    assert counterfactuals
    for cf in counterfactuals:
        match = re.search(r"volume (\d+\.\d) Mm3", cf.change)
        assert match is not None
        volume = float(match.group(1))
        direct_key = ScenarioKey(volume, key.duration_s, key.mode)
        direct_lead = lead_time_for(SETTLEMENT, CORRIDOR_CHAINAGE_M, direct_key)
        assert cf.new_lead_time_minutes == direct_lead.lead_time_minutes


@pytest.mark.network
def test_verifier_veto_appears_in_all_three_registers() -> None:
    ledger = _contested_ledger()
    table = verify(ledger, "test_explainer_veto")
    output = explain(ledger, table, "medium", ("Timure", "Syapru Besi"), "test_explainer_veto")
    assert output.vetoed is True
    assert output.decision.status == "INSUFFICIENT"
    assert "INSUFFICIENT" in output.public_note.english
    assert STATUS_NEPALI["INSUFFICIENT"] in output.public_note.nepali
    for script in output.scripts:
        assert STATUS_NEPALI["INSUFFICIENT"] in script.nepali_text


@pytest.mark.network
def test_no_evidence_ref_in_rendering_is_absent_from_the_ledger() -> None:
    ledger, key = _clean_ledger_with_scenario()
    table = verify(ledger, "test_explainer_clean")
    output = explain(ledger, table, "medium", (SETTLEMENT,), "test_explainer_clean")
    known_refs = {e.ref for e in ledger.evidence}
    for ref in output.evidence_pack.provenance_links:
        assert ref in known_refs


def test_evidence_pack_is_pure_python_no_network_needed() -> None:
    from agent.verifier import VerificationTable

    ledger, _ = _clean_ledger_with_scenario()
    table = VerificationTable(run_id="x", claims=(), rejected_post_cutoff=0, status="WATCH")
    inputs = DecisionInputs(3.4, 20.0, 916, "medium", False)
    decision = decide(inputs)
    pack = build_evidence_pack(ledger, table, decision, ())
    assert pack.status == decision.status
    assert len(pack.contributions) == 4
