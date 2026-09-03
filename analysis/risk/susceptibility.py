from __future__ import annotations

from functools import lru_cache

from analysis.risk.base_rates import base_rate_by_dam_type, pdgl_inventory, relative_dam_weight
from analysis.risk.observability import ATTENTION_THRESHOLD_KM2, DETECTION_LIMIT_KM2
from analysis.risk.schemas import (
    BaseRate,
    DamType,
    ParameterValue,
    SusceptibilityBand,
    SusceptibilityScore,
)

FRAMEWORKS: tuple[str, ...] = (
    "Rounce et al. 2016, HESS 20:3455, hazard parameter framework",
    "ICIMOD/UNDP 2020 potentially dangerous glacial lake methodology",
    "empirical base rates joined from HMAGLOFDB against the ICIMOD 2015 inventory",
)

RANKING_CAVEATS: tuple[str, ...] = (
    "this is a relative ranking against other inventoried lakes, not a probability of failure",
    "no output states or implies that a specific lake will fail, or when",
    "parameters that cannot be observed are reported as unobserved and excluded from the "
    "score rather than assumed benign",
    "the DEM predates any recent event and downstream terms are computed on it",
)

GROUP_WEIGHTS: dict[str, float] = {
    "dam": 0.30,
    "lake": 0.25,
    "trigger": 0.20,
    "conditioning": 0.10,
    "downstream": 0.15,
}

BAND_EDGES: tuple[tuple[float, SusceptibilityBand], ...] = (
    (0.75, "very_high"),
    (0.55, "high"),
    (0.35, "moderate"),
    (0.0, "low"),
)

INVENTORY_TYPE_TO_DAM: dict[str, DamType] = {
    "M(o)": "moraine",
    "M(e)": "moraine",
    "M(l)": "moraine",
    "I(s)": "ice",
    "I(v)": "ice",
    "E(o)": "bedrock",
    "E(c)": "bedrock",
    "O": "unknown",
}


def _normalise(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _dam_parameters(dam_type: DamType) -> list[ParameterValue]:
    return [
        ParameterValue(
            name="dam_type",
            group="dam",
            value=relative_dam_weight(dam_type),
            unit="relative base-rate weight",
            source="HMAGLOFDB x ICIMOD 2015 empirical rate",
            note=f"classified as {dam_type}",
        ),
        ParameterValue(
            name="freeboard",
            group="dam",
            value=None,
            unit="m",
            source="requires field survey or sub-metre stereo imagery",
            observable=False,
            note="not observable from the layers this system holds",
        ),
        ParameterValue(
            name="width_to_height_ratio",
            group="dam",
            value=None,
            unit="ratio",
            source="requires dam crest geometry",
            observable=False,
        ),
        ParameterValue(
            name="ice_core_present",
            group="dam",
            value=None,
            unit="boolean",
            source="requires ground-penetrating survey",
            observable=False,
        ),
    ]


def _lake_parameters(area_km2: float, elevation_m: float) -> list[ParameterValue]:
    return [
        ParameterValue(
            name="lake_area",
            group="lake",
            value=_normalise(area_km2, ATTENTION_THRESHOLD_KM2, 2.0),
            unit="km2",
            source="ICIMOD 2015 inventory",
            note=f"{area_km2:.4f} km2",
        ),
        ParameterValue(
            name="elevation",
            group="lake",
            value=_normalise(elevation_m, 3500.0, 5600.0),
            unit="m",
            source="ICIMOD 2015 inventory",
            note=f"{elevation_m:.0f} m",
        ),
        ParameterValue(
            name="area_change_rate",
            group="lake",
            value=None,
            unit="km2/yr",
            source="requires a multi-date series at this lake",
            observable=False,
        ),
        ParameterValue(
            name="glacier_terminus_contact",
            group="lake",
            value=None,
            unit="boolean",
            source="requires terminus delineation at this lake",
            observable=False,
        ),
    ]


def _context_parameters() -> list[ParameterValue]:
    return [
        ParameterValue(
            name="slope_above_lake",
            group="trigger",
            value=None,
            unit="degrees",
            source="computable from the HMA DEM where the lake falls inside tile coverage",
            observable=False,
        ),
        ParameterValue(
            name="recent_mass_movement",
            group="trigger",
            value=None,
            unit="boolean",
            source="OPERA DIST-ALERT-HLS, cloud limited",
            observable=False,
        ),
        ParameterValue(
            name="temperature_anomaly",
            group="conditioning",
            value=None,
            unit="sigma",
            source="conditioning factor only, not a trigger",
            observable=False,
        ),
        ParameterValue(
            name="distance_to_first_settlement",
            group="downstream",
            value=None,
            unit="m",
            source="requires routing from this lake, held only for watched corridors",
            observable=False,
        ),
    ]


def _score_from(parameters: list[ParameterValue]) -> float:
    totals: dict[str, list[float]] = {}
    for parameter in parameters:
        if parameter.value is None or not parameter.observable:
            continue
        totals.setdefault(parameter.group, []).append(parameter.value)
    weighted = 0.0
    available = 0.0
    for group, weight in GROUP_WEIGHTS.items():
        values = totals.get(group)
        if not values:
            continue
        weighted += weight * (sum(values) / len(values))
        available += weight
    if available <= 0:
        return 0.0
    return weighted / available


def _band(score: float, observed_groups: int) -> SusceptibilityBand:
    if observed_groups == 0:
        return "not_assessable"
    for edge, band in BAND_EDGES:
        if score >= edge:
            return band
    return "low"


def score_lake(
    node_id: str, dam_type: DamType, area_km2: float, elevation_m: float
) -> SusceptibilityScore:
    parameters = (
        _dam_parameters(dam_type)
        + _lake_parameters(area_km2, elevation_m)
        + _context_parameters()
    )
    score = _score_from(parameters)
    observed = {p.group for p in parameters if p.value is not None and p.observable}
    rates: list[BaseRate] = []
    rate = base_rate_by_dam_type().get(dam_type)
    if rate is not None:
        rates.append(rate)
    unobservable = tuple(p.name for p in parameters if not p.observable)
    caveats = RANKING_CAVEATS
    if area_km2 <= DETECTION_LIMIT_KM2:
        caveats = (*caveats, "this lake sits at or below the detection limit")
    return SusceptibilityScore(
        node_id=node_id,
        rank_score=score,
        band=_band(score, len(observed)),
        parameters=tuple(parameters),
        base_rates=tuple(rates),
        unobservable_parameters=unobservable,
        frameworks=FRAMEWORKS,
        caveats=caveats,
    )


@lru_cache(maxsize=1)
def rank_pdgls() -> tuple[SusceptibilityScore, ...]:
    frame = pdgl_inventory()
    scored = [
        score_lake(
            str(row.GL_ID),
            INVENTORY_TYPE_TO_DAM.get(str(row.Type), "unknown"),
            float(row.Area),
            float(row.Elevation),
        )
        for row in frame.itertuples()
    ]
    return tuple(sorted(scored, key=lambda item: item.rank_score, reverse=True))


def susceptibility_at(node_id: str) -> SusceptibilityScore | None:
    return next((score for score in rank_pdgls() if score.node_id == node_id), None)
