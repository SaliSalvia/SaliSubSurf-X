package com.salsalvia.subsurf.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import com.salsalvia.subsurf.data.ThemeMode

/**
 * Light scheme — a daylight "field instrument": crisp white surfaces, gold as the accent for
 * actions, blue for data/secondary and ember for caution. Gold is darkened here so body-level
 * gold text still clears AA on white.
 */
private val LightColors = lightColorScheme(
    primary = Gold700,
    onPrimary = Color.White,
    primaryContainer = Gold100,
    onPrimaryContainer = Gold900,
    inversePrimary = Gold300,

    secondary = Blue700,
    onSecondary = Color.White,
    secondaryContainer = Blue100,
    onSecondaryContainer = Blue900,

    tertiary = Ember700,
    onTertiary = Color.White,
    tertiaryContainer = Ember100,
    onTertiaryContainer = Color(0xFF3D1200),

    background = Daylight50,
    onBackground = Graphite900,
    surface = Paper,
    onSurface = Graphite900,
    surfaceVariant = Daylight200,
    onSurfaceVariant = Graphite700,
    surfaceTint = Gold600,
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFFBFCFD),
    surfaceContainer = Daylight100,
    surfaceContainerHigh = Daylight200,
    surfaceContainerHighest = Daylight300,
    inverseSurface = Ink800,
    inverseOnSurface = Daylight100,

    outline = Daylight400,
    outlineVariant = Daylight300,

    error = ErrorLight,
    onError = Color.White,
    errorContainer = ErrorContainerLight,
    onErrorContainer = Color(0xFF410E0B),
)

/**
 * Dark scheme — the logo's native environment: obsidian surfaces with gold signal, electric
 * blue data accents and ember alerts. Kept deliberately deep (near #050709) so the map and the
 * luminous gold read like the icon.
 */
private val DarkColors = darkColorScheme(
    primary = Gold300,
    onPrimary = Gold900,
    primaryContainer = Gold800,
    onPrimaryContainer = Gold100,
    inversePrimary = Gold600,

    secondary = Blue300,
    onSecondary = Blue900,
    secondaryContainer = Blue800,
    onSecondaryContainer = Blue100,

    tertiary = Ember300,
    onTertiary = Color(0xFF3D1200),
    tertiaryContainer = Ember700,
    onTertiaryContainer = Ember100,

    background = Ink950,
    onBackground = Slate200,
    surface = Ink900,
    onSurface = Slate200,
    surfaceVariant = Ink700,
    onSurfaceVariant = Slate300,
    surfaceTint = Gold300,
    surfaceContainerLowest = Obsidian,
    surfaceContainerLow = Ink950,
    surfaceContainer = Ink850,
    surfaceContainerHigh = Ink800,
    surfaceContainerHighest = Ink750,
    inverseSurface = Slate200,
    inverseOnSurface = Ink900,

    outline = Ink500,
    outlineVariant = Ink600,

    error = ErrorDark,
    onError = Color(0xFF690005),
    errorContainer = ErrorContainerDark,
    onErrorContainer = Color(0xFFFFDAD6),
)

val SubsurfShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(30.dp),
)

/** Spacing / sizing tokens that are not part of [MaterialTheme]. */
object Dims {
    val xs = 4.dp
    val s = 8.dp
    val m = 12.dp
    val l = 16.dp
    val xl = 20.dp
    val xxl = 28.dp
    val minTouch = 48.dp
}

/** Resolves the user's stored appearance preference against the current system setting. */
@Composable
fun ThemeMode.isDarkTheme(): Boolean = when (this) {
    ThemeMode.SYSTEM -> isSystemInDarkTheme()
    ThemeMode.LIGHT -> false
    ThemeMode.DARK -> true
}

@Composable
fun SubsurfTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    val view = LocalView.current
    if (!view.isInEditMode) {
        val context = LocalContext.current
        SideEffect {
            val window = (context as? Activity)?.window ?: return@SideEffect
            // Edge-to-edge: bars stay transparent, icon colour follows the scheme.
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !darkTheme
                isAppearanceLightNavigationBars = !darkTheme
            }
        }
    }
    MaterialTheme(
        colorScheme = colors,
        typography = SubsurfTypography,
        shapes = SubsurfShapes,
        content = content,
    )
}
