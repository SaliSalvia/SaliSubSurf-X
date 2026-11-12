"""Sentinel-2 L2A catalog metadata search.

Uses the Copernicus Data Space Ecosystem OData API **anonymously** — metadata search
requires no account, no API key and no token. Product *downloads* would require a free
account; that is out of scope for this service (metadata-only by design, see SCIENCE-SCOPE).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

import requests

from ..geo import ring_to_wkt

ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PROVIDER = "Copernicus Data Space Ecosystem"
COLLECTION = "SENTINEL-2"
PROCESSING_LEVEL_TOKEN = "MSIL2A"
LICENCE_NOTE = (
    "Copernicus Sentinel data — free, full and open access under the Copernicus Space "
    "Component Data Open Access licence. Catalog metadata retrieved anonymously."
)
MAX_RESULTS_LIMIT = 25

# Transient upstream states worth retrying; anything else fails fast.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
_sleep = time.sleep


def _retry_delay(resp: requests.Response | None, attempt: int) -> float:
    """Backoff for one failed attempt; honours a small ``Retry-After`` when present."""
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(5.0, max(0.0, float(retry_after)))
            except (TypeError, ValueError):
                pass
    return min(4.0, 0.5 * (2 ** attempt))


def build_filter(ring: Sequence[Tuple[float, float]], date_from: str, date_to: str) -> str:
    """OData $filter string: L2A products whose footprint intersects the polygon."""
    wkt = ring_to_wkt(ring)
    return (
        f"Collection/Name eq '{COLLECTION}'"
        f" and OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')"
        f" and ContentDate/Start gt {date_from}T00:00:00.000Z"
        f" and ContentDate/Start lt {date_to}T23:59:59.999Z"
        f" and contains(Name,'{PROCESSING_LEVEL_TOKEN}')"
    )


def parse_product(p: Dict[str, Any]) -> Dict[str, Any]:
    """Map one raw OData product entry to the API's ProductSummary shape."""
    name = p.get("Name", "")
    start = (p.get("ContentDate") or {}).get("Start")
    cloud: float | None = None
    for attr in p.get("Attributes") or []:
        # The live API uses "cloudCover"; older docs used "CloudCoverage".
        if attr.get("Name") in ("cloudCover", "CloudCoverage"):
            try:
                cloud = float(attr.get("Value"))
            except (TypeError, ValueError):
                cloud = None
            break
    length = p.get("ContentLength")
    size_mb = round(float(length) / 1048576.0, 1) if length else None
    return {
        "id": p.get("Id", ""),
        "name": name,
        "processing_level": "S2MSI2A" if PROCESSING_LEVEL_TOKEN in name else "S2",
        "datetime": start,
        "cloud_cover_percent": cloud,
        "size_mb": size_mb,
        "footprint": p.get("GeoFootprint"),
    }


def search_products(
    ring: Sequence[Tuple[float, float]],
    date_from: str,
    date_to: str,
    max_cloud_percent: float = 30.0,
    max_results: int = 15,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    """Query the catalog and return ``{products, total_matched, provenance, warnings}``."""
    params = {
        "$filter": build_filter(ring, date_from, date_to),
        "$expand": "Attributes",
        "$orderby": "ContentDate/Start desc",
        "$top": max(1, min(int(max_results), MAX_RESULTS_LIMIT)),
        # Ask for the full match count: $top only pages the returned products.
        "$count": "true",
    }
    resp: requests.Response | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = requests.get(
                ODATA_URL,
                params=params,
                timeout=timeout,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise RuntimeError(f"Could not reach the Copernicus catalog: {exc}") from exc
            _sleep(_retry_delay(None, attempt))
            continue

        if resp.status_code == 200:
            break
        if resp.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS - 1:
            _sleep(_retry_delay(resp, attempt))
            continue
        raise RuntimeError(
            f"Copernicus catalog returned HTTP {resp.status_code}. The service is "
            f"occasionally busy (HTTP 429/503) — retry in a few seconds."
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError("Copernicus catalog returned malformed JSON.") from exc

    raw = payload.get("value", []) or []
    products = [parse_product(p) for p in raw]
    kept = [
        p
        for p in products
        if p["cloud_cover_percent"] is None
        or p["cloud_cover_percent"] <= max_cloud_percent
    ]
    warnings: List[str] = []
    if raw and not kept:
        warnings.append(
            f"All {len(raw)} matched products exceed the {max_cloud_percent:.0f}% "
            f"cloud-cover limit. Widen the date range or raise the limit."
        )
    try:
        total_matched = int(payload.get("@odata.count"))
    except (TypeError, ValueError):
        total_matched = len(products)

    return {
        "products": kept,
        "total_matched": total_matched,
        "provenance": [
            {
                "provider": PROVIDER,
                "collection": COLLECTION,
                "licence_note": LICENCE_NOTE,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        ],
        "warnings": warnings,
    }
