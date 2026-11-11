package com.salsalvia.subsurf.map

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The scale bar is the only piece of new "maths" in the UI layer, so it is pinned down here:
 * it must always snap to a 1/2/5 × 10^n value and never be smaller than the requested distance
 * (otherwise the bar would claim a longer distance than it draws).
 */
class ScaleBarTest {

    @Test
    fun snapsToNiceValues() {
        assertEquals(1.0, niceDistance(0.7), 1e-9)
        assertEquals(2.0, niceDistance(1.3), 1e-9)
        assertEquals(5.0, niceDistance(4.1), 1e-9)
        assertEquals(10.0, niceDistance(9.9), 1e-9)
        assertEquals(200.0, niceDistance(120.0), 1e-9)
        assertEquals(5000.0, niceDistance(4100.0), 1e-9)
    }

    @Test
    fun neverUnderstatesTheDistance() {
        val samples = listOf(0.03, 0.4, 1.0, 7.9, 63.0, 780.0, 12345.0, 987654.0)
        samples.forEach { value ->
            assertTrue("niceDistance($value) < $value", niceDistance(value) >= value)
        }
    }

    @Test
    fun handlesDegenerateInput() {
        assertEquals(1.0, niceDistance(0.0), 1e-9)
        assertEquals(1.0, niceDistance(-5.0), 1e-9)
        assertEquals(1.0, niceDistance(Double.NaN), 1e-9)
    }

    @Test
    fun formatsMetresAndKilometres() {
        assertEquals("500 m", formatDistance(500.0))
        assertEquals("2 km", formatDistance(2000.0))
        assertEquals("50 cm", formatDistance(0.5))
    }
}
