"""Transparent evidence fusion → 0–100 surface-change anomaly score.

Published weights (docs/DEEP-PROCESSING.md §6) — deliberately simple and
hand-recomputable, matching the SCIENCE-SCOPE philosophy:

    score/100 = 0.25 · moisture_deficit
              + 0.20 · vegetation_stress
              + 0.15 · soil_exposure
              + 0.20 · persistence
              + 0.20 · deep_model_anomaly

Each evidence layer is capped to [0, 1]; the deep-model layer is already a
percentile. Coherence = the share of the five layers agreeing (≥ 0.5). Pixel
confidence classes combine score, coherence and persistence.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

WEIGHTS: Dict[str, float] = {
    "moisture_deficit": 0.25,
    "vegetation_stress": 0.20,
    "soil_exposure": 0.15,
    "persistence": 0.20,
    "deep_model": 0.20,
}

COMPONENT_THRESHOLD = 0.5  # a layer "agrees" when it exceeds this


def _cap01(x: np.ndarray) -> np.ndarray:
    return np.clip(np.nan_to_num(x, nan=0.0), 0.0, 1.0).astype(np.float32)


def fuse(evidence: Dict[str, np.ndarray], deep_map: np.ndarray) -> Dict[str, np.ndarray]:
    """Build the fused 0–100 score plus all diagnostic layers.

    Sign convention: moisture/vegetation anomalies are NEGATIVE z (deficit,
    stress) — so the evidence layers use −z; soil exposure is POSITIVE z.
    """
    moisture = _cap01(-evidence["z_ndmi"] / 3.0)
    vegetation = _cap01(-evidence["z_ndvi"] / 3.0)
    soil = _cap01(evidence["z_bsi"] / 3.0)
    persistence = _cap01(evidence["persistence"])
    deep = _cap01(deep_map)

    fused = (
        WEIGHTS["moisture_deficit"] * moisture
        + WEIGHTS["vegetation_stress"] * vegetation
        + WEIGHTS["soil_exposure"] * soil
        + WEIGHTS["persistence"] * persistence
        + WEIGHTS["deep_model"] * deep
    )
    score100 = (fused * 100.0).astype(np.float32)

    layers = (moisture, vegetation, soil, persistence, deep)
    agree = _cap01(sum((l >= COMPONENT_THRESHOLD).astype(np.float32) for l in layers) / 5.0)

    return {
        "score_0_100": score100,
        "coherence": agree,
        "layers": {
            "moisture_deficit": moisture,
            "vegetation_stress": vegetation,
            "soil_exposure": soil,
            "persistence": persistence,
            "deep_model": deep,
        },
    }


def confidence_classes(
    score: np.ndarray, coherence: np.ndarray, persistence: np.ndarray
) -> np.ndarray:
    """uint8 class map: 0 background, 1 low, 2 medium, 3 high."""
    cls = np.zeros(score.shape, dtype=np.uint8)
    cls[(score >= 35)] = 1
    cls[(score >= 50) & (coherence >= 0.4)] = 2
    cls[(score >= 65) & (coherence >= 0.6) & (persistence >= 0.5)] = 3
    return cls


CONFIDENCE_NAMES = {0: "background", 1: "low", 2: "medium", 3: "high"}


def classify_component(
    mean_score: float, mean_coherence: float, mean_persistence: float, pixels: int
) -> str:
    """Component-level confidence (min-pixel rule applied by the caller)."""
    if mean_score >= 65 and mean_coherence >= 0.6 and mean_persistence >= 0.5 and pixels >= 9:
        return "high"
    if mean_score >= 50 and mean_coherence >= 0.4 and pixels >= 9:
        return "medium"
    if mean_score >= 35 and pixels >= 9:
        return "low"
    return "background"
