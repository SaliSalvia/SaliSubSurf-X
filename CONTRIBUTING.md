# Contributing

Thanks for considering a contribution to SaliSurf-X.

## Ground rules

1. **Scientific honesty first.** Do not add features that claim to detect buried objects, estimate
   depths, or classify targets from satellite data. Claims must follow the guardrails in
   `docs/SCIENCE-SCOPE.md`.
2. **Provenance is mandatory.** Every new data source must expose provider, product/layer ID,
   acquisition time, processing version, resolution, quality flags, and licence terms.
3. **No secrets in code.** Never commit keystores, tokens, or credentials. Signing on CI is done via
   GitHub Secrets only.

## Development

* Android: open `android/` in Android Studio (JDK 17+, SDK Platform 36). Code style: ktlint-friendly
  Kotlin, 4-space indent (see `.editorconfig`).
* Backend: `cd backend && python -m pip install -e ".[dev]"`, run tests with `pytest -q`.
  Formatting: PEP 8, 4-space indent, line length 100.

## Pull requests

* Keep PRs focused; update `CHANGELOG.md`.
* CI must pass: `Backend tests` and `Android APK` workflows.
* Any user-visible string must exist in both `values/strings.xml` (English) and
  `values-fa/strings.xml` (Persian).
