package com.salsalvia.subsurf.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * JSON contract — must stay in sync with backend/subsurface_api/schemas.py.
 * Field names are snake_case on the wire (matched with @SerialName).
 */

@Serializable
data class RegionRequest(
    @SerialName("polygon") val polygon: List<List<Double>>,
    @SerialName("name") val name: String? = null,
)

@Serializable
data class ValidationResponse(
    @SerialName("valid") val valid: Boolean,
    @SerialName("issues") val issues: List<String> = emptyList(),
    @SerialName("warnings") val warnings: List<String> = emptyList(),
    @SerialName("vertex_count") val vertexCount: Int = 0,
    @SerialName("area_sqm") val areaSqm: Double = 0.0,
    @SerialName("area_hectares") val areaHectares: Double = 0.0,
    @SerialName("perimeter_m") val perimeterM: Double = 0.0,
    @SerialName("centroid") val centroid: List<Double> = emptyList(),
    @SerialName("bbox") val bbox: List<Double> = emptyList(),
)

@Serializable
data class CatalogRequest(
    @SerialName("polygon") val polygon: List<List<Double>>,
    @SerialName("date_from") val dateFrom: String,
    @SerialName("date_to") val dateTo: String,
    @SerialName("max_cloud_percent") val maxCloudPercent: Double = 30.0,
    @SerialName("max_results") val maxResults: Int = 15,
)

@Serializable
data class ProductSummary(
    @SerialName("id") val id: String,
    @SerialName("name") val name: String,
    @SerialName("processing_level") val processingLevel: String = "S2MSI2A",
    @SerialName("datetime") val datetime: String? = null,
    @SerialName("cloud_cover_percent") val cloudCoverPercent: Double? = null,
    @SerialName("size_mb") val sizeMb: Double? = null,
)

@Serializable
data class ProvenanceNote(
    @SerialName("provider") val provider: String,
    @SerialName("collection") val collection: String? = null,
    @SerialName("licence_note") val licenceNote: String? = null,
    @SerialName("retrieved_at") val retrievedAt: String? = null,
)

@Serializable
data class CatalogResponse(
    @SerialName("region") val region: ValidationResponse,
    @SerialName("products") val products: List<ProductSummary> = emptyList(),
    @SerialName("total_matched") val totalMatched: Int = 0,
    @SerialName("provenance") val provenance: List<ProvenanceNote> = emptyList(),
    @SerialName("warnings") val warnings: List<String> = emptyList(),
)

@Serializable
data class ElevationStats(
    @SerialName("min_m") val minM: Double = 0.0,
    @SerialName("max_m") val maxM: Double = 0.0,
    @SerialName("mean_m") val meanM: Double = 0.0,
    @SerialName("std_m") val stdM: Double = 0.0,
)

@Serializable
data class SlopeStats(
    @SerialName("mean_deg") val meanDeg: Double = 0.0,
    @SerialName("max_deg") val maxDeg: Double = 0.0,
    @SerialName("std_deg") val stdDeg: Double = 0.0,
    @SerialName("percent_over_15") val percentOver15: Double = 0.0,
)

@Serializable
data class TerrainResponse(
    @SerialName("zoom") val zoom: Int = 0,
    @SerialName("resolution_m_per_px") val resolutionMPerPx: Double = 0.0,
    @SerialName("nodata_fraction") val nodataFraction: Double = 0.0,
    @SerialName("tiles_fetched") val tilesFetched: Int = 0,
    @SerialName("elevation") val elevation: ElevationStats = ElevationStats(),
    @SerialName("slope") val slope: SlopeStats = SlopeStats(),
    @SerialName("roughness_tri_mean") val roughnessTriMean: Double = 0.0,
    @SerialName("dominant_gradient_azimuth_deg") val dominantGradientAzimuthDeg: Double? = null,
    @SerialName("gradient_consistency") val gradientConsistency: Double? = null,
    @SerialName("surface_anomaly_score") val surfaceAnomalyScore: Double? = null,
    @SerialName("score_components") val scoreComponents: Map<String, Double> = emptyMap(),
    @SerialName("provenance") val provenance: List<ProvenanceNote> = emptyList(),
    @SerialName("caveats") val caveats: List<String> = emptyList(),
)

@Serializable
data class HealthResponse(
    @SerialName("status") val status: String,
    @SerialName("version") val version: String = "",
    @SerialName("time_utc") val timeUtc: String? = null,
)
