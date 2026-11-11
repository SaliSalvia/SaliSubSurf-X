"""Transparent, documented fusion of terrain indicators into a 0–1 score.

This is a **surface terrain-shape anomaly score**, not a probability of a buried
target. The weights and normalisation anchors below are fixed, published here, and
deliberately simple so that any reviewer can reproduce the number.
"""

from __future__ import annotations

from typing import Dict

# Component weights — must sum to 1.0 (documented in docs/SCIENCE-SCOPE.md).
WEIGHTS: Dict[str, float] = {
    "slope_variability": 0.30,
    "roughness": 0.30,
    "gradient_consistency": 0.25,
    "relief": 0.15,
}

# Normalisation anchors (indicator value that maps to a normalised 1.0).
ANCHOR_STD_SLOPE_DEG = 8.0
ANCHOR_TRI_M = 15.0
ANCHOR_RELIEF_M = 300.0


def _cap01(x: float) -> float:
    return max(0.0, min(1.0, x))


def surface_anomaly_score(result: Dict) -> Dict:
    """Add ``surface_anomaly_score`` and ``score_components`` to a terrain result dict."""
    slope = result.get("slope", {})
    consistency = result.get("gradient_consistency")
    elev = result.get("elevation", {})

    std_slope = float(slope.get("std_deg", 0.0))
    tri_mean = float(result.get("roughness_tri_mean", 0.0))
    relief = float(elev.get("max_m", 0.0)) - float(elev.get("min_m", 0.0))

    components = {
        "slope_variability": round(_cap01(std_slope / ANCHOR_STD_SLOPE_DEG), 4),
        "roughness": round(_cap01(tri_mean / ANCHOR_TRI_M), 4),
        "gradient_consistency": round(_cap01(float(consistency or 0.0)), 4),
        "relief": round(_cap01(relief / ANCHOR_RELIEF_M), 4),
    }
    score = round(sum(WEIGHTS[k] * v for k, v in components.items()), 4)
    return {
        "surface_anomaly_score": score,
        "score_components": components,
        "score_definition": (
            "Weighted mean of documented surface-shape components; see "
            "docs/SCIENCE-SCOPE.md. Surface indicator only — NOT a buried-target "
            "probability."
        ),
    }
