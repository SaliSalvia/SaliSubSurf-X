"""Copernicus Data Space Ecosystem — Process API client (pixel data, not metadata).

Unlike the catalog module (anonymous OData metadata search), downloading *pixels*
requires a free CDSE account. Two authentication flavours are supported:

* username/password (``grant_type=password``, ``client_id=cdse-public``) — the
  personal-account flow documented by CDSE;
* an OAuth client created in the CDSE Data Space Profile
  (``grant_type=client_credentials`` with client id + secret).

Credentials are read from the environment and are never logged:

* ``COPERNICUS_USERNAME`` / ``COPERNICUS_PASSWORD``   (personal account), or
* ``COPERNICUS_CLIENT_ID`` / ``COPERNICUS_CLIENT_SECRET`` (OAuth client).

Pixel requests go to the Sentinel Hub-compatible Process API
(https://sh.dataspace.copernicus.eu/api/v1/process) with a small evalscript that
returns an 8-band UINT16 stack:
    B02 B03 B04 B08 B11 B12 SCL dataMask
Only the requested bbox at the requested grid is downloaded (tens of KB per
date) — full scenes (~1 GB) are never transferred.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Sequence, Tuple

import numpy as np
import requests
import tifffile

log = logging.getLogger("subsurface_api.deep.cdse")

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
PROVIDER = "Copernicus Data Space Ecosystem — Process API (sentinel-2-l2a)"

# Processing baseline >= 04.00 (Jan 2022) stores DN = reflectance*10000 + 1000.
# Override via env if Copernicus ever changes the offset.
DN_OFFSET = float(os.environ.get("S2_DN_OFFSET", "1000"))

BAND_ORDER: Tuple[str, ...] = ("B02", "B03", "B04", "B08", "B11", "B12", "SCL", "dataMask")

# CRITICAL (v1.3.0): reflectance bands MUST be requested with units:"DN".
# Without it the Process API serves default REFLECTANCE units (floats in
# [0,1]) which truncate to 0/1 when cast to the UINT16 sample type — every
# pixel then fails the (DN-1000)/10000 harmonisation and live mode returns
# garbage. SCL/dataMask are classification/mask bands and take no units.
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [
      { bands: ["B02", "B03", "B04", "B08", "B11", "B12"], units: "DN" },
      ["SCL", "dataMask"]
    ],
    output: { bands: 8, sampleType: "UINT16" }
  };
}
function evaluatePixel(s) {
  return [s.B02, s.B03, s.B04, s.B08, s.B11, s.B12, s.SCL, s.dataMask];
}
"""


class DeepAuthError(RuntimeError):
    """Raised when CDSE credentials are missing or rejected."""


class DeepFetchError(RuntimeError):
    """Raised when the Process API keeps failing after retries."""


def credentials_present() -> bool:
    """True when at least one credential pair is configured in the environment."""
    return bool(
        (os.environ.get("COPERNICUS_USERNAME") and os.environ.get("COPERNICUS_PASSWORD"))
        or (os.environ.get("COPERNICUS_CLIENT_ID") and os.environ.get("COPERNICUS_CLIENT_SECRET"))
    )


def get_token(timeout: float = 30.0) -> str:
    """Fetch an access token using whichever credential pair is configured."""
    username = os.environ.get("COPERNICUS_USERNAME")
    password = os.environ.get("COPERNICUS_PASSWORD")
    client_id = os.environ.get("COPERNICUS_CLIENT_ID")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET")

    if username and password:
        data = {
            "grant_type": "password",
            "client_id": "cdse-public",
            "username": username,
            "password": password,
        }
    elif client_id and client_secret:
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    else:
        raise DeepAuthError(
            "No Copernicus credentials configured. Set COPERNICUS_USERNAME/"
            "COPERNICUS_PASSWORD (free account) or COPERNICUS_CLIENT_ID/"
            "COPERNICUS_CLIENT_SECRET (OAuth client) as environment variables."
        )

    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=timeout)
    except requests.RequestException as exc:
        raise DeepAuthError(f"Could not reach the CDSE identity server: {exc}") from exc
    if resp.status_code != 200:
        raise DeepAuthError(
            f"CDSE rejected the credentials (HTTP {resp.status_code}). Check the "
            "account exists, is verified, and the password/client secret is current."
        )
    token = resp.json().get("access_token")
    if not token:
        raise DeepAuthError("CDSE token response contained no access_token.")
    return str(token)


def _process_payload(
    ring: Sequence[Tuple[float, float]],
    date_iso: str,
    width: int,
    height: int,
    max_cloud_percent: float,
    resampling: str = "nearest",
) -> Dict:
    closed = list(ring) + [ring[0]]
    resampling = resampling if resampling in ("nearest", "bilinear", "bicubic") else "nearest"
    return {
        "input": {
            "bounds": {
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[float(lon), float(lat)] for lon, lat in closed]],
                },
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{date_iso}T00:00:00Z",
                            "to": f"{date_iso}T23:59:59Z",
                        },
                        "maxCloudCoverage": float(max_cloud_percent),
                    },
                    "processing": {"resampling": resampling},
                }
            ],
        },
        "output": {
            "width": int(width),
            "height": int(height),
            "responses": [
                {"identifier": "default", "format": {"type": "image/tiff"}}
            ],
        },
        "evalscript": EVALSCRIPT,
    }


def fetch_scene_stack(
    token: str,
    ring: Sequence[Tuple[float, float]],
    date_iso: str,
    width: int,
    height: int,
    max_cloud_percent: float = 20.0,
    timeout: float = 90.0,
    retries: int = 3,
    resampling: str = "nearest",
) -> np.ndarray:
    """Download one date as a ``(height, width, 8)`` UINT16 stack.

    ``resampling``: "nearest" preserves the native DN grid; "bilinear"/
    "bicubic" are smoother when the requested grid is finer than the band GSD
    (B11/B12 are 20 m native). Retries on 429/5xx with linear back-off (the
    free Process API rate-limits politely). Raises :class:`DeepFetchError`
    after ``retries`` failures.
    """
    payload = _process_payload(ring, date_iso, width, height, max_cloud_percent, resampling)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    last_err = "unknown error"
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.post(PROCESS_URL, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last_err = f"network error: {exc}"
        else:
            if resp.status_code == 200 and resp.content:
                try:
                    stack = tifffile.imread(__import__("io").BytesIO(resp.content))
                except Exception as exc:  # corrupt TIFF body
                    last_err = f"unreadable TIFF body: {exc}"
                else:
                    arr = np.asarray(stack)
                    if arr.ndim == 3 and arr.shape[2] == len(BAND_ORDER):
                        return arr.astype(np.uint16)
                    last_err = f"unexpected stack shape {arr.shape}"
            elif resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code} (busy/rate-limited)"
            else:
                detail = resp.text[:200] if resp.text else ""
                raise DeepFetchError(
                    f"Process API HTTP {resp.status_code} for {date_iso}: {detail}"
                )
        # Never sleep after the final attempt: it only delays the error by
        # 4-12 s per date and buys no extra chance of success.
        if attempt < max(1, retries):
            sleep_s = 4.0 * attempt
            log.info("CDSE fetch retry %d/%d for %s (%s) — sleeping %.0fs",
                     attempt, retries, date_iso, last_err, sleep_s)
            time.sleep(sleep_s)
    raise DeepFetchError(f"Process API failed for {date_iso}: {last_err}")


def plan_dates(
    date_from: str,
    date_to: str,
    max_dates: int,
) -> List[str]:
    """Newest-first candidate acquisition dates (daily stepping, capped)."""
    from datetime import datetime as _datetime, timedelta as _td

    d0 = _datetime.strptime(date_from, "%Y-%m-%d").date()
    d1 = _datetime.strptime(date_to, "%Y-%m-%d").date()
    today = _datetime.now(timezone_utc()).date()
    if d1 > today:
        d1 = today
    if d0 > d1:
        return []
    dates: List[str] = []
    cur = d1
    while cur >= d0 and len(dates) < int(max_dates):
        dates.append(cur.isoformat())
        cur -= _td(days=1)
    return dates


def timezone_utc():
    from datetime import timezone

    return timezone.utc
