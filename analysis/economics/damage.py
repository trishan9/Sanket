from __future__ import annotations

from dataclasses import dataclass

NPR_PER_USD = 141.0

UNIT_COST_SOURCES: tuple[str, ...] = (
    "building replacement cost band from Nepal NRA post-2015-earthquake reconstruction "
    "grant tiers, inflated to present and reported as a range",
    "bridge replacement cost band from Nepal Department of Roads standard bridge norms",
    "road reinstatement cost band from Nepal Department of Roads district road norms",
)

NOT_MONETISED = (
    "loss of life, injury, displacement and livelihood loss are not monetised here; they "
    "are the real costs of this hazard and no figure below represents them"
)

DAMAGE_CAVEATS: tuple[str, ...] = (
    NOT_MONETISED,
    "unit costs are national bands, not location-specific valuations",
    "exposure counts come from modelled population and mapped building footprints, which "
    "under-count informal and recently built structures",
    "depth-damage fractions are generic curves, not calibrated to Nepali hill construction",
    "the DEM predates the event, so modelled depths carry that error into every figure",
)

BUILDING_COST_NPR = (900_000.0, 2_400_000.0)
BRIDGE_COST_NPR = (35_000_000.0, 120_000_000.0)

DEPTH_DAMAGE_FRACTION: tuple[tuple[float, float, float], ...] = (
    (0.0, 0.5, 0.05),
    (0.5, 1.0, 0.18),
    (1.0, 2.0, 0.40),
    (2.0, 3.0, 0.62),
    (3.0, 1000.0, 0.85),
)


@dataclass(frozen=True)
class DamageRange:
    settlement: str
    depth_m: float
    buildings_exposed: int
    bridges_exposed: int
    damage_fraction: float
    low_npr: float
    high_npr: float
    assumptions: tuple[str, ...]
    caveats: tuple[str, ...]

    @property
    def low_usd(self) -> float:
        return self.low_npr / NPR_PER_USD

    @property
    def high_usd(self) -> float:
        return self.high_npr / NPR_PER_USD

    def rendered(self) -> str:
        return (
            f"{self.settlement}: modelled direct asset damage NPR "
            f"{self.low_npr / 1e6:.1f}-{self.high_npr / 1e6:.1f} million "
            f"(USD {self.low_usd / 1e6:.2f}-{self.high_usd / 1e6:.2f} million) at "
            f"{self.depth_m:.1f} m modelled depth. {NOT_MONETISED}."
        )


def damage_fraction_for_depth(depth_m: float) -> float:
    for low, high, fraction in DEPTH_DAMAGE_FRACTION:
        if low <= depth_m < high:
            return fraction
    return DEPTH_DAMAGE_FRACTION[-1][2]


def estimate_damage(
    settlement: str, depth_m: float, buildings: int, bridges: int
) -> DamageRange:
    fraction = damage_fraction_for_depth(depth_m)
    low = buildings * BUILDING_COST_NPR[0] * fraction + bridges * BRIDGE_COST_NPR[0]
    high = buildings * BUILDING_COST_NPR[1] * fraction + bridges * BRIDGE_COST_NPR[1]
    assumptions = (
        f"depth-damage fraction {fraction:.2f} applied at {depth_m:.1f} m modelled depth",
        f"building replacement NPR {BUILDING_COST_NPR[0]:,.0f}-{BUILDING_COST_NPR[1]:,.0f}",
        f"bridge replacement NPR {BRIDGE_COST_NPR[0]:,.0f}-{BRIDGE_COST_NPR[1]:,.0f}",
        "bridges are treated as lost outright rather than depth-scaled",
        f"NPR per USD {NPR_PER_USD:.0f}",
    )
    return DamageRange(
        settlement=settlement,
        depth_m=depth_m,
        buildings_exposed=buildings,
        bridges_exposed=bridges,
        damage_fraction=fraction,
        low_npr=low,
        high_npr=high,
        assumptions=assumptions + UNIT_COST_SOURCES,
        caveats=DAMAGE_CAVEATS,
    )
