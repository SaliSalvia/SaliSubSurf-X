# Security Policy

## Reporting a vulnerability

Please open a private GitHub security advisory on this repository (Security → Report a
vulnerability) instead of a public issue. You can expect an initial response within 7 days.

## Scope

* The Android app stores only an API base URL in `SharedPreferences`; it performs no analytics,
  no tracking, and requests only the `INTERNET` permission.
* The backend is a read-only analysis service. The reference deployment binds to `127.0.0.1` or a
  trusted LAN. If you expose it publicly, put it behind TLS and an authenticating reverse proxy.
* Release signing material must live only in GitHub Secrets (or your own secure storage). The
  repository never contains keystores; `.gitignore` blocks `*.keystore`, `*.jks`, and `*.b64`.

## Operational notes

* Request ids are opaque correlation tokens only; they never contain credentials, and the
  request log records method/path/status/duration — not headers or bodies.
* The container image runs as an unprivileged user (uid 10001) and writes only to its
  artifact directory.
* Release builds disable HTTP logging in the Android client.

## Known limitations

* The app talks to the backend over plain HTTP on local networks for development convenience
  (cleartext is enabled). For production, deploy the backend behind HTTPS and set the base URL to
  `https://...` in the in-app Settings screen.
