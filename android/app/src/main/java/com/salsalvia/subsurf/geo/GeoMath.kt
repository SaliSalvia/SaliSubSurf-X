package com.salsalvia.subsurf.geo

import kotlin.math.abs
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/** One sketched vertex. Latitude/longitude in decimal degrees (EPSG:4326). */
data class Vertex(val lat: Double, val lon: Double)

/** Geodesic helpers mirroring the backend (same formulas, same rounding rules). */
object GeoMath {

    const val EARTH_RADIUS_M = 6378137.0
    const val MIN_VERTICES = 3
    const val MAX_VERTICES = 10

    fun normalizeRing(points: List<Vertex>): List<Vertex> {
        val ring = ArrayList<Vertex>(points.size)
        for (p in points) {
            if (ring.isEmpty() || ring.last() != p) ring.add(p)
        }
        if (ring.size >= 2 && ring.first() == ring.last()) ring.removeAt(ring.size - 1)
        return ring
    }

    /** Geodesic polygon area in m² (spherical excess; same formula as the backend/Turf.js). */
    fun sphericalAreaM2(ring: List<Vertex>): Double {
        if (ring.size < 3) return 0.0
        var total = 0.0
        val n = ring.size
        for (i in 0 until n) {
            val p1 = ring[i]
            val p2 = ring[(i + 1) % n]
            total += Math.toRadians(p2.lon - p1.lon) *
                (2.0 + sin(Math.toRadians(p1.lat)) + sin(Math.toRadians(p2.lat)))
        }
        return abs(total) * EARTH_RADIUS_M * EARTH_RADIUS_M / 2.0
    }

    fun haversineM(a: Vertex, b: Vertex): Double {
        val phi1 = Math.toRadians(a.lat)
        val phi2 = Math.toRadians(b.lat)
        val dPhi = Math.toRadians(b.lat - a.lat)
        val dLmb = Math.toRadians(b.lon - a.lon)
        val h = sin(dPhi / 2) * sin(dPhi / 2) +
            cos(phi1) * cos(phi2) * sin(dLmb / 2) * sin(dLmb / 2)
        return 2 * EARTH_RADIUS_M * asin(min(1.0, kotlin.math.sqrt(h)))
    }

    fun perimeterM(ring: List<Vertex>): Double {
        if (ring.size < 2) return 0.0
        var total = 0.0
        for (i in ring.indices) total += haversineM(ring[i], ring[(i + 1) % ring.size])
        return total
    }

    fun areaHectares(ring: List<Vertex>): Double = sphericalAreaM2(ring) / 10_000.0

    // ------------------------------------------------------------------ //
    // Offline validation fallback (mirrors backend/subsurface_api/validation.py)
    // ------------------------------------------------------------------ //

    /** Fast local sanity check used before any network request. */
    fun localCheck(polygonLonLat: List<List<Double>>): Boolean {
        val ring = normalizeRing(polygonLonLat.map { Vertex(lat = it[1], lon = it[0]) })
        if (ring.size !in MIN_VERTICES..MAX_VERTICES) return false
        for (v in ring) {
            if (v.lon !in -180.0..180.0 || v.lat !in -90.0..90.0) return false
        }
        return !hasSelfIntersection(ring)
    }

    /** O(n²) segment-intersection test — n ≤ 10 here, so brute force is fine. */
    fun hasSelfIntersection(ring: List<Vertex>): Boolean {
        val n = ring.size
        if (n < 4) return false
        for (i in 0 until n) {
            val a1 = ring[i]
            val a2 = ring[(i + 1) % n]
            for (j in i + 1 until n) {
                if (j == i || (j + 1) % n == i) continue
                val b1 = ring[j]
                val b2 = ring[(j + 1) % n]
                if (segmentsProperlyIntersect(a1, a2, b1, b2)) return true
            }
        }
        return false
    }

    private fun segmentsProperlyIntersect(p1: Vertex, p2: Vertex, p3: Vertex, p4: Vertex): Boolean {
        val d1 = cross(p3, p4, p1)
        val d2 = cross(p3, p4, p2)
        val d3 = cross(p1, p2, p3)
        val d4 = cross(p1, p2, p4)
        return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
            ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
    }

    private fun cross(a: Vertex, b: Vertex, c: Vertex): Double {
        val bx = b.lon - a.lon
        val by = b.lat - a.lat
        val cx = c.lon - a.lon
        val cy = c.lat - a.lat
        return bx * cy - by * cx
    }

    fun compassLabel(azimuthDeg: Double): String {
        val dirs = listOf("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        val normalized = ((azimuthDeg % 360.0) + 360.0) % 360.0
        val idx = ((normalized / 45.0) + 0.5).toInt() % 8
        return dirs[idx]
    }
}
