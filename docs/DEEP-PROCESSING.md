# Deep temporal processing (`/api/v1/deep`)

Version 1.2.0 adds the **deep-processing pipeline**: real multi-temporal pixel
analysis of Sentinel-2 L2A data — not just catalog metadata. This document is
the exact specification of every number the pipeline emits. `docs/SCIENCE-SCOPE.md`
still applies verbatim: outputs are *surface-change indicators*, never
buried-target probabilities, never depths.

## 1. Pipeline overview

```
┌ acquire ────────┐  ┌ preprocess ────┐  ┌ indices ─────────────────────┐
│ CDSE Process API│→ │ reflectance    │→ │ NDVI NDWI MNDWI NDMI         │
│ 8-band stacks   │  │ (DN−1000)/10⁴  │  │ NBR BSI albedo               │
│ per date, 10 m  │  │ SCL cloud mask │  │ (NaN = invalid pixel)        │
└─────────────────┘  └────────────────┘  └──────────────┬───────────────┘
                                                        ↓
┌ outputs ─────────────────────────┐  ┌ fusion ─────────────────────────────┐
│ GeoTIFF (EPSG:4326) · PNG        │← │ weighted evidence 0–100 + coherence │
│ overlay · GeoJSON · report.json  │  │ + confidence classes                │
└──────────────────────────────────┘  └──────────────┬──────────────────────┘
                                     ┌ model ────────┴──────────────────────┐
                                     │ unsupervised: robust PCA (default)   │
                                     │ or numpy autoencoder (8→3→8)         │
                                     │ reconstruction-error percentile      │
                                     └──────────────┬───────────────────────┘
                                     ┌ temporal ────┴───────────────────────┐
                                     │ median baseline · MAD z-scores       │
                                     │ persistence · Theil–Sen trend        │
                                     └──────────────────────────────────────┘
```

## 2. Acquisition

* Endpoint: `https://sh.dataspace.copernicus.eu/api/v1/process` (sentinel-2-l2a).
* Auth: CDSE token — either personal account (`grant_type=password`,
  `client_id=cdse-public`) or an OAuth client (`client_credentials`).
  Environment variables (never logged):
  * `COPERNICUS_USERNAME` + `COPERNICUS_PASSWORD`, **or**
  * `COPERNICUS_CLIENT_ID` + `COPERNICUS_CLIENT_SECRET`.
* Evalscript returns one UINT16 stack per date: `B02 B03 B04 B08 B11 B12 SCL dataMask`.
* A 429/5xx is retried 3× with linear back-off; the free-tier rate limits are
  respected by daily stepping and the `max_dates` cap (≤ 24 accepted scenes).
* Only the requested bbox is transferred — tens of KB per date, never full scenes.

## 3. Preprocessing

* Reflectance = `(DN − 1000) / 10000` (processing-baseline 4.0 harmonisation
  offset; override with `S2_DN_OFFSET` if Copernicus ever changes it).
* Valid surface pixels: SCL ∈ {2 dark, 4 vegetation, 5 bare, 6 water,
  7 unclassified} **and** `dataMask > 0`. Clouds (8/9), cirrus (10), shadows (3),
  snow (11), nodata (0/1) are excluded — clouds must never read as ground change.
* Scene quality gate: a scene is used only if `valid_fraction ≥ min_valid_fraction`
  (default 0.55). At least 4 usable scenes are required.

## 4. Spectral indices (exact formulas)

| Index | Formula | Meaning |
| --- | --- | --- |
| NDVI | (B08−B04)/(B08+B04) | greenness / vegetation vigour |
| NDWI | (B03−B08)/(B03+B08) | open water (McFeeters) |
| MNDWI | (B03−B11)/(B03+B11) | moist land / wet surfaces (Xu) |
| NDMI | (B08−B11)/(B08+B11) | canopy & soil moisture |
| NBR | (B08−B12)/(B08+B12) | drying / disturbance proxy |
| BSI | ((B11+B04)−(B08+B02)) / ((B11+B04)+(B08+B02)) | bare-soil exposure |
| Albedo | mean(B02,B03,B04,B08) | broadband brightening |

## 5. Temporal evidence (robust statistics)

For every index:

* **Baseline** = pixel-wise *median* over all accepted scenes before the recent
  window; **dispersion** = MAD × 1.4826 (+10⁻⁴ floor):
  `z = (recent_median − baseline_median) / (1.4826·MAD + 10⁻⁴)`.
* **Persistence** = fraction of the last `recent_k` scenes in which the pixel's
  z crossed the threshold (default |z| ≥ 1.5) in the anomaly direction; the
  reported layer is the mean over {NDMI, NDVI, BSI, NBR} — indices whose
  *deficit/exposure* direction is physically coherent.
* **Trend** = Theil–Sen slope (median of pairwise slopes, ≤ 36 pairs) over the
  accepted window, reported per 30 days, clipped to ±0.1.

The recent window is the last `recent_k` (default 4) scenes; the baseline is
everything up to and including its first scene.

## 6. Anomaly model (unsupervised, deterministic)

Feature vector per pixel (13 dims): NDVI NDWI MNDWI NDMI NBR BSI albedo,
z(NDMI) z(NDVI) z(BSI), persistence, trend(NDMI), trend(NDVI).
Robust-standardised (median / IQR); invalid pixels excluded and scored 0.

* `pca` (default): SVD, components kept for ≥ 90 % variance, per-pixel
  reconstruction error → percentile rank in [0, 1].
* `autoencoder`: numpy tanh MLP 13→8→3→8→13, SGD lr 0.02, ≤ 300 epochs,
  batch 1024, early stop 10⁻⁷, seeded (42), trained on ≤ 40 000 valid pixels.
  Reconstruction error → percentile rank.

The output is always "how spectrally *surprising* is this pixel relative to the
region" — a relative measure, never an absolute physical quantity.

## 7. Evidence fusion — two modes (v1.3.0)

### 7a. CPF-lite (default, `fusion_mode="cpf"`) — calibrated detection

The legacy score (below) answers "which pixels look stressed?" but has no
false-positive control: under smooth seasonal drift it flags most of a region,
and its deep-model term is a percentile (uniform by construction). CPF-lite
replaces the *detection criterion* with a calibrated statistical test on the
same evidence:

1. **Context detrending** — for each signed channel z_c a degree-3 2-D
   polynomial "natural null" is fitted with Tukey-biweight IRLS
   (c = 4.685, 6 iterations). Residuals r_c = z_c − poly_c are what remains
   after phenology/soil/illumination trends are removed.
2. **Robust whitening** — per-channel median/MAD standardisation, covariance
   estimated on the central 80 % (by norm) with Ledoit–Wolf-style shrinkage
   (λ = 0.1), then d² = (r−med)ᵀ·mad⁻²·W·(r−med) with W = S^(−1/2).
   Correlated channels no longer double-count.
3. **Empirical null** — d² is rescaled by s = median(d²)/χ²₆(0.5) (Efron-style
   empirical null) because real residuals are heavier-tailed than Gaussian.
4. **Cluster-mass surrogates** — clusters are seeded where d²/s > χ²₆^{-1}(1−10⁻³)
   (8-connected, ≥ min_pixels). Cluster *mass* = Σ(d²/s − thr). A null
   distribution of the maximum cluster mass is built from `n_surrogates`
   (default 199) phase-randomised surrogates: per-channel power spectra are
   kept, phases are drawn once and shared across channels (cross-channel
   structure survives). A cluster is reported only when its add-1 conformal
   p-value p = (1 + #{null_max ≥ m})/(1 + n_surr) ≤ alpha (default 0.01).

Confidence: high (p ≤ 0.001), medium (p ≤ 0.01), low (otherwise).
`score_map.png`/`score.tif` carry a 0–100 per-pixel significance score
(−log10 survival-function-scaled d²/s); detections carry `p_value`, `method`,
`bbox_wgs84` and `elongation_ratio`.

**Measured calibration** (deterministic injection suite,
`tests/test_null_injection.py`, 9 scenes, 96–128 px):

| scenario | legacy FP-area | CPF FP-area | CPF recall |
| --- | --- | --- | --- |
| pure noise, no anomaly | 1.7 % | 0.0 % | — |
| smooth seasonal drift, no anomaly | **69 %** | **3.2 %** | — |
| planted anomaly + drift | 72 % | 7.5 % | 1.00 |
| weak planted (35 %) + drift | 70 % | 4.0 % | 0.96 |

### 7b. Legacy (`fusion_mode="legacy"`) — transparent weighted score

```
score/100 = 0.25 · min(−z(NDMI)/3, 1)        (moisture deficit)
          + 0.20 · min(−z(NDVI)/3, 1)        (vegetation stress)
          + 0.15 · min( z(BSI)/3, 1)         (soil exposure)
          + 0.20 · persistence
          + 0.20 · deep-model percentile
```

* **Coherence** = share of the five layers ≥ 0.5 (agreement 0–1).
* **Pixel confidence classes**: high = score ≥ 65 ∧ coherence ≥ 0.6 ∧
  persistence ≥ 0.5; medium = score ≥ 50 ∧ coherence ≥ 0.4; low = score ≥ 35.

Kept for comparability and as a diagnostic; its known failure mode (drift →
everything flagged) is exactly what CPF-lite fixes.

## 8. Detections (connected components)

* CPF mode: mask = pixels of clusters significant at `alpha`; components are
  labeled globally after tiling (p-value = min over the tile clusters merged
  into the component).
* Legacy mode: fused score ≥ `score_threshold` (default 55/100) ∧ valid pixel.
* 8-connected labelling (BFS); regions < `min_pixels` (default 9 px) dropped;
  at 10 m GSD that is a ~900 m² minimum footprint.
* Each region → convex-hull polygon (pixel centres → WGS84) with properties:
  area (geodesic m²), mean/max score, coherence, persistence, confidence,
  centroid, bbox, elongation ratio, synthetic flag (selftest), and p_value +
  method in CPF mode. Top 50 components by size are reported.

### Native-resolution tiling (v1.3.0)

With `resolution_m` set (10–100 m) the AOI bbox is gridded at native scale
(≤ 4.2 M px total, ≤ 3072 px per side) and split into ≤512-px tiles with a
24-px overlap halo. Each tile runs the full chain (acquire → indices →
evidence → model → fusion); per-tile maps are stitched (halo discarded) and
components labeled globally. Per-tile statistics (detrend surface, whitening,
null) are computed per tile — a documented approximation bounded by the halo.
Scene acceptance is also per tile; tiles with < 4 usable scenes are dropped
and reported as `tiles_failed`.

## 9. Artifacts (per job, under `DEEP_DATA_DIR/<job_id>/`)

| File | Content |
| --- | --- |
| `score_map.png` | fused score, fixed colour ramp |
| `overlay.png` | latest scene natural colour + anomaly overlay |
| `layer_*.png` | the five evidence layers |
| `score.tif` / `persistence.tif` / `deep_anomaly.tif` | GeoTIFF float32, EPSG:4326 |
| `detections.geojson` | component polygons + properties |
| `timeseries.json` | AOI-median of every index per date (charts) |
| `report.json` | full parameters, scenes used, weights, caveats, provenance |

## 10. API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/deep/capabilities` | what this deployment supports right now |
| `POST /api/v1/deep/analyze` | start a job (`mode: live \| selftest`) |
| `GET /api/v1/deep/jobs` / `jobs/{id}` | queue status / progress / stage |
| `GET /api/v1/deep/jobs/{id}/result` | full report |
| `GET /api/v1/deep/jobs/{id}/files/{name}` | artifact download |
| `POST /api/v1/deep/selftest?grid=192` | synchronous offline validation |
| `GET /deep-console` | browser console (bbox → analyze → artifacts) |

If `DEEP_API_KEY` is set in the environment, all deep endpoints require the
header `X-API-Key`.

## 11. Selftest mode

`mode: "selftest"` runs the *identical* downstream chain on a deterministic
synthetic stack (a fading "drying/stress" ellipse injected into 9 scenes).
Use it to verify a deployment without any Copernicus account. The report,
every geojson feature and the API response all carry `"synthetic": true` —
these detections verify the deployment, nothing about real terrain. With
`resolution_m` the selftest also exercises the tiling/stitching path (the
single ellipse is planted in full-grid coordinates, so non-overlapping tiles
act as in-situ null controls).

## 12. Honest limitations

1. Optical imagery sees the **surface**, never the subsurface; a "detection" is
   a coherent multi-date surface-change anomaly. Daily thermal penetration is
   tens of cm, seasonal ~2–3 m; tunnels ≥ 10 m in rock leave no thermal or
   radar signature — only surface effects (shaft mounds, access tracks,
   vegetation lines).
2. Agriculture (harvest, irrigation change), hydrology, geology, fire, and
   residual cloud/shadow artefacts can produce identical signatures.
3. CPF controls false positives **relative to a surrogate null of this region**;
   it does not classify the *cause* of a change and cannot detect anything
   below the sensitivity floor of the sensor stack.
4. Grid mode (≤ 512 px) trades spatial detail for PaaS memory limits; use
   `resolution_m` for native 10 m analysis (≤ ~20×20 km per job). The
   effective cell size is reported in every response.
5. The Terrarium DEM used by terrain indicators is SRTM-derived (~30 m true
   resolution); the reported `resolution_m_per_px` is the sampling spacing,
   not the native DEM resolution. Copernicus GLO-30 is the planned upgrade.
6. Statistical evidence prioritises land for ground investigation; field
   confirmation (EMI / magnetometry / GPR, legally) is always required —
   including heritage permits for historical sites.
