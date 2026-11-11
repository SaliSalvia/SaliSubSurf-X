# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.2] - 2026-11-12

Operability hotfix: clears the CI lint gate, makes Runflare Git-deploys actually build
the API, and ships a hardened one-shot Termux deploy script.

### Fixed
- **CI lint gate** (`:app:lintDebug` → "Lint found errors"): `LocalContextGetResourceValueCall`
  in `AppRoot.kt` — `Context.getString()` inside `LaunchedEffect` — resolved by capturing
  `stringResource(R.string.report_copied)` during composition.
- **Runflare "default webpage" root cause**: Git-connected Runflare builds the *repository
  root*, where no Dockerfile existed. Added a root `Dockerfile` (same pinned, non-root,
  `$PORT`-aware image as `backend/Dockerfile`) + `.dockerignore` keeping Android/CI/docs out
  of the image context.
- **Termux deploy script** (`scripts/salisurf-x-runflare.sh`): a Persian prompt reached the
  variable-name slot of `printf -v` ("invalid variable name") and the script silently fell
  through to 10 minutes of pointless health polling. Rewritten: argument order is validated
  inside `ask()` (the bug class is now structurally impossible), `set -euo pipefail` + explicit
  aborts on every failed step (push/SHA verification before polling), the script self-locates
  the project (repo root, `~/SaliSurf-X-src`, or newest ZIP in Downloads — no more
  "No such file or directory" when run from the wrong folder), and health polling now
  distinguishes a healthy JSON, the Runflare placeholder page (with Revert/port-8000/Dockerfile
  checklist), connection failure, and non-API HTML.

### Added
- `android/local.properties` git-ignored (SDK path must never be committed).

## [1.6.0] - 2026-11-11

Brand-identity release: the SaliSurf-X **mother logo**, **wordmark**, and **signature**
artwork are now first-class assets inside the app and the repo. No scientific models, API
contracts or geo-maths change; the `applicationId` is unchanged so existing installs keep
updating in place.

### Added
- **In-app brand artwork**: four full-resolution brand assets now ship in `drawable-nodpi/`
  — `brand_mother_logo.png` (the CPU-chip-meets-earth hero with the gold "Salar Farzaneh"
  signature), `brand_chip_blue.png` (the neural-network core, used as the system splash
  mark), `brand_chip_terrain.png` (the magma-terrain variant), and `brand_wordmark.png`
  (the gold→electric-blue chrome wordmark, keyed to alpha so it composites on any dark
  surface).
- **Density-bucketed splash mark** (`mipmap-mdpi…xxxhdpi/ic_splash_mark.png`): the blue
  chip is cropped to its inner content (signature arc removed) and rendered at all five
  Android density buckets so the cold-start splash is crisp at every device resolution.
- **Hero "About" panel** in Settings: a brand-hero card that stacks the wordmark banner on
  a molten gold→electric-blue gradient strip, the full mother logo, app name + tagline +
  version, and the "Brand artwork & signature by Salar Farzaneh" credit. Existing
  disclaimer and licence text are preserved below a hairline divider.
- **Bilingual brand strings** (`values/` + `values-fa/`): `brand_tagline` ("Surface
  intelligence · subsurface intuition" / "هوشمندی سطح · شهود زیرسطحی"),
  `brand_designer_credit`, and accessibility `contentDescription`s for every brand image.
- **README banner**: the ASCII-art header is replaced by the actual wordmark banner and a
  512-px mother-logo thumbnail. New `docs/images/wordmark_banner.png`,
  `play_feature_graphic.png` (1024×500, Google-Play-ready), and `mother_logo_512.png`.

### Changed
- **`launch_screen.xml`** now references `@mipmap/ic_splash_mark` (the density-bucketed
  blue-chip PNGs) instead of the old layer-list vector. The redundant
  `drawable/ic_splash_mark.xml` layer-list is removed; the splash mark is now a single
  crisp rasterised chip centred on the obsidian field.
- **Version bumped** to `1.6.0` / `versionCode 8` to reflect the new visual identity
  assets.

### Removed
- `drawable/ic_splash_mark.xml` — superseded by the density-bucketed PNG set in `mipmap-/`.

## [1.5.0] - 2026-11-11

Brand + design-system release: the product is now **SaliSurf-X** (formerly
SubsurfaceExplorer / Sal-Subsurf). No scientific models, API contracts or geo-maths change;
the `applicationId` is unchanged so existing installs keep updating in place.

### Changed
- **Renamed the product to SaliSurf-X everywhere it is user-visible**: launcher label
  (English and فارسی), report titles, exit dialog, Settings "about" text and API-URL help,
  the FastAPI service title (`/docs`), the deep console page, Gradle root project name, CI
  artifact names (`SaliSurf-X-debug.apk` / `SaliSurf-X-release-signed.apk`), README, docs and
  helper scripts. The code package/namespace stays `com.salsalvia.subsurf`.
- **Launcher icon refresh**: the adaptive-icon foreground is now a crisp vector (no more
  rasterized foregrounds), with the subsurface-signal chevrons rendered in the brand's
  molten-gold gradient (Gold200→Gold500) and gold vertex markers over an obsidian field with a
  faint radial gold bloom. The monochrome/themed silhouette is unchanged.
- **Android 12+ branded system splash**: `values-v31` / `values-night-v31` themes set
  `windowSplashScreenBackground` + `windowSplashScreenAnimatedIcon`, so the very first frame
  matches the obsidian brand plate — no white flash between system splash and window.
- **Press micro-interactions**: the circular map buttons, dock actions, lock button and the
  primary "Collect data" CTA now dip ~4–8 % in scale while pressed (replacing/supplementing
  the default ripple) — a single consistent physical feedback language across the app.
- **Softer screen transitions**: tab changes now combine fade, a shorter upward slide and a
  barely perceptible scale settle on standard Material easing curves
  (`FastOutSlowInEasing` / `LinearOutSlowInEasing`).

### Added
- **One-command Termux deploy** (`scripts/salisurf-x-deploy.sh`): finds the project ZIP in the
  phone's Download folder, creates the `SaliSurf-X` GitHub repository via `gh`, pushes with
  gh-token credentials, interactively creates a personal keystore (hidden passwords, alias and
  certificate details asked in-terminal) when signing secrets are missing, registers all four
  secrets *before* the first push, watches the Actions run to completion, waits for the
  release, and downloads the APKs back to the Download folder.
- **Releases on every push to `main`**: the Android workflow now derives the tag from
  `versionName` and publishes/updates a rolling GitHub Release (`v1.5.0`, both APKs attached,
  auto-generated notes) — no manual tagging. `v*` tag pushes still pin a release to the tag;
  bump `versionName` to mint a fresh release.
- `scripts/termux-sign.sh` gains a pointer to the all-in-one deploy script and SaliSurf-X
  defaults (alias `salisurf-x`, keystore path, certificate CN/O).

### Fixed
- README quickstart no longer tells users to push a tag to get a release — pushes to `main`
  release automatically now.

## [1.4.1] - 2026-11-07

Operability + hardening release: everything between "it builds" and "someone can actually use
it" on the phone, plus the backend hardening pass. Still presentation/client-side on the
Android side — no scientific models, API contracts or geo-maths change.

### Fixed
- **Lock did not lock.** While tracing, pan/zoom/double-tap gestures stayed active, so a drag
  could move the map mid-trace and taps landed in the wrong place. Gestures are now disabled while
  the area is locked (and re-applied after a basemap swap) — and, per review, the **on-screen
  camera controls (zoom buttons, globe, fit/recenter) are disabled while tracing too**, so the
  locked camera cannot be moved from the chrome either.
- **The map ignored the app theme.** The resolved appearance is now published into `UiState`
  (`isDark`) by the activity, so a user who chose Dark on a light-mode phone gets the dark
  basemap.
- **Auto-terrain never retried.** The "fetch terrain after the catalog arrives" guard was a
  one-shot boolean: a failed call disabled the automatic fetch for the rest of the session. It is
  now keyed on the sketch vertices + a per-run `runId`, and refuses to auto-fire while a run is in
  an error state.
- **The collection overlay could spin forever.** It now hides as soon as a run fails, leaving the
  map visible with the retry affordance.
- **Results appeared on failed runs.** Navigation to Results now requires valid server validation
  *and* a catalog response (the `analysisSeq` one-shot); a rejected region keeps the user on the
  map with the actual issue in the retry banner.
- **`metresPerPixel()`** returned a no-op expression (`/512*512`); it now uses the correct
  512-px-tile Web Mercator relation that the new scale bar depends on.
- **Basemap attribution was disabled.** MapLibre's attribution control is back on (OpenStreetMap /
  OpenFreeMap attribution is a licence obligation, not decoration).
- Android: `busy`/`terrainBusy` are set before the coroutine starts (double-tap race), and a
  late response is discarded when the sketch changed while the request was in flight.
- Android: HTTP logging is disabled in release builds so request URLs never reach logcat.
- Deep `/analyze` now applies the same strict geometry validation as the catalog and terrain
  endpoints and normalises closed rings before they reach the Process API.
- A failed CDSE pixel fetch no longer sleeps after its final attempt (4–12 s saved per date).
- Terrain analysis refuses to report statistics when more than half of the DEM grid is missing.
- The Android Retrofit cache is a small LRU instead of an unbounded map.

### Added
- **In-place failure handling**: a failed collection shows a banner on the map with the actual
  cause (unknown host / timeout / connection refused / HTTP detail) and **Try again** / **Dismiss**;
  the primary button becomes a retry. Settings and the terrain card report the same reason.
- **Startup backend probe** with an offline notice on the map ("Backend not reachable", shortcut to
  Settings) and a live **Online / Offline / Checking…** pill in Settings.
- **Map scale bar** (Google-Maps style) that snaps to 1/2/5 × 10ⁿ and refreshes when the camera
  settles. New unit tests pin the snapping, the "never understates" property and the formatting.
- **Share / copy the run summary** as plain text from Results (always including the scientific
  caveat), with a confirmation snackbar.
- **Android back navigation**: back from Results/Settings returns to the map; back on the map asks
  before leaving.
- **R8 (minify + resource shrinking) enabled for release** with the rules MapLibre, Retrofit/OkHttp,
  kotlinx-serialization and ViewModels actually need — smaller APK, faster start.
- 22 new strings in English and فارسی (143 total, parity checked in CI).
- `TERRAIN` retry is its own action, and editing the API address re-probes immediately so the
  status pill can never show a stale result next to a new URL.
- `GET /api/v1/ready` readiness probe that verifies the artifact volume is writable; the
  Docker `HEALTHCHECK` now uses it, while `/api/v1/health` stays I/O-free (liveness).
- Every HTTP response carries an `X-Request-ID` (client-supplied IDs are accepted only when
  they match a safe charset) and the server logs one line per request with status and latency.
- Deep-processing queue cap (`MAX_ACTIVE_JOBS = 4`): excess submissions get HTTP 429 with
  `Retry-After` instead of queueing unbounded RAM-heavy jobs.
- Catalog responses now report the true `total_matched` via OData `$count=true`.
- CI gates: Android `:app:lintDebug` (with `abortOnError = true`) and backend `ruff` E9/F.
- Selftest runs are capped at two concurrent executions (429 + `Retry-After`) and their
  artifact directories are pruned to the ten newest, so diagnostics cannot fill the volume.
- CORS preflights may send `X-Request-ID`; the deep executor shuts down with the app.

### Changed
- Transport errors are translated into actionable sentences instead of raw exception text.
- Copernicus catalog calls retry transient 429/5xx responses with capped exponential
  backoff and honour a small `Retry-After`; malformed JSON becomes a clean 502.
- Container image runs as unprivileged uid 10001 and owns only its artifact directory.
- Backend dependencies are pinned with SHA-256 hashes in `requirements.lock` and
  `requirements-dev.lock` (universal markers for Python 3.10+, uv-generated); Docker and CI
  install those locks, and `requirements.txt` is now a shim for PaaS hosts. Builds no longer
  drift with new upstream releases.
- The PEP 517 build backend is pinned too (`setuptools==84.2.1` in `pyproject.toml` and
  hash-locked in `requirements-build.lock`); Docker and CI build the wheel with
  `--no-build-isolation` and a fixed `SOURCE_DATE_EPOCH`, producing byte-identical wheels.
- **Scoped cleartext policy, revised after review.** The first cut only allowed cleartext for
  `10.0.2.2`/`localhost`/`127.0.0.1`, which silently broke the documented "physical phone on
  your LAN" workflow (`http://192.168.x.x:8000/`). Android's network security config cannot
  express private IP ranges, so the base config now permits cleartext (a self-hosted LAN
  backend has no TLS certificate) while HTTPS stays available and preferred for every host
  that supports it — see `res/xml/network_security_config.xml`.

### Documentation
- README: end-to-end "use the app" walkthrough (lock → trace → collect → share), the backend
  address rules, and what each failure banner means.

## [1.4.0] - 2026-11-08

Exploration-flow and identity release. **Presentation only** — backend, API contracts, geo maths
and the analysis pipeline are untouched.

### Fixed
- **Release build broken on `main`** (introduced with the v1.3.0 UI work): `BRAND`/`BRAND_LIGHT`
  were declared `const val` but initialised with `.toInt()`, which is not a compile-time constant
  in Kotlin. They are now `val`s, and `AndroidManifest`-referenced `@mipmap/ic_launcher_round`
  exists at every density.

### Added — Google-Earth-style exploration
- The home screen now opens on the **globe** and behaves like a maps app: free one-finger pan,
  pinch zoom, a "back to globe" and "recenter/fit" control, and no accidental vertex drops.
- **Lock → trace → collect**: a prominent **Lock** button freezes the camera, and each tap then
  places a corner of the exploration boundary. The boundary is drawn as a **red and black dashed
  ring** (`lineDasharray`) over a faint gold fill, with gold vertex handles, a blue centroid
  marker and a pulsing crosshair reticle while tracing.
- Live area/perimeter read-out while tracing, plus a step-dot progress indicator (3–10 points).
- A full-screen **collection overlay** ("Collecting data for your area") with staged progress
  rows for validation → satellite catalog → terrain indicators.
- One run now gathers the complete picture: when the Sentinel-2 catalog for the locked area
  arrives, the terrain indicators are fetched automatically (UI orchestration only).

### Added — brand identity from the logo
- New launcher icon generated from the supplied artwork at every density, plus adaptive
  foreground/background (near-black plate), round variants and a monochrome themed-icon glyph.
- Branded launch window built from the logo; the app **defaults to the dark theme** because the
  logo is luminous artwork on black (Light and System remain selectable in Settings).
- Full palette rebuilt around the logo: obsidian neutrals, **molten gold** primary, **electric
  blue** secondary and **ember orange** alerts, in both light and dark schemes.
- The logo now appears in the map header plate and in Settings → About.

### Changed
- Every screen was re-cut against the new palette; removed unused colour/style tokens.
- Copy for the new flow added and translated in English + فارسی (no dead string keys remain).

## [1.3.0] - 2026-11-07

Calibration & honesty release, driven by an independent scientific review of v1.2.0.

### Fixed
- **CRITICAL live-mode bug**: the Process API evalscript requested reflectance bands without
  `units: "DN"` — the API served REFLECTANCE floats (0..1) that truncate to 0/1 under the
  UINT16 sample type, so every pixel failed the (DN−1000)/10⁴ harmonisation and live analysis
  produced garbage. The script now groups B02..B12 under `units: "DN"` (SCL/dataMask stay
  unit-less) — guarded by a regression test.
- API-key comparison now uses `hmac.compare_digest` (constant-time; no byte-by-byte key
  recovery via response timing).
- CORS is configurable via `CORS_ORIGINS` (comma-separated) and restricts methods/headers
  to what the API actually uses; the default stays `*` so the Android app and `/deep-console`
  work unchanged.

### Added
- **CPF-lite fusion (default `fusion_mode="cpf"`)** — calibrated anomaly statistics replacing
  the raw hand-weighted score as the detection criterion:
  1. Tukey-biweight IRLS degree-3 polynomial **context detrending** per evidence channel
     (smooth phenology/soil/illumination trends are removed before anything is "anomalous");
  2. robust median/MAD standardisation + trimmed shrinkage-covariance **whitening** →
     Mahalanobis d² over the six signed channels (correlated evidence is not double-counted);
  3. Efron-style **empirical null scaling** of d² to a chi²₆ reference;
  4. **phase-randomised surrogates** (shared phases across channels, default 199) calibrate a
     cluster-mass null; detections get **add-1 conformal p-values** and are reported only at
     p ≤ alpha (default 0.01). Confidence classes: high (p≤0.001) / medium (p≤0.01) / low.
  Measured on the null/drift injection suite (`tests/test_null_injection.py`): under strong
  seasonal drift with NO anomaly the legacy detector flags ~69 % of a region while CPF keeps
  false-positive area at ~3 %; with a planted anomaly CPF retains recall 1.00 at ~7.5 % FP
  (legacy: 72 % FP). Legacy fusion stays available via `fusion_mode="legacy"`.
- **Native-resolution tiling**: `resolution_m` (10..100 m) analyses the AOI on its native
  Sentinel-2 grid instead of resampling to ≤512 px. The area is split into ≤512-px space tiles
  with a 24-px overlap halo, each tile runs the full chain, maps are stitched and components
  labeled globally. Budget: ≤4.2 M px (≈20×20 km at 10 m) with a clear error message beyond.
  Requests: `processing.resampling` is set (bilinear in native mode, nearest in grid mode).
- **Synthetic flags everywhere in selftest mode**: report (`synthetic: true`), every
  detections.geojson feature (`properties.synthetic`), FeatureCollection metadata and the API
  response — a planted-ellipse detection can no longer be mistaken for real-terrain evidence.
- Detection properties now include `bbox_wgs84`, `elongation_ratio` (line-like detections such
  as shaft rows are no longer hidden by the convex-hull blob) and, in CPF mode, `p_value` +
  `method`. report.json gains `fusion_mode`, `cpf` (calibration summary), `native_resolution`,
  `resolution_m`, `tiles`, `tiles_ok/failed`.
- `n_surrogates`, `alpha`, `fusion_mode`, `resolution_m` request fields; selftest endpoint
  accepts `resolution_m`/`fusion_mode`/`n_surrogates` query parameters; capabilities endpoint
  advertises fusion modes + native-resolution limits. `n_surrogates` is auto-raised to the
  add-1 conformal floor (1/alpha − 1) when it would otherwise make significance impossible.
- `/deep-console` gains fusion-mode and native-resolution controls and surfaces
  synthetic/native/tile info in the completion line.
- New test modules: `test_null_injection.py` (legacy-vs-CPF drift/injection contract),
  `test_cpf.py` (detrend/whiten/null-scale/plant/quiet unit tests), `test_tiling.py`
  (native grid caps, exact tile-core coverage, stitched selftest, legacy-through-tiles) and
  evalscript/payload regression tests — suite now **72 tests, all green**.

### Changed
- Version bump to 1.3.0 (app `versionCode` 4; backend 1.3.0; report schema
  `subsurf.deep.report/1.3.0`); `scipy>=1.11` added to backend dependencies.

## [1.3.1] - 2026-11-07

_See 1.4.0 below._


### Android — presentation overhaul (PR #11)

Purely visual/UX work on the Android client. Networking, ViewModel logic, geo maths, API
contracts and the FastAPI backend are untouched.

#### Added
- **Design system** (`ui/theme`, `ui/components`): full Material 3 colour schemes for light and
  dark (hand-tuned AA contrast), a dedicated type scale, a spacing/elevation token set, and
  reusable primitives — `SubsurfCard`, `CardHeader`, `Pill`, `MetricValue`/`MetricRow`,
  `MeterBar`/`MeterRow`, `InfoBanner`, `BulletLine`, `EmptyState`, `SegmentedPicker`.
- **Local icon set** (`ui/icons`): 20 hand-built 24dp glyphs on a single 2dp optical stroke.
  Keeps the APK small — no `material-icons-extended` dependency was added.
- **Theme choice**: System / Light / Dark, persisted locally (`SettingsStore.themeMode`).
- **Real cartography**: the key-less MapLibre *demo* style was replaced with OpenFreeMap
  vector basemaps (Positron in light, Dark in dark mode), so roads, water and land cover
  actually render and the map matches the app theme.
- **Live sketch feedback**: floating area/perimeter read-out, vertex progress pill and a
  step-dot indicator; the polygon fill, connecting line and vertex markers now have distinct
  layers with a soft halo, plus in-map zoom and "fit region" controls.
- **Results as a report**: validation hero, metric grid, animated surface-anomaly gauge with a
  transparent component breakdown, satellite products with cloud-quality pills, terrain metric
  cards, provenance/caveat sections and a proper empty state that links back to the map.
- **Settings**: connection section with inline URL validation, typed test-connection result
  banner (success/failure), appearance picker, data-source cards and an about/licence block.
- **Branding**: new adaptive launcher icon (light/dark/monochrome), round icon variant and a
  dependency-free branded launch window (`launch_screen` layer-list) instead of a white flash.

#### Changed
- Floating pill navigation bar with animated selection capsule (replaces the stock bar).
- Edge-to-edge layout handled through `WindowInsets.safeDrawing`; screens respect the status
  bar, navigation pill and display cut-outs (`shortEdges`).
- All user-facing copy revised and fully translated (English + فارسی); no hardcoded UI strings.

#### Performance
- Map GeoJSON source is only rewritten when the sketch geometry actually changes (previously
  every recomposition rebuilt the feature collection, which stuttered during animations).
- Sketch layers install on a freshly loaded style without redundant look-ups.
- Theme flips reload the basemap in place and replay the sketch, so the map never resets.
- Icon/animation work is allocation-light (precomputed vectors, `graphicsLayer` scaling), and
  the launcher icon gained a monochrome variant for themed-icon rendering.

## [1.2.0] - 2026-11-07

### Added
- **Deep temporal-processing pipeline** (`backend/subsurface_api/deep/`, `/api/v1/deep/...`):
  - Copernicus Data Space **Process API** client — per-date 8-band UINT16 stacks
    (B02/B03/B04/B08/B11/B12/SCL/dataMask) with OAuth (password grant or client credentials),
    retry/back-off, and small bbox-only transfers (no full-scene downloads).
  - Preprocessing: baseline-4.0 reflectance harmonisation ((DN−1000)/10⁴) and SCL cloud/shadow/
    snow masking with a per-scene valid-fraction quality gate (≥ 55 % by default, ≥ 4 scenes).
  - Seven spectral indices: NDVI, NDWI, MNDWI, NDMI, NBR, BSI, albedo (NaN = invalid).
  - Robust temporal evidence: median/MAD z-scores, anomaly persistence over the recent window,
    Theil–Sen trends (per 30 days).
  - Unsupervised anomaly models: robust PCA (default) or a dependency-free numpy autoencoder
    (13→8→3→8→13, seeded, deterministic) → reconstruction-error percentile.
  - Transparent evidence fusion (0.25 moisture + 0.20 vegetation + 0.15 soil exposure +
    0.20 persistence + 0.20 deep model) with coherence and confidence classes.
  - Detections: 8-connected components (≥ 9 px), convex-hull GeoJSON polygons with geodesic area,
    mean/max score, persistence, coherence, confidence.
  - Artifacts per job: score/overlay/evidence PNGs, three EPSG:4326 GeoTIFFs (tifffile),
    detections.geojson, timeseries.json, full report.json.
  - Async job manager (single-worker executor, progress stages, artifact retention) and optional
    `X-API-Key` gate via `DEEP_API_KEY`.
  - `mode: selftest` — identical downstream chain on a deterministic synthetic region; verifies a
    deployment end-to-end without any Copernicus account (`POST /api/v1/deep/selftest`).
  - Browser console at `/deep-console` (MapLibre bbox picker → analyze → artifacts).
- `docs/DEEP-PROCESSING.md` — full mathematical specification + honest limitations.
- `docs/DEPLOY-RUNFLARE-FA.md` — complete Persian Runflare deployment guide (CLI, GitHub oAuth/
  classic, port mapping, Secrets, disk, post-deploy tests).
- `backend/requirements.txt` for PaaS/Docker builds expecting a plain requirements file.
- 20 new backend tests (indices math, robust statistics, labeling, GeoTIFF roundtrip, API selftest,
  artifact serving, credential gate) — suite now 50 tests, all green.

### Changed
- Version bump to 1.2.0 (app `versionCode` 3, backend package 1.2.0); `tifffile` dependency added.

## [1.1.0] - 2026-11-07

### Added
- Gradle wrapper fully committed (`gradlew`, `gradlew.bat`, `gradle-wrapper.jar`) — the CI workflow
  and local Termux builds now use `./gradlew` directly; no pre-installed Gradle needed anywhere.
- `:app:testDebugUnitTest` added to the APK workflow — GeoMath unit tests run on every CI build.
- Backend `Dockerfile` (+ `.dockerignore`) honouring `$PORT` with a container health check —
  deployable to RunFlare (Docker hosting), Hugging Face Spaces, or any Docker host.
- `scripts/termux-sign.sh` — one-shot Termux script: installs `openjdk-17`/`gh`, generates the
  RSA-4096 keystore, base64-encodes it and registers all four GitHub Secrets automatically.
- `scripts/upload-to-github.sh` — Termux-friendly `git` push that preserves the hidden
  `.github/workflows` folder (which the GitHub web uploader drops).
- `docs/QUICKSTART-FA.md` — complete Persian quick-start (zip → repo → APK → backend incl. RunFlare).
- `github-workflow-backup/` — visible copies of both workflow files with web-uploader recovery
  instructions (Persian + English).
- RunFlare free-tier deployment option documented in `docs/OPERATIONS.md` (option E).

### Changed
- Version bump to 1.1.0 (app `versionCode` 2, backend package 1.1.0).
- APK workflow: `gradle/actions/setup-gradle@v4` now used for dependency caching only; the build
  itself runs through the committed wrapper.

## [1.0.0] - 2026-11-07

### Added
- Native Android app: Kotlin 2.2, Jetpack Compose (Material 3), MapLibre Native 11 interactive map.
- Region sketching: tap to add 3–10 vertices, undo, clear, live geodesic area estimate.
- Local (offline) polygon validation fallback inside the app; server validation on top.
- FastAPI backend: strict polygon validation (geometry, vertex count, area bounds, self-intersection).
- Live Sentinel-2 L2A catalog metadata search via Copernicus Data Space Ecosystem OData API
  (anonymous, no API key), with cloud-cover filter and full provenance notes.
- Real terrain analysis from AWS Terrain Tiles (Terrarium DEM): elevation statistics, slope (Horn),
  roughness (TRI), gradient-orientation consistency, nodata handling, tile-count limits.
- Documented, weighted surface terrain-anomaly score with explicit scientific caveats
  (surface indicator only — not a buried-target probability).
- Android Settings screen: runtime API base URL override + connection health check.
- GitHub Actions workflows: automatic APK build (debug + release; signed when secrets present,
  unsigned otherwise; artifacts + tag releases) and backend test suite.
- Gradle release signing driven by environment variables (`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`,
  `KEY_ALIAS`, `KEY_PASSWORD`) — no keystore ever committed.
- Documentation: architecture, science scope, operations (data collection & registration),
  Termux signing guide (فارسی/English), roadmap.
- Persian (فارسی) UI localization; RTL support.
