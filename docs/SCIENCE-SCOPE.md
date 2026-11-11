# Scientific scope

This document defines every indicator the system computes, how the fusion score is built,
and — equally important — what the system deliberately does **not** claim.

## 1. Guardrails

1. A surface anomaly is **not** evidence of a buried target.
2. Optical, thermal, SAR and elevation datasets differ in spatial/temporal resolution,
   processing artefacts and licence terms; provenance is therefore mandatory.
3. No depth estimate or object-type classification is ever emitted without a validated
   physical model and site-specific ground truth.
4. Every observation retains provider, product ID, acquisition time, processing version,
   spatial resolution, quality flags and licence metadata.
5. Field confirmation requires ground-based methods (EMI, magnetometry, GPR) selected for
   the target and geology, performed within local law.

## 2. Connected data sources (v1.0.0)

| Source | Access | Anonymous | Used for |
| --- | --- | --- | --- |
| Copernicus Data Space Ecosystem — OData catalog | HTTPS JSON | yes (metadata) | Sentinel-2 **L2A** scene discovery: footprint intersect, date window, cloud coverage, size |
| AWS Open Data — Terrain Tiles (Tilezen, Terrarium PNG) | HTTPS PNG | yes | global DEM analysis |
| MapLibre demo style | HTTPS | yes | basemap (no key) |

Not connected (by design, see ROADMAP): satellite asset download, Sentinel-1 SAR,
thermal data, any user account system.

## 3. Terrain indicators (exact definitions)

Sampling: the region bbox is resampled onto a regular 256×256 lat/lon grid (bilinear,
from the Web-Mercator tile mosaic). Tile budget ≤ 64 tiles; zoom auto-selected z14→z8.
Effective resolution `156543.03392·cos(lat_mid)/2^z` m/px is reported.

* **Elevation statistics** — min / max / mean / std over valid samples.
* **Slope (Horn)** — third-order finite-difference gradient on the common grid;
  cell size in metres derives from the bbox extents (isotropic on the sphere).
  Reported: mean, max, std, share of cells > 15°.
* **Roughness (Riley TRI)** — mean over cells of the square root of the sum of squared
  elevation differences to the 8 neighbours.
* **Gradient orientation** — slope-magnitude-weighted circular mean of the uphill azimuth
  (0° = north, clockwise) and the resultant length `R ∈ [0,1]` (consistency:
  1 = one dominant direction, 0 = scattered).
* **No-data handling** — missing tiles/sea cells count into `nodata_fraction`; statistics
  use valid samples; slopes use the mean-filled grid only where needed for gradients.

## 4. Surface anomaly score (transparent fusion)

```
score = 0.30 · min(σ_slope/8°, 1)
      + 0.30 · min(TRI_mean/15 m, 1)
      + 0.25 · R
      + 0.15 · min((zmax − zmin)/300 m, 1)
```

The anchors (8°, 15 m, 300 m) are fixed normalisation constants published here; the score
is a weighted mean of the four normalised components and lies in `[0, 1]`. Components are
returned alongside the score so any reader can recompute it by hand.

**Interpretation ceiling:** the score measures *terrain-shape irregularity* — the same
signature that hillslope geology, drainage, vegetation cover, agriculture, or DEM
artefacts produce. It is explicitly **not** a probability of a buried object, and no
depth or target class is derived from it.

## 5. Catalog semantics

* Collection: `SENTINEL-2`, name filter `MSIL2A` → Level-2A (surface reflectance line).
* Geometry filter: `OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(...))`.
* Ordering: newest first (`ContentDate/Start desc`), top ≤ 25, client default 12.
* Cloud coverage: product attribute `CloudCoverage`; client-side threshold (default 30 %).
* Provenance per response: provider, collection, licence note, retrieval timestamp.

## 6. Path to credible detections (what "detection" can honestly mean)

1. **Prioritise**: use catalog metadata + terrain indicators to shortlist areas worth
   visiting (less guesswork, documented reasons).
2. **Ground-truth**: EMI/magnetometry/GPR surveys by qualified operators, legally.
3. **Record**: log the provenance chain (this system) together with field results.
4. **Only then** can anyone speak of "detections" — ground truth defines them; satellites
   never do.
