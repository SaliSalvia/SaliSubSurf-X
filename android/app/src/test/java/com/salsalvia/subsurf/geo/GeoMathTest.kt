package com.salsalvia.subsurf.geo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GeoMathTest {

    private val square = listOf(
        Vertex(0.0, 0.0),
        Vertex(0.0, 1.0),
        Vertex(1.0, 1.0),
        Vertex(1.0, 0.0),
    )

    @Test
    fun areaOfOneDegreeSquareNearEquator() {
        val area = GeoMath.sphericalAreaM2(square)
        assertTrue("area=$area", area > 1.20e10 && area < 1.26e10)
    }

    @Test
    fun areaScalesQuadratically() {
        val big = listOf(
            Vertex(0.0, 0.0), Vertex(0.0, 2.0), Vertex(2.0, 2.0), Vertex(2.0, 0.0),
        )
        val ratio = GeoMath.sphericalAreaM2(big) / GeoMath.sphericalAreaM2(square)
        assertEquals(4.0, ratio, 0.01)
    }

    @Test
    fun normalizeRingDropsClosingVertex() {
        val ring = GeoMath.normalizeRing(square + square.first())
        assertEquals(4, ring.size)
    }

    @Test
    fun perimeterIsReasonable() {
        val per = GeoMath.perimeterM(square)
        assertTrue("per=$per", per > 4.3e5 && per < 4.6e5)
    }

    @Test
    fun localCheckAcceptsValidSquare() {
        val payload = square.map { listOf(it.lon, it.lat) }
        assertTrue(GeoMath.localCheck(payload))
    }

    @Test
    fun localCheckRejectsBowtie() {
        val bowtie = listOf(
            listOf(0.0, 0.0), listOf(1.0, 1.0), listOf(1.0, 0.0), listOf(0.0, 1.0),
        )
        assertFalse(GeoMath.localCheck(bowtie))
    }

    @Test
    fun localCheckRejectsTooFewVertices() {
        assertFalse(GeoMath.localCheck(listOf(listOf(0.0, 0.0), listOf(1.0, 1.0))))
    }

    @Test
    fun compassLabels() {
        assertEquals("N", GeoMath.compassLabel(0.0))
        assertEquals("E", GeoMath.compassLabel(90.0))
        assertEquals("NW", GeoMath.compassLabel(315.0))
        assertEquals("N", GeoMath.compassLabel(360.0))
    }
}
