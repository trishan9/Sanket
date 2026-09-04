from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "board"
COMPONENTS = BOARD / "components"
CAUSAL_GRAPH = COMPONENTS / "awareness" / "CausalGraph.tsx"

BANNER_FRAGMENT = "not an attribution of any specific flood"

ATTRIBUTION_PATTERNS: tuple[str, ...] = (
    r"was caused by",
    r"were caused by",
    r"caused the (flood|outburst|disaster|event)",
    r"climate change caused",
    r"warming caused",
    r"attributable to",
    r"killed people here",
)

NEGATORS: tuple[str, ...] = ("not ", "never", "no ", "rather than", "whether", "question for")


def _tsx_files() -> list[Path]:
    return sorted(BOARD.rglob("*.tsx"))


def _strings_in(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rendered_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    joined = re.sub(r'"\s*\+\s*"', "", raw)
    return re.sub(r"\s+", " ", joined)


def test_causal_graph_carries_the_non_attribution_banner() -> None:
    text = _rendered_text(CAUSAL_GRAPH)
    assert BANNER_FRAGMENT in text
    assert "dedicated" in text and "attribution study" in text


def test_banner_renders_unconditionally_on_every_view() -> None:
    text = _strings_in(CAUSAL_GRAPH)
    body = text.split("export function CausalGraph()", 1)[1]
    assert "NON_ATTRIBUTION_BANNER" in body
    banner_line = next(
        line for line in body.splitlines() if "NON_ATTRIBUTION_BANNER" in line
    )
    assert "&&" not in banner_line
    assert "?" not in banner_line


def test_no_rendered_string_attributes_a_specific_event_to_a_specific_cause() -> None:
    offenders: list[str] = []
    for path in _tsx_files():
        lowered = _rendered_text(path).lower()
        for pattern in ATTRIBUTION_PATTERNS:
            for match in re.finditer(pattern, lowered):
                window = lowered[max(0, match.start() - 70) : match.start()]
                if any(negator in window for negator in NEGATORS):
                    continue
                offenders.append(f"{path.relative_to(ROOT)}: {pattern!r}")
    assert not offenders, "dashboard attributed a specific event to a cause:\n" + "\n".join(
        offenders
    )


def test_the_contested_edge_is_present_and_labelled_contested() -> None:
    text = _strings_in(CAUSAL_GRAPH)
    assert "More frequent GLOFs" in text
    contested_block = text.split("More frequent GLOFs", 1)[1][:400]
    assert '"contested"' in contested_block
    assert "Veh et al" in contested_block


def test_every_risk_capability_is_visible_in_a_dashboard() -> None:
    gov = _strings_in(BOARD / "app" / "gov" / "page.tsx")
    for component in (
        "SusceptibilityPanel",
        "CascadeGraph",
        "ScenarioMatrix",
        "ValidationPanel",
        "CompletenessHeatmap",
        "SimulationControl",
        "CausalGraph",
    ):
        assert component in gov, f"{component} is not mounted on /gov"
    public = _strings_in(BOARD / "app" / "page.tsx")
    for component in ("AmISafe", "MeasuresPanel", "CausalGraph"):
        assert component in public, f"{component} is not mounted on the public board"


def test_scenarios_are_watermarked_and_never_styled_as_observations() -> None:
    for name in ("risk/ScenarioMatrix.tsx", "risk/CascadeGraph.tsx", "sim/SimulationControl.tsx"):
        text = _strings_in(COMPONENTS / name)
        assert "SCENARIO" in text, f"{name} does not watermark its scenario output"


def test_susceptibility_panel_states_it_is_not_a_probability() -> None:
    text = _rendered_text(COMPONENTS / "risk" / "SusceptibilityPanel.tsx")
    assert "Not a probability of failure" in text
    assert "never a statement of when any lake may fail" in text
