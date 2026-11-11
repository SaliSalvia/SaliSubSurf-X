# Architecture

```
┌────────────────────────────── Android app (Kotlin 2.2 / Compose / Material 3) ──────────────────────────────┐
│                                                                                                             │
│  MainActivity ── AppRoot (3 tabs)                                                                           │
│      │                                                                                                      │
│      ├─ MapScreen ──── RegionMapView (MapLibre Native 11)                                                   │
│      │      │            • demotiles basemap (no API key)                                                   │
│      │      │            • tap → vertex, GeoJsonSource + Fill/Line/Circle layers                            │
│      │      │            • geodesic area via GeoMath (same formula as backend)                              │
│      │      └─ AppViewModel (StateFlow<UiState>)                                                            │
│      │              • offline validation fallback (GeoMath.localCheck)                                      │
│      ├─ ResultsScreen  (validation card, catalog products, terrain indicators, provenance, caveats)         │
│      ├─ SettingsScreen (runtime API base URL + health check; SharedPreferences persistence)                 │
│      └─ data/ : Retrofit + kotlinx-serialization → SubsurfApi (4 endpoints), OkHttp, SettingsStore          │
└──────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                               │ HTTPS/HTTP JSON (snake_case contract)
┌──────────────────────────────────────────────▼──────────────────────────────────────────────────────────────┐
│                                        FastAPI backend (subsurface_api)                                     │
│                                                                                                             │
│  main.py ── /api/v1/health, /regions/validate, /regions/catalog-search, /regions/terrain-indicators         │
│     │          schemas.py  (pydantic — single source of truth for the JSON contract)                        │
│     ├─ validation.py  (shapely is_simple, vertex budget 3–10, area bounds 500 m² … 500 km²)                 │
│     ├─ geo.py         (spherical area, haversine perimeter, centroid, bbox, WKT)                            │
│     ├─ indicators.py  (transparent weighted fusion → surface_anomaly_score + components)                    │
│     └─ providers/                                                                                           │
│         ├─ cdse.py    → Copernicus OData catalog (anonymous): L2A intersect + cloud + provenance            │
│         └─ terrain.py → AWS Terrain Tiles (Terrarium PNG): mosaic → 256×256 lat/lon grid → Horn slope,      │
│                        Riley TRI, gradient-orientation consistency, nodata, provenance                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Modules

| Path | Responsibility |
| --- | --- |
| `android/app/.../geo/GeoMath.kt` | geodesic math + offline polygon check (mirrors backend) |
| `android/app/.../map/RegionMapView.kt` | MapLibre lifecycle inside Compose, sketch overlay |
| `android/app/.../data/*` | Retrofit API, JSON models, settings persistence |
| `android/app/.../AppViewModel.kt` | single state machine for all screens |
| `backend/subsurface_api/geo.py` | shared geodesic helpers |
| `backend/subsurface_api/validation.py` | authoritative region validation |
| `backend/subsurface_api/providers/cdse.py` | catalog search + product parsing |
| `backend/subsurface_api/providers/terrain.py` | DEM download/decode/metrics |
| `backend/subsurface_api/indicators.py` | documented score fusion |

## Contract discipline

The JSON field names are defined **once** per side (`schemas.py` ↔ `ApiModels.kt` with
`@SerialName`) and both unit-test suites pin them. When adding a field: schemas.py →
ApiModels.kt → tests → CHANGELOG.

## Key design decisions

1. **Two validators, same rules.** The app validates locally (instant feedback, works
   offline) and the server re-validates authoritatively (shapely). Rules are duplicated
   deliberately and mirrored by tests on both sides.
2. **Runtime-configurable endpoint.** The base URL lives in Settings (overriding the
   `API_BASE_URL` build-time default), so one APK serves emulator/LAN/VPS without rebuilds.
3. **Anonymous sources only** in v1: nothing in the critical path needs an account or key;
   Copernicus metadata and DEM tiles work out of the box.
4. **Signing via environment.** `app/build.gradle.kts` reads `KEYSTORE_BASE64` et al.; no
   keystore in the repo, and a missing secret degrades to an unsigned release instead of a
   broken build.
5. **CI without the wrapper JAR.** The workflow installs Gradle 8.14.6 directly
   (`gradle/actions/setup-gradle`), so the repository never stores binary wrapper JARs.

## Build & CI

* Toolchain: JDK 17 · AGP 8.13.2 · Gradle 8.14.6 · Kotlin 2.2.21 · compile/targetSdk 36 ·
  minSdk 26 · MapLibre 11.13.5 · Compose BOM 2025.12.01.
* `.github/workflows/android.yml`: checkout → JDK 17 → SDK (platforms;android-36,
  build-tools;36.0.0) → Gradle → `assembleDebug` + `assembleRelease` → artifacts →
  release attach on `v*` tags.
* `.github/workflows/backend.yml`: Python 3.12 → `pip install -e "backend[dev]"` → pytest.
