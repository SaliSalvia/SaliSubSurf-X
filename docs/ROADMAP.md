# Roadmap

Staged, evidence-first implementation plan. Nothing here promises buried-target
detection; each milestone adds one defensible capability with provenance.

## M0 — Bootstrap (✅ shipped in 1.0.0)

- [x] Android app: map, region sketching (3–10 vertices), area estimate, offline validation
- [x] Backend: strict polygon validation
- [x] Sentinel-2 L2A catalog metadata search (anonymous, Copernicus OData)
- [x] Open-DEM terrain indicators + transparent surface-anomaly score
- [x] CI: automatic APK builds (signed via secrets) + backend tests
- [x] Scientific guardrails, provenance everywhere, bilingual docs (EN/فا)

## M1 — Optical surface indicators (✅ shipped in 1.2.0–1.3.0)

- [x] Copernicus Data Space Process API pixel download (authenticated, DN units)
- [x] Band math on the backend: NDVI / NDWI / MNDWI / NDMI / NBR / BSI / albedo
- [x] Multi-temporal robust statistics (median/MAD z-scores, persistence, Theil–Sen)
- [x] Deep temporal pipeline with artifacts (PNG/GeoTIFF/GeoJSON/report)
- [x] **CPF-lite calibrated detection** (context detrend + whitening + surrogate
      conformal p-values) and **native 10 m tiling** (v1.3.0)
- [x] Null/drift injection suite in CI — the false-positive contract is tested
      on every push

## M2 — CPF full: cross-physics fusion (the "پردازش عمیق" program)

Ordered by marginal value per engineering effort:

1. **Thermal physics** — ECOSTRESS LST (~70 m, multiple overpass hours; ISS
   coverage 52°N–52°S includes Iran) + Landsat 8/9 TIRS: apparent thermal
   inertia and thermal-time-constant maps (system identification against
   diurnal forcing), the strongest remote proxy for near-surface moisture
   and disturbed ground.
2. **Sentinel-1 SAR series** — coherence and InSAR subsidence (water
   withdrawal / irrigation as explicit nuisance model), backscatter moisture
   proxy. NISAR L-band (public since 2026-07, ASF DAAC, 12-day repeat,
   provisional) for deeper dry-sand penetration (~1–2 m best case).
3. **Hypothesis-based evidence combination** — for each hypothesis (dry cavity,
   water conduit / qanat, disturbed soil, dense structure, metal) define the
   *predicted* signature across sensors; combine with Dempster–Shafer mass
   assignment including explicit "unknown", with copula corrections so
   correlated sensors are not counted twice.
4. **Structural lineament layer** — Frangi vesselness with qanat slope
   constraints, equal-spacing shaft-row detection, blob + "artificialness"
   indices (straightness, periodicity).
5. **Detectability map** — per-pixel minimum detectable target size given the
   fused sensitivity; "nothing found" then only claimed where sensitivity was
   adequate. This is the honest null.
6. **Context-aware null (GP on covariates)** — geology, slope, soil
   (SoilGrids), land cover (WorldCover) as covariates instead of per-tile
   polynomial detrending; non-stationary surrogate.
7. **Calibration & validation** — physical void injection into real data +
   known qanat / cave / mine sites (OSM, cave registers) with spatial block
   cross-validation. Prior-art search before any novelty claim.

Background layers: Copernicus GLO-30 DEM (replacing Terrarium/SRTM ~30 m),
ERA5-Land + IMERG (rain), SoilGrids, WorldCover, national geological maps,
EMIT/EnMAP hyperspectral (check access). EMAG2/WGM2012 magnetics & gravity
only as regional context (~km resolution) — local targets need drone
magnetometry, GPR, ERT or microgravity.

## M3 — Analysis hardening

- [ ] Persisted "survey projects" (local DB: regions, chosen scenes, notes, results)
- [ ] Export: GeoJSON of region + JSON report with full provenance chain
- [ ] Time-series view of indicators per region
- [ ] Optional read-only sharing link (self-hosted backend)

## M4 — Field-truth bridge

- [ ] Manual entry of ground observations (method, date, operator, result)
- [ ] Side-by-side comparison: surface indicators vs field results (honest scatter, no
      model fitting until data volume justifies it)
- [ ] Clear separation: "prioritisation tool" — never an autonomous "detector"
- [ ] Per-target recommended field method (GPR / ERT / magnetometry /
      microgravity) with permit notes (heritage sites require permits)

## Non-goals

- Depth estimation, target classification, "treasure maps", or any claim that satellite
  data can identify buried objects. These are physically unsupported without site-specific
  physical models and ground truth (see SCIENCE-SCOPE.md).
