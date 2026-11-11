package com.salsalvia.subsurf.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.sp

/**
 * Type scale tuned for dense, data-first screens: tight titles, comfortable body copy,
 * slightly tracked labels. Font sizes follow the Material 3 scale so accessibility font
 * scaling keeps working as expected.
 */
private val Sans = FontFamily.SansSerif

private val tightLineHeight = LineHeightStyle(
    alignment = LineHeightStyle.Alignment.Center,
    trim = LineHeightStyle.Trim.None,
)

private fun style(
    size: Int,
    line: Int,
    weight: FontWeight = FontWeight.Normal,
    tracking: Double = 0.0,
): TextStyle = TextStyle(
    fontFamily = Sans,
    fontWeight = weight,
    fontSize = size.sp,
    lineHeight = line.sp,
    letterSpacing = tracking.sp,
    lineHeightStyle = tightLineHeight,
)

val SubsurfTypography = Typography(
    displayLarge = style(52, 58, FontWeight.Bold, -1.0),
    displayMedium = style(42, 48, FontWeight.Bold, -0.8),
    displaySmall = style(34, 40, FontWeight.SemiBold, -0.5),
    headlineLarge = style(30, 36, FontWeight.Bold, -0.4),
    headlineMedium = style(26, 32, FontWeight.Bold, -0.3),
    headlineSmall = style(23, 29, FontWeight.SemiBold, -0.2),
    titleLarge = style(20, 26, FontWeight.SemiBold, -0.1),
    titleMedium = style(16, 22, FontWeight.SemiBold, 0.1),
    titleSmall = style(14, 20, FontWeight.SemiBold, 0.1),
    bodyLarge = style(16, 24, FontWeight.Normal, 0.15),
    bodyMedium = style(14, 21, FontWeight.Normal, 0.2),
    bodySmall = style(13, 18, FontWeight.Normal, 0.25),
    labelLarge = style(14, 19, FontWeight.SemiBold, 0.2),
    labelMedium = style(12, 16, FontWeight.Medium, 0.4),
    labelSmall = style(11, 15, FontWeight.Medium, 0.5),
)
