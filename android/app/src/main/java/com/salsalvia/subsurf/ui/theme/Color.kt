package com.salsalvia.subsurf.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Palette derived from the product logo: a black obsidian field, molten gold as the primary
 * signal, electric blue as the secondary and ember red/orange as the alert accent. The logo is
 * luminous on black, so the dark theme is the "native" one; the light theme is a bright,
 * daylight-mapping version of the same hues so the outdoor map use case stays readable.
 */

// --- Gold (primary) -------------------------------------------------------- //
val Gold900 = Color(0xFF3A2703)
val Gold800 = Color(0xFF5C3E05)
val Gold700 = Color(0xFF7C5507)
val Gold600 = Color(0xFF9C6B09)
val Gold500 = Color(0xFFC08A10)
val Gold400 = Color(0xFFE0A81E)
val Gold300 = Color(0xFFF5C542)
val Gold200 = Color(0xFFFFDB7A)
val Gold100 = Color(0xFFFFEDB8)

// --- Electric blue (secondary) --------------------------------------------- //
val Blue900 = Color(0xFF04203A)
val Blue800 = Color(0xFF063A63)
val Blue700 = Color(0xFF07527F)
val Blue600 = Color(0xFF0A6FA8)
val Blue500 = Color(0xFF1491D6)
val Blue400 = Color(0xFF35B4F2)
val Blue300 = Color(0xFF6DD0FF)
val Blue200 = Color(0xFFA9E5FF)
val Blue100 = Color(0xFFD6F3FF)

// --- Ember (tertiary / alert) ---------------------------------------------- //
val Ember700 = Color(0xFF8C2A06)
val Ember500 = Color(0xFFC2410C)
val Ember300 = Color(0xFFFF8A50)
val Ember100 = Color(0xFFFFD9C4)

// --- Neutrals: obsidian ---------------------------------------------------- //
val Obsidian = Color(0xFF050709)
val Ink950 = Color(0xFF070B10)
val Ink900 = Color(0xFF0A0F15)
val Ink850 = Color(0xFF0E141B)
val Ink800 = Color(0xFF121A22)
val Ink750 = Color(0xFF161F28)
val Ink700 = Color(0xFF1B252F)
val Ink600 = Color(0xFF26323D)
val Ink500 = Color(0xFF3A4854)
val Slate400 = Color(0xFF8595A3)
val Slate300 = Color(0xFFAEBCC8)
val Slate200 = Color(0xFFD0DAE2)

// --- Neutrals: daylight ---------------------------------------------------- //
val Paper = Color(0xFFFFFFFF)
val Daylight50 = Color(0xFFF6F8F9)
val Daylight100 = Color(0xFFEFF3F6)
val Daylight200 = Color(0xFFE7EDF1)
val Daylight300 = Color(0xFFDCE4EA)
val Daylight400 = Color(0xFFC9D4DC)
val Graphite700 = Color(0xFF3B4650)
val Graphite900 = Color(0xFF11171C)

// --- Semantic -------------------------------------------------------------- //
val ErrorLight = Color(0xFFB3261E)
val ErrorDark = Color(0xFFFFB4AB)
val ErrorContainerLight = Color(0xFFF9DEDC)
val ErrorContainerDark = Color(0xFF690005)

/** Accent colours used by the map sketch (kept in sync with the raw ARGB ints in RegionMapView). */
val Smoke = Color(0xFF6B7A88)
