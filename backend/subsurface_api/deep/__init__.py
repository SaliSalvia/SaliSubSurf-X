"""Deep temporal processing of Sentinel-2 L2A pixel data.

This sub-package extends the metadata-only API (v1.1.x) with real multi-temporal
pixel analysis — the "deep processing" pipeline:

    acquire (CDSE Process API) -> preprocess (SCL cloud mask, reflectance scaling)
    -> spectral indices (NDVI/NDWI/MNDWI/NDMI/NBR/BSI/albedo)
    -> robust temporal statistics (median/MAD baseline, z-scores, persistence,
       Theil-Sen trend) -> unsupervised anomaly model (robust PCA, optional
       numpy autoencoder) -> transparent evidence fusion -> connected-component
       labeling -> GeoTIFF / PNG / GeoJSON outputs.

Scientific scope (docs/SCIENCE-SCOPE.md still applies verbatim): every output is
a **multi-temporal surface-change anomaly** indicator. It is never a probability
of a buried target, never a depth estimate, and never a target classification.
"""

from __future__ import annotations

DEEP_VERSION = "1.3.0"
