<p align="center">
  <img src="docs/images/wordmark_banner.png" alt="SaliSurf-X" width="720" />
</p>

<p align="center">
  <img src="docs/images/mother_logo_512.png" alt="SaliSurf-X mother logo" width="160" />
</p>

# SaliSurf-X

**An evidence-aware geospatial workspace for exploring satellite and terrain observations.**

> Formerly known as *SubsurfaceExplorer / Sal-Subsurf* — v1.5.0 introduced the
> **SaliSurf-X** brand; v1.6.0 brings the full brand identity (mother logo, wordmark,
> and signature) in-app. Same app, same package id, upgraded design system.

SaliSurf-X is an Android-first project for selecting survey areas, organizing geospatial
observations, and analysing verified satellite/terrain products. It is **not** a remote subsurface
scanner. Satellite imagery does not directly identify buried metal objects, tunnels, cavities, or
their depth. The project therefore focuses on mapping, region geometry, data provenance, and
defensible surface indicators.

## Status

* Native Android app (Kotlin, Jetpack Compose, Material 3, MapLibre Native 11).
* Region sketching on an interactive map (3–10 vertices, undo, clear, live area estimate).
* FastAPI backend with strict polygon validation and live Sentinel-2 L2A catalog metadata search
  (Copernicus Data Space Ecosystem, anonymous access, no API key).
* **Deep temporal processing (v1.3.0)** — real Sentinel-2 L2A pixel analysis via the Copernicus
  Process API: per-date 8-band stacks, SCL cloud masking, 7 spectral indices, robust multi-date
  statistics (median/MAD z-scores, persistence, Theil–Sen trend), an unsupervised anomaly model
  (robust PCA or numpy autoencoder), transparent evidence fusion (0–100), connected-component
  detections (GeoJSON + GeoTIFF + PNG overlay) and a browser console (`/deep-console`).
  Full spec: [docs/DEEP-PROCESSING.md](docs/DEEP-PROCESSING.md).
* Real terrain analysis from open global DEM tiles (AWS Terrain Tiles / Terrarium — no account):
  elevation statistics, slope, roughness (TRI), gradient-orientation consistency, and a documented,
  weighted **surface terrain-anomaly score** with full provenance and caveats.
* Android-to-API requests with loading, success, and error states; local offline validation fallback.
* **Design-system upgrade (v1.5.0)** — the whole product now reads as one instrument: a refreshed
  adaptive launcher icon with molten-gold signal chevrons over an obsidian glow, an Android 12+
  branded system splash, press-scale micro-interactions on every map control and dock button, and
  softer Material-easing screen transitions.
* **Operational UX (v1.4.1)** — a lockable camera while tracing, a Google-Maps-style scale bar, a
  startup backend probe with an offline notice, actionable failure banners with retry, and
  share/copy of the run summary. Release builds are R8-shrunk and use a scoped cleartext policy.
* Python unit tests and CI workflows.
* Scientific guardrails and a staged implementation roadmap.

Only Copernicus catalog **metadata** search, open DEM analysis, and the deep *surface-change*
pipeline are connected. Satellite full-scene downloads, user accounts, and buried-target
interpretation are **not** implemented, by design. The UI never fabricates results.

## Repository layout

```
android/       Android application (Kotlin + Compose + MapLibre)
backend/       Python geospatial API (FastAPI)
docs/          Architecture, science scope, operations, signing, roadmap
.github/       CI/CD: APK build workflow + backend tests
```

## Build the APK (GitHub Actions — fully automatic)

### One command from Termux (recommended)

Put the project ZIP in your phone's **Download** folder, then in Termux (with `gh` already
logged in — see [docs/SIGNING-TERMUX.md](docs/SIGNING-TERMUX.md)):

```bash
bash salisurf-x-deploy.sh
```

The script is fully interactive and does **everything**: creates a new `SaliSurf-X` repository,
extracts and pushes the project, creates your personal signing keystore right in the terminal
(hidden password prompts), registers the four signing secrets, watches the Actions build, waits
for the GitHub Release — and downloads the final APK(s) back to your Download folder.

### Step by step (the manual equivalent)

1. Create a new **empty** GitHub repository (public recommended — Actions are free and unlimited).
2. Upload the contents of this folder to the repository — **push with `git`** (recommended, keeps
   the hidden `.github/` workflow folder):
   ```bash
   bash scripts/upload-to-github.sh https://github.com/USER/REPO.git
   ```
   The GitHub *web* uploader drops dot-folders; if you use it anyway, recreate the workflows from
   `github-workflow-backup/` (see its README). Persian walkthrough: `docs/QUICKSTART-FA.md`.
3. GitHub Actions (`.github/workflows/android.yml`) runs automatically and builds:
   * `SaliSurf-X-debug.apk` — always
   * `SaliSurf-X-release-signed.apk` — **if you added signing secrets**, otherwise
     `SaliSurf-X-release-unsigned.apk`
   * It also runs the app's unit tests on every build.
4. **Every push to `main` also publishes a GitHub Release** (tag `v` + the `versionName` from
   `android/app/build.gradle.kts`) with both APKs attached — no manual tagging needed. Pushing a
   `v*` tag publishes a release pinned to that tag. Bump the version to mint a fresh release.
5. Download the APKs from the Releases page (or the run's *Artifacts*).

### Sign releases with your own key (Termux)

No external service is required. The all-in-one deploy script (`salisurf-x-deploy.sh`, above)
handles signing as part of the flow. To add or refresh signing on an *existing* repository, run
the one-shot helper (installs tools, generates the keystore interactively — hidden password
prompts — and registers all four secrets via `gh`):

```bash
bash scripts/termux-sign.sh
```

…or follow the manual step-by-step guide:
[docs/SIGNING-TERMUX.md](docs/SIGNING-TERMUX.md) (فارسی + English).

| Secret | Meaning |
| --- | --- |
| `KEYSTORE_BASE64` | Base64 of your `.keystore` file |
| `KEYSTORE_PASSWORD` | Keystore password |
| `KEY_ALIAS` | Key alias |
| `KEY_PASSWORD` | Key password (for PKCS12 = keystore password) |

## Run the backend

```bash
cd backend
python -m venv .venv
# Activate the environment, then:
python -m pip install -e ".[dev]"
uvicorn subsurface_api.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`.

Operations: `GET /api/v1/health` is a dependency-free liveness probe, `GET /api/v1/ready`
returns `503` unless the artifact directory is writable (used by the container health check),
and every response includes an `X-Request-ID` that also appears in the server log line.

## Open the Android app

Open `android/` in Android Studio with JDK 17+, Android SDK Platform 36, and Build Tools 36.0.0.
The Gradle build uses Kotlin DSL and a version catalog. The **complete Gradle wrapper is committed**
(`gradlew` + JAR, Gradle 8.14.6), so both CI and local builds (`./gradlew :app:assembleDebug`)
work without installing anything — the wrapper downloads Gradle itself.

### Use the app (the 60-second version)

1. **Find your area.** The app opens on the globe — drag to pan, pinch to zoom, use
   *back to globe* / *fit* on the right edge. A scale bar tells you how big the view is.
2. **Lock.** Press **Lock**. The camera freezes (gestures are off) so a tap can only ever place a
   corner of your boundary.
3. **Trace.** Tap 3–10 corners. The boundary is drawn as a **red-and-black dashed** ring over a
   faint gold fill, and live area/perimeter update as you go. *Undo* removes the last corner.
4. **Collect.** Press **Collect data**. One run validates the polygon with the server, searches the
   last 90 days of Sentinel-2 catalog (< 30 % cloud), and then fetches the terrain indicators
   automatically. A staged overlay shows which step is running.
5. **Read the report.** You land on **Results** with the validation, the catalog and the terrain
   metrics (elevation, slope, roughness, surface-anomaly score). **Share** or **Copy** exports the
   run as plain text — the scientific caveat is always included.

If anything fails, the banner tells you *why* (server not found, timeout, connection refused) and
offers **Try again** — you never have to re-draw the polygon.

### Connect the Android app to the backend

Start the API on your development computer
(`uvicorn subsurface_api.main:app --host 0.0.0.0 --port 8000`). The Android emulator uses
`http://10.0.2.2:8000/` by default. For a physical phone, open **Settings** inside the app and set
the API base URL to your computer's LAN address, e.g. `http://192.168.1.20:8000/`. You can also
pass it at build time:

```bash
gradle -PAPI_BASE_URL=http://192.168.1.20:8000/ :app:assembleDebug
```

The runtime value in Settings always wins over the build-time default, so you never need to rebuild
just to change the endpoint. Settings shows a live **Online / Offline / Checking…** pill, and the
map shows a dismissible notice when the backend is unreachable, so a wrong address is obvious
immediately rather than at the first collection run.

**What the failure messages mean**

| Message | Cause | Fix |
| --- | --- | --- |
| `Server not found` | DNS/host typo, or the app is on a different network | Fix the address in Settings |
| `Cannot reach the server` | Nothing is listening on that host/port | Start the backend; check `--host 0.0.0.0` |
| `The server took too long` | Terrain/DEM window too large, or a slow link | Retry, or lock a smaller area |
| `Network problem` | No connectivity / captive portal | Fix the connection |

The app permits cleartext HTTP for self-hosted backends (LAN addresses such as
`192.168.x.x`, the emulator's `10.0.2.2`, `localhost`, Termux) because Android's network
security config cannot scope private IP ranges — and a LAN host has no TLS certificate. HTTPS
is always available and preferred for every host that supports it (VPS, Runflare, a reverse
proxy). Details and rationale: `android/app/src/main/res/xml/network_security_config.xml`.
Practical deployment options (LAN, ADB reverse, Termux on the same
phone, **Runflare**, VPS + HTTPS) are described in [docs/OPERATIONS.md](docs/OPERATIONS.md),
[docs/DEPLOY-RUNFLARE-FA.md](docs/DEPLOY-RUNFLARE-FA.md) (راهنمای کامل فارسی رانفلر) and
[docs/QUICKSTART-FA.md](docs/QUICKSTART-FA.md) (فارسی).

### Deep processing API (v1.3.0)

```bash
# offline end-to-end validation (no Copernicus account needed)
curl -X POST "http://127.0.0.1:8000/api/v1/deep/selftest?grid=160"
# native 10 m tiling selftest:  /api/v1/deep/selftest?resolution_m=10

# real analysis — needs CDSE credentials in the environment (see docs/DEEP-PROCESSING.md)
curl -X POST http://127.0.0.1:8000/api/v1/deep/analyze -H 'Content-Type: application/json' \
  -d '{"polygon":[[52.50,29.55],[52.70,29.55],[52.70,29.70],[52.50,29.70]],
       "date_from":"2026-06-01","date_to":"2026-11-07","grid":512,"mode":"live"}'
```

Browser console: `http://127.0.0.1:8000/deep-console`. Full endpoint list and the exact math:
[docs/DEEP-PROCESSING.md](docs/DEEP-PROCESSING.md).

## Scientific guardrails

1. A surface anomaly is not evidence of a buried target.
2. Optical, thermal, SAR, and elevation datasets have different spatial/temporal resolutions,
   processing artefacts, and license terms.
3. No depth estimate or object-type classification is emitted without a validated physical model
   and site-specific ground truth.
4. Every observation retains provider, product ID, acquisition time, processing version, spatial
   resolution, quality flags, and licence/provenance metadata.
5. Field confirmation needs suitable ground-based methods (e.g. EMI, magnetometry, or GPR), chosen
   for the target and geology.

See [docs/SCIENCE-SCOPE.md](docs/SCIENCE-SCOPE.md) (indicator definitions and scoring),
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/OPERATIONS.md](docs/OPERATIONS.md) (data
collection & registration), and [docs/ROADMAP.md](docs/ROADMAP.md).

## Licensing

Application/backend source: MIT. Documentation: CC BY 4.0.
See `LICENSE` and `docs/LICENSE-DOCS.md`.
