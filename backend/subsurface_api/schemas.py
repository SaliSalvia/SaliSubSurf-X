"""Pydantic schemas — the single source of truth for the JSON contract used by the app."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _validate_polygon_pairs(v: List[List[float]]) -> List[List[float]]:
    """Shared shape check: an open/closed ring of distinct ``[lon, lat]`` pairs."""
    if len(v) < 3:
        raise ValueError("polygon needs at least 3 vertices")
    for p in v:
        if len(p) != 2:
            raise ValueError("each vertex must be a [lon, lat] pair")
    return v


class RegionRequest(BaseModel):
    """A sketched region. ``polygon`` is an open or closed ring of ``[lon, lat]`` pairs."""

    polygon: List[List[float]]
    name: Optional[str] = None

    @field_validator("polygon")
    @classmethod
    def _check_pairs(cls, v: List[List[float]]) -> List[List[float]]:
        return _validate_polygon_pairs(v)


class RegionCheckOut(BaseModel):
    valid: bool
    issues: List[str] = []
    warnings: List[str] = []
    vertex_count: int
    area_sqm: float
    area_hectares: float
    perimeter_m: float
    centroid: List[float]
    bbox: List[float]


class CatalogRequest(BaseModel):
    polygon: List[List[float]]
    date_from: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    max_cloud_percent: float = Field(30.0, ge=0.0, le=100.0)
    max_results: int = Field(15, ge=1, le=25)

    @field_validator("polygon")
    @classmethod
    def _check_pairs(cls, v: List[List[float]]) -> List[List[float]]:
        # Same contract as RegionRequest: fail fast with 422 on malformed vertices instead of
        # silently truncating triples or forwarding a degenerate ring to the geometry checks.
        return _validate_polygon_pairs(v)


class ProductSummary(BaseModel):
    id: str
    name: str
    processing_level: str = "S2MSI2A"
    datetime: Optional[str] = None
    cloud_cover_percent: Optional[float] = None
    size_mb: Optional[float] = None
    footprint: Optional[Any] = None


class ProvenanceNote(BaseModel):
    provider: str
    collection: Optional[str] = None
    licence_note: Optional[str] = None
    retrieved_at: Optional[str] = None


class CatalogResponse(BaseModel):
    region: RegionCheckOut
    products: List[ProductSummary] = []
    total_matched: int = 0
    provenance: List[ProvenanceNote] = []
    warnings: List[str] = []


class ElevationStats(BaseModel):
    min_m: float
    max_m: float
    mean_m: float
    std_m: float


class SlopeStats(BaseModel):
    mean_deg: float
    max_deg: float
    std_deg: float
    percent_over_15: float


class TerrainResponse(BaseModel):
    zoom: int
    resolution_m_per_px: float
    nodata_fraction: float
    tiles_fetched: int
    elevation: ElevationStats
    slope: SlopeStats
    roughness_tri_mean: float
    dominant_gradient_azimuth_deg: Optional[float] = None
    gradient_consistency: Optional[float] = None
    surface_anomaly_score: Optional[float] = None
    score_components: Dict[str, float] = {}
    score_definition: Optional[str] = None
    provenance: List[ProvenanceNote] = []
    caveats: List[str] = []


class HealthResponse(BaseModel):
    status: str
    version: str
    time_utc: str
