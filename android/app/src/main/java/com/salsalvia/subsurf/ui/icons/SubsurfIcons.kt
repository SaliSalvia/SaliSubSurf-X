package com.salsalvia.subsurf.ui.icons

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/**
 * A tiny, hand-built icon set on a single 24dp grid with a 1.8-unit optical stroke.
 *
 * Every glyph is stored as SVG path data and compiled through
 * [androidx.compose.ui.graphics.vector.addPathNodes], the documented public API for building
 * vectors programmatically. Drawing these locally keeps the APK small: the official
 * `material-icons-extended` artifact alone is several megabytes of mostly unused glyphs.
 *
 * Geometry notes: circles are written as two half arcs with the relative form
 * `a r r 0 1 1 0 2r`, which always renders (the absolute two-arc idiom collapses when both arc
 * endpoints are identical).
 */
object SubsurfIcons {

    /** Stroked, open/closed line art. */
    private fun line(name: String, vararg paths: String): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            for (data in paths) {
                addPath(
                    pathData = addPathNodes(data),
                    stroke = SolidColor(Color.Black),
                    strokeLineWidth = 1.8f,
                    strokeLineCap = StrokeCap.Round,
                    strokeLineJoin = StrokeJoin.Round,
                )
            }
        }.build()

    /** Solid silhouettes (dots, badges, sparkles). */
    private fun solid(name: String, vararg paths: String): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            for (data in paths) {
                addPath(pathData = addPathNodes(data), fill = SolidColor(Color.Black))
            }
        }.build()

    // ----------------------------------------------------------------------- //
    // Navigation & primary actions
    // ----------------------------------------------------------------------- //

    /** Survey region: a closed sketch polygon with vertex dots. */
    val Region: ImageVector by lazy {
        ImageVector.Builder(
            name = "Region",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes("M4.6,8.6 L12,3.6 L19.8,8.1 L18.1,18.4 L6.3,19.4 Z"),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineJoin = StrokeJoin.Round,
            )
            addPath(
                pathData = addPathNodes(
                    "M12,2.9 a1.3,1.3 0 1 1 0,2.6 a1.3,1.3 0 1 1 0,-2.6 Z " +
                        "M4.6,7.3 a1.3,1.3 0 1 1 0,2.6 a1.3,1.3 0 1 1 0,-2.6 Z " +
                        "M19.8,6.8 a1.3,1.3 0 1 1 0,2.6 a1.3,1.3 0 1 1 0,-2.6 Z",
                ),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Layered map sheets. */
    val Layers: ImageVector by lazy {
        line(
            "Layers",
            "M12,3.5 L21,8.5 L12,13.5 L3,8.5 Z",
            "M3,13 L12,18 L21,13",
        )
    }

    /** Terrain / hillshade. */
    val Terrain: ImageVector by lazy {
        line("Terrain", "M2.5,19 L9,6.5 L13,13.5 L16,9 L21.5,19 Z")
    }

    /** Analysis / bar chart. */
    val Analytics: ImageVector by lazy {
        line(
            "Analytics",
            "M5,19.5 L5,13",
            "M12,19.5 L12,5.5",
            "M19,19.5 L19,9.5",
        )
    }

    /** Appearance / half-filled disc. */
    val Theme: ImageVector by lazy {
        ImageVector.Builder(
            name = "Theme",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes("M12,3 a9,9 0 1 1 0,18 a9,9 0 1 1 0,-18 Z"),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
            )
            addPath(
                pathData = addPathNodes("M12,3.2 a8.8,8.8 0 0 1 0,17.6 Z"),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Connectivity / signal arcs. */
    val Signal: ImageVector by lazy {
        ImageVector.Builder(
            name = "Signal",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes(
                    "M3,8.5 a13,13 0 0 1 18,0 " +
                        "M6.2,12.4 a8.2,8.2 0 0 1 11.6,0 " +
                        "M9.4,16.2 a4.2,4.2 0 0 1 5.2,0",
                ),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineCap = StrokeCap.Round,
            )
            addPath(
                pathData = addPathNodes("M12,17.4 a2.1,2.1 0 1 1 0,4.2 a2.1,2.1 0 1 1 0,-4.2 Z"),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** North arrow / orientation. */
    val Compass: ImageVector by lazy {
        ImageVector.Builder(
            name = "Compass",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes("M12,3 a9,9 0 1 1 0,18 a9,9 0 1 1 0,-18 Z"),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
            )
            addPath(
                pathData = addPathNodes("M16.2,7.8 L13.6,13.6 L7.8,16.2 L10.4,10.4 Z"),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Fit-to-region crosshair. */
    val Fit: ImageVector by lazy {
        line(
            "Fit",
            "M3.5,8.5 L3.5,3.5 L8.5,3.5",
            "M15.5,3.5 L20.5,3.5 L20.5,8.5",
            "M20.5,15.5 L20.5,20.5 L15.5,20.5",
            "M8.5,20.5 L3.5,20.5 L3.5,15.5",
        )
    }

    /** Ruler / measurement. */
    val Ruler: ImageVector by lazy {
        line(
            "Ruler",
            "M3,8.5 L21,8.5 L21,15.5 L3,15.5 Z",
            "M7,8.5 L7,12",
            "M11,8.5 L11,12",
            "M15,8.5 L15,12",
        )
    }

    /** Provenance / verified source shield. */
    val Provenance: ImageVector by lazy {
        line(
            "Provenance",
            "M12,3 L20,6 L20,12 C20,16.6 16.4,20.2 12,21.2 C7.6,20.2 4,16.6 4,12 L4,6 Z",
            "M8.6,11.8 L11.2,14.4 L15.6,9.2",
        )
    }

    /** Caution / caveats. */
    val Caveat: ImageVector by lazy {
        line(
            "Caveat",
            "M12,3.6 L21.2,19.8 L2.8,19.8 Z",
            "M12,9.2 L12,14",
            "M12,16.4 L12,16.9",
        )
    }

    /** Sparkle accent used on headline badges. */
    val Sparkle: ImageVector by lazy {
        solid(
            "Sparkle",
            "M12,2.6 L13.8,10.2 L21.4,12 L13.8,13.8 L12,21.4 L10.2,13.8 L2.6,12 L10.2,10.2 Z",
        )
    }

    /** Globe / region on earth. */
    val Globe: ImageVector by lazy {
        line(
            "Globe",
            "M12,3 a9,9 0 1 1 0,18 a9,9 0 1 1 0,-18 Z",
            "M3.2,12 L20.8,12",
            "M12,3.1 C15.5,6.2 15.5,17.8 12,20.9 C8.5,17.8 8.5,6.2 12,3.1 Z",
        )
    }

    /** Undo the last vertex. */
    val Undo: ImageVector by lazy {
        line(
            "Undo",
            "M8.2,6.6 L4.4,10.4 L8.2,14.2",
            "M4.4,10.4 L14.2,10.4 C17.4,10.4 19.8,12.3 19.8,15.2 " +
                "C19.8,18.1 17.4,19.8 14.2,19.8 L8.6,19.8",
        )
    }

    /** Palette for the appearance section. */
    val Palette: ImageVector by lazy {
        ImageVector.Builder(
            name = "Palette",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes(
                    "M12,3 C7.1,3 3,7.1 3,12 C3,16.9 7.1,21 12,21 " +
                        "C13.5,21 14.2,19.9 14.2,18.8 C14.2,17.6 15.3,16.6 16.5,16.6 " +
                        "L18.4,16.6 C20.5,16.6 21.9,15.1 21.4,13.2 C20.5,7.4 16.7,3 12,3 Z",
                ),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineJoin = StrokeJoin.Round,
            )
            addPath(
                pathData = addPathNodes(
                    "M7.4,11.6 a1.6,1.6 0 1 1 0,3.2 a1.6,1.6 0 1 1 0,-3.2 Z " +
                        "M10.2,7.4 a1.6,1.6 0 1 1 0,3.2 a1.6,1.6 0 1 1 0,-3.2 Z " +
                        "M15.4,7.4 a1.6,1.6 0 1 1 0,3.2 a1.6,1.6 0 1 1 0,-3.2 Z",
                ),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Satellite observation. */
    val Satellite: ImageVector by lazy {
        line(
            "Satellite",
            "M14.4,9.6 L9.6,14.4",
            "M9.2,5.6 L11.4,3.4 L17.8,9.8 L15.6,12",
            "M12.4,8.8 L19.6,16 L16.4,19.2 L9.2,12 Z",
            "M5.4,15.4 L3.4,17.4",
            "M18.6,6.4 L20.6,4.4",
        )
    }

    /** Sensor / pulse used for the score hero. */
    val Pulse: ImageVector by lazy {
        line("Pulse", "M2.8,12.4 L7.4,12.4 L9.6,6.6 L12.6,17.8 L15.2,11 L16.8,12.4 L21.2,12.4")
    }

    /** Cloud cover. */
    val Cloud: ImageVector by lazy {
        line(
            "Cloud",
            "M7.2,18.4 C4.6,18.4 2.8,16.6 2.8,14.3 C2.8,11.9 4.8,10.2 7.1,10.2 " +
                "C7.8,7.5 10.1,5.6 12.9,5.6 C16.3,5.6 19.1,8.3 19.2,11.6 " +
                "C20.6,12.1 21.4,13.3 21.4,14.9 C21.4,16.8 19.8,18.4 17.8,18.4 Z",
        )
    }

    /** Closed padlock — "lock this area and start tracing it". */
    val Lock: ImageVector by lazy {
        ImageVector.Builder(
            name = "Lock",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes(
                    "M7.4,10.4 L7.4,7.6 a4.6,4.6 0 0 1 9.2,0 L16.6,10.4",
                ),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineCap = StrokeCap.Round,
            )
            addPath(
                pathData = addPathNodes("M5,10.4 L19,10.4 L19,20.4 L5,20.4 Z"),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineJoin = StrokeJoin.Round,
            )
            addPath(
                pathData = addPathNodes(
                    "M12,13.6 a1.5,1.5 0 1 1 0,3 a1.5,1.5 0 1 1 0,-3 Z " +
                        "M11.2,16.2 L12.8,16.2 L13.1,18.6 L10.9,18.6 Z",
                ),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Open padlock — "unlock and go back to free navigation". */
    val Unlock: ImageVector by lazy {
        ImageVector.Builder(
            name = "Unlock",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes(
                    "M7.4,10.4 L7.4,7.6 a4.6,4.6 0 0 1 9.2,0 L16.6,12.2",
                ),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineCap = StrokeCap.Round,
            )
            addPath(
                pathData = addPathNodes("M5,10.4 L19,10.4 L19,20.4 L5,20.4 Z"),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineJoin = StrokeJoin.Round,
            )
            addPath(
                pathData = addPathNodes(
                    "M12,13.6 a1.5,1.5 0 1 1 0,3 a1.5,1.5 0 1 1 0,-3 Z " +
                        "M11.2,16.2 L12.8,16.2 L13.1,18.6 L10.9,18.6 Z",
                ),
                fill = SolidColor(Color.Black),
            )
        }.build()
    }

    /** Plus / zoom in. */
    val Plus: ImageVector by lazy {
        line("Plus", "M12,5 L12,19", "M5,12 L19,12")
    }

    /** Minus / zoom out. */
    val Minus: ImageVector by lazy {
        line("Minus", "M5,12 L19,12")
    }

    /** Share the run summary. */
    val Share: ImageVector by lazy {
        ImageVector.Builder(
            name = "Share",
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            addPath(
                pathData = addPathNodes(
                    "M12,3.4 L12,14.6 M8.4,7 L12,3.4 L15.6,7 " +
                        "M6,12 L4.4,12 L4.4,20.4 L19.6,20.4 L19.6,12 L18,12",
                ),
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.8f,
                strokeLineCap = StrokeCap.Round,
                strokeLineJoin = StrokeJoin.Round,
            )
        }.build()
    }

    /** Copy the run summary to the clipboard. */
    val Copy: ImageVector by lazy {
        line(
            "Copy",
            "M9,3.6 L18.4,3.6 L18.4,15.4",
            "M6,7.4 L15,7.4 L15,20.4 L6,20.4 Z",
        )
    }

    /** Warning used by the offline banner. */
    val Offline: ImageVector by lazy {
        line(
            "Offline",
            "M3,3 L21,21",
            "M7.2,10.6 a7.6,7.6 0 0 1 4,-2.1",
            "M16.8,10.6 a7.6,7.6 0 0 1 3.4,2.6",
            "M10.6,15.4 a3.2,3.2 0 0 1 3.2,0.6",
        )
    }

    /** Chevron used in list rows. */
    val ChevronRight: ImageVector by lazy {
        line("ChevronRight", "M9.4,5.4 L16,12 L9.4,18.6")
    }
}
