from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rasterio.enums import Resampling
from rasterio.warp import reproject

from core.provenance import EvidenceRef

MIN_DETECTORS_FOR_AGREEMENT = 2


@dataclass(frozen=True)
class DetectorMask:
    independence_group: str
    water_mask: np.ndarray
    transform: object
    crs: str


@dataclass(frozen=True)
class AgreementRaster:
    concordance: np.ndarray
    n_detectors: int
    reference_transform: object
    reference_crs: str
    independence_groups: tuple[str, ...]

    def confidence_at(self, row: int, col: int) -> str:
        count = int(self.concordance[row, col])
        if count >= self.n_detectors:
            return "high"
        if count >= MIN_DETECTORS_FOR_AGREEMENT:
            return "medium"
        if count == 1:
            return "low"
        return "none"


def _resample_mask(
    mask: DetectorMask,
    reference_transform: object,
    reference_shape: tuple[int, int],
    reference_crs: str,
) -> np.ndarray:
    destination = np.zeros(reference_shape, dtype=np.uint8)
    reproject(
        source=mask.water_mask.astype(np.uint8),
        destination=destination,
        src_transform=mask.transform,
        src_crs=mask.crs,
        dst_transform=reference_transform,
        dst_crs=reference_crs,
        resampling=Resampling.nearest,
    )
    return destination.astype(bool)


def build_agreement(masks: list[DetectorMask], reference_index: int = 0) -> AgreementRaster:
    if not masks:
        raise ValueError("at least one detector mask is required")
    reference = masks[reference_index]
    shape = reference.water_mask.shape
    concordance = np.zeros(shape, dtype=np.int16)
    groups = []
    for mask in masks:
        aligned = (
            mask.water_mask
            if mask is reference
            else _resample_mask(mask, reference.transform, shape, reference.crs)
        )
        concordance += aligned.astype(np.int16)
        groups.append(mask.independence_group)
    return AgreementRaster(
        concordance=concordance,
        n_detectors=len(masks),
        reference_transform=reference.transform,
        reference_crs=reference.crs,
        independence_groups=tuple(groups),
    )


def independence_refs(raster: AgreementRaster) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(
            ref=f"agreement_{group}",
            source=group,
            independence_group=group,
            claim_type="observation",
        )
        for group in raster.independence_groups
    )
