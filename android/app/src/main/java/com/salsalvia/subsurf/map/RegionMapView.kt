package com.salsalvia.subsurf.map

import android.graphics.Color
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.salsalvia.subsurf.R
import com.salsalvia.subsurf.geo.Vertex
import com.salsalvia.subsurf.ui.icons.SubsurfIcons
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.OnMapReadyCallback
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.FillLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory.circleColor
import org.maplibre.android.style.layers.PropertyFactory.circleOpacity
import org.maplibre.android.style.layers.PropertyFactory.circleRadius
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeColor
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeWidth
import org.maplibre.android.style.layers.PropertyFactory.fillColor
import org.maplibre.android.style.layers.PropertyFactory.fillOutlineColor
import org.maplibre.android.style.layers.PropertyFactory.lineColor
import org.maplibre.android.style.layers.PropertyFactory.lineDasharray
import org.maplibre.android.style.layers.PropertyFactory.lineJoin
import org.maplibre.android.style.layers.PropertyFactory.lineWidth
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon

/**
 * Free, key-less vector basemaps (OpenFreeMap, OSM-derived). The old MapLibre *demo* style had no
 * real cartography, which is what made the map look unfinished next to Google Earth/Maps.
 */
private const val STYLE_LIGHT = "https://tiles.openfreemap.org/styles/positron"
private const val STYLE_DARK = "https://tiles.openfreemap.org/styles/dark"

private const val SRC = "subsurf-region-src"
private const val SRC_TRACE = "subsurf-trace-src"
private const val LAYER_FILL = "subsurf-region-fill"
private const val LAYER_OPEN = "subsurf-region-open"
private const val LAYER_LINE = "subsurf-region-line"
private const val LAYER_DASH = "subsurf-trace-dash"
private const val LAYER_HALO = "subsurf-region-halo"
private const val LAYER_POINTS = "subsurf-region-points"
private const val LAYER_CENTER = "subsurf-region-center"

/** Whole-earth opening view, like the first frame of Google Earth. */
private const val DEFAULT_LAT = 22.0
private const val DEFAULT_LON = 12.0
private const val GLOBE_ZOOM = 1.6
private const val FOCUS_ZOOM = 11.5

/** Logo-derived acccents: gold signal, electric blue highlight, ember alert. */
private val GOLD = 0xFFF5C542.toInt()
private val GOLD_DIM = 0xFFC08A10.toInt()
private val BLUE = 0xFF35B4F2.toInt()
private val EMBER = 0xFFFF8A50.toInt()

/**
 * Bridges Compose to the MapLibre view: owns the sketch sources/layers, remembers the camera and
 * tolerates style reloads (theme switches replay the geometry instead of losing it).
 *
 * Drawing model — deliberately Google-Earth-like:
 *  * free pan/zoom with one finger,
 *  * a **lock** toggles "tracing" mode; while tracing, the camera is fixed and every tap adds a
 *    vertex of the exploration boundary,
 *  * the boundary is rendered as a black **and** red dashed ring over a faint amber fill, plus a
 *    crosshair at the centroid.
 */
class RegionMapController {

    var onTap: ((Double, Double) -> Unit)? = null
    var onCameraMoved: ((Boolean) -> Unit)? = null

    private var map: MapLibreMap? = null
    private var regionSource: GeoJsonSource? = null
    private var traceSource: GeoJsonSource? = null
    private var pending: List<Vertex> = emptyList()
    private var lastPushed: List<Vertex>? = null
    private var darkStyle: Boolean? = null
    private var viewInset: IntArray = intArrayOf(0, 0, 0, 0)
    private var locked = false

    fun onMapReady(map: MapLibreMap, dark: Boolean) {
        this.map = map
        darkStyle = dark
        map.moveCamera(
            CameraUpdateFactory.newLatLngZoom(LatLng(DEFAULT_LAT, DEFAULT_LON), GLOBE_ZOOM),
        )
        map.uiSettings.apply {
            // Kept ON: the basemap licence (OpenStreetMap / OpenFreeMap) requires attribution.
            isAttributionEnabled = true
            isLogoEnabled = false
            isCompassEnabled = false
            isRotateGesturesEnabled = false
            isTiltGesturesEnabled = false
        }
        map.addOnMapClickListener(
            MapLibreMap.OnMapClickListener { point ->
                onTap?.invoke(point.latitude, point.longitude)
                true
            },
        )
        map.addOnCameraMoveStartedListener { onCameraMoved?.invoke(true) }
        map.addOnCameraIdleListener { onCameraMoved?.invoke(false) }
        loadStyle(dark)
    }

    /**
     * Locks the camera. While locked, pan/zoom gestures are disabled so a tap can only ever place
     * a boundary vertex — this is what makes "lock the area, then trace it" reliable on a phone
     * where a fat-finger drag would otherwise move the map mid-trace.
     */
    fun setLocked(locked: Boolean) {
        this.locked = locked
        map?.uiSettings?.apply {
            isScrollGesturesEnabled = !locked
            isZoomGesturesEnabled = !locked
            isDoubleTapGesturesEnabled = !locked
            isRotateGesturesEnabled = false
            isTiltGesturesEnabled = false
        }
    }

    /** Swaps the basemap when the theme changes, replaying the sketch afterwards. */
    fun syncTheme(dark: Boolean) {
        if (map == null || darkStyle == dark) return
        darkStyle = dark
        loadStyle(dark)
    }

    private fun loadStyle(dark: Boolean) {
        val current = map ?: return
        regionSource = null
        traceSource = null
        lastPushed = null
        current.setStyle(
            Style.Builder().fromUri(if (dark) STYLE_DARK else STYLE_LIGHT),
            object : Style.OnStyleLoaded {
                override fun onStyleLoaded(style: Style) {
                    installLayers(style)
                    applyInset()
                    setLocked(locked)
                }
            },
        )
    }

    /** Re-attempts the basemap download after a failed style load (e.g. device was offline). */
    fun retry() {
        loadStyle(darkStyle ?: false)
    }

    private fun installLayers(style: Style) {
        // A retry can hand us a style that still carries our ids; clear them first so
        // addSource/addLayer never throws on a duplicate id.
        for (id in listOf(LAYER_FILL, LAYER_OPEN, LAYER_DASH, LAYER_LINE, LAYER_HALO, LAYER_POINTS, LAYER_CENTER)) {
            style.getLayer(id)?.let { style.removeLayer(it) }
        }
        for (id in listOf(SRC_TRACE, SRC)) {
            style.getSource(id)?.let { style.removeSource(it) }
        }

        // --- The traced exploration boundary ------------------------------- //
        val trace = GeoJsonSource(SRC_TRACE)
        style.addSource(trace)
        traceSource = trace

        style.addLayer(
            FillLayer(LAYER_FILL, SRC_TRACE).withProperties(
                fillColor(Color.argb(38, Color.red(GOLD), Color.green(GOLD), Color.blue(GOLD))),
                fillOutlineColor(Color.TRANSPARENT),
            ),
        )
        // Solid dark under-stroke so the dashed line reads on bright satellite imagery.
        style.addLayer(
            LineLayer(LAYER_OPEN, SRC_TRACE).withProperties(
                lineColor(Color.argb(150, 0, 0, 0)),
                lineWidth(5.5f),
                lineJoin("round"),
            ),
        )
        // The red dashed boundary itself.
        style.addLayer(
            LineLayer(LAYER_DASH, SRC_TRACE).withProperties(
                lineColor(EMBER),
                lineWidth(2.8f),
                lineJoin("round"),
                lineDasharray(arrayOf(2.0f, 1.6f)),
            ),
        )
        style.addLayer(
            LineLayer(LAYER_LINE, SRC_TRACE).withProperties(
                lineColor(GOLD),
                lineWidth(1.4f),
                lineJoin("round"),
            ),
        )

        // --- Vertex handles ------------------------------------------------- //
        val region = GeoJsonSource(SRC)
        style.addSource(region)
        regionSource = region

        style.addLayer(
            CircleLayer(LAYER_HALO, SRC).withProperties(
                circleColor(GOLD),
                circleRadius(14.0f),
                circleOpacity(0.22f),
            ),
        )
        style.addLayer(
            CircleLayer(LAYER_POINTS, SRC).withProperties(
                circleColor(GOLD),
                circleRadius(6.5f),
                circleStrokeWidth(2.5f),
                circleStrokeColor(Color.BLACK),
            ),
        )
        style.addLayer(
            CircleLayer(LAYER_CENTER, SRC).withProperties(
                circleColor(BLUE),
                circleRadius(4.0f),
                circleOpacity(0.9f),
            ),
        )
        push(pending)
    }

    /**
     * Pushes the sketch into both sources. Called on every recomposition, so it bails out when
     * nothing changed — rebuilding the collections each frame made the map stutter while the
     * action sheet animated.
     */
    fun push(vertices: List<Vertex>) {
        pending = vertices
        if (vertices == lastPushed) return
        lastPushed = vertices

        val points = vertices.map { Point.fromLngLat(it.lon, it.lat) }

        // Ring geometry (dashed boundary) lives in its own source.
        traceSource?.let { src ->
            val ring = ArrayList<Feature>(1)
            when {
                points.size >= 3 -> ring.add(
                    Feature.fromGeometry(Polygon.fromLngLats(listOf(points + points.first()))),
                )
                points.size == 2 -> ring.add(Feature.fromGeometry(LineString.fromLngLats(points)))
            }
            src.setGeoJson(FeatureCollection.fromFeatures(ring))
        }

        // Handles: vertices plus a centroid marker once a polygon exists.
        regionSource?.let { src ->
            val features = ArrayList<Feature>(points.size + 1)
            for (p in points) features.add(Feature.fromGeometry(p))
            if (points.size >= 3) {
                var lat = 0.0
                var lon = 0.0
                for (v in vertices) {
                    lat += v.lat
                    lon += v.lon
                }
                val n = vertices.size.toDouble()
                features.add(Feature.fromGeometry(Point.fromLngLat(lon / n, lat / n)))
            }
            src.setGeoJson(FeatureCollection.fromFeatures(features))
        }
    }

    /** Shrinks the usable viewport so the sketch frames between the header and the action sheet. */
    fun setViewInset(top: Int, bottom: Int, start: Int = 0, end: Int = 0) {
        viewInset = intArrayOf(start, top, end, bottom)
        applyInset()
    }

    private fun applyInset() {
        val current = map ?: return
        runCatching {
            current.setPadding(viewInset[0], viewInset[1], viewInset[2], viewInset[3])
        }
    }

    /** Zooms to a whole-earth view (the "back to globe" affordance). */
    fun showGlobe() {
        map?.animateCamera(
            CameraUpdateFactory.newLatLngZoom(LatLng(DEFAULT_LAT, DEFAULT_LON), GLOBE_ZOOM),
            900,
        )
    }

    /** Frames the whole sketch with a comfortable margin. */
    fun fitTo(vertices: List<Vertex>) {
        val current = map ?: return
        if (locked) return
        if (vertices.isEmpty()) return
        if (vertices.size == 1) {
            current.animateCamera(
                CameraUpdateFactory.newLatLngZoom(
                    LatLng(vertices.first().lat, vertices.first().lon), FOCUS_ZOOM,
                ),
                700,
            )
            return
        }
        var minLat = Double.MAX_VALUE
        var maxLat = -Double.MAX_VALUE
        var minLon = Double.MAX_VALUE
        var maxLon = -Double.MAX_VALUE
        for (v in vertices) {
            if (v.lat < minLat) minLat = v.lat
            if (v.lat > maxLat) maxLat = v.lat
            if (v.lon < minLon) minLon = v.lon
            if (v.lon > maxLon) maxLon = v.lon
        }
        // A single point or a degenerate bbox would make newLatLngBounds blow up.
        if (maxLat - minLat < 1e-6 && maxLon - minLon < 1e-6) {
            current.animateCamera(
                CameraUpdateFactory.newLatLngZoom(LatLng(minLat, minLon), FOCUS_ZOOM),
                700,
            )
            return
        }
        val padded = LatLngBounds.from(
            maxLat + 1e-5, maxLon + 1e-5, minLat - 1e-5, minLon - 1e-5,
        )
        current.animateCamera(
            CameraUpdateFactory.newLatLngBounds(padded, 96, 96, 96, 96),
            700,
        )
    }

    fun zoomBy(delta: Double) {
        val current = map ?: return
        val target = (current.cameraPosition.zoom + delta).coerceIn(0.5, 20.0)
        current.animateCamera(CameraUpdateFactory.zoomTo(target), 220)
    }

    /** Current zoom, used by the UI to decide how much map context to show. */
    fun currentZoom(): Double = map?.cameraPosition?.zoom ?: GLOBE_ZOOM

    /**
     * Ground resolution at the camera target, in metres per screen pixel.
     *
     * Standard Web Mercator relation for 512px tiles (MapLibre's tile size):
     * `156543.03392 * cos(lat) / 2^zoom` is the resolution for a *256px* tile world, and 512px
     * tiles halve it. Good enough for a scale bar; the platform does not need survey accuracy here.
     */
    fun metresPerPixel(): Double? {
        val camera = map?.cameraPosition ?: return null
        val latRad = Math.toRadians(camera.target?.latitude ?: 0.0)
        val equatorMetresPerPixel = 156543.03392 / Math.pow(2.0, camera.zoom)
        return equatorMetresPerPixel * Math.cos(latRad) / 2.0
    }
}

/**
 * @param locked when true the camera is frozen and taps add boundary vertices
 * @param fitRequest increment to animate the camera onto the current sketch
 */
@Composable
fun RegionMapView(
    vertices: List<Vertex>,
    onMapTap: (Double, Double) -> Unit,
    modifier: Modifier = Modifier,
    dark: Boolean = false,
    fitRequest: Int = 0,
    onController: (RegionMapController) -> Unit = {},
    onLoadState: (Boolean) -> Unit = {},
    onLoadError: () -> Unit = {},
) {
    val context = LocalContext.current
    val controller = remember { RegionMapController() }
    val currentTap by rememberUpdatedState(onMapTap)
    val currentDark by rememberUpdatedState(dark)
    val currentLoadState by rememberUpdatedState(onLoadState)
    val currentLoadError by rememberUpdatedState(onLoadError)
    var mapView by remember { mutableStateOf<MapView?>(null) }

    AndroidView(
        modifier = modifier,
        factory = { ctx ->
            MapLibre.getInstance(ctx)
            MapView(ctx).apply {
                onCreate(null)
                onStart()
                onResume()
                getMapAsync(
                    OnMapReadyCallback { map ->
                        controller.onMapReady(map, currentDark)
                        onController(controller)
                    },
                )
                addOnDidFinishLoadingMapListener { currentLoadState(true) }
                addOnDidFailLoadingMapListener { currentLoadError() }
                mapView = this
            }
        },
        update = { view ->
            controller.onTap = { lat, lon -> currentTap(lat, lon) }
            controller.push(vertices)
            controller.syncTheme(dark)
            view.onResume()
        },
    )

    LaunchedEffect(fitRequest, mapView) {
        if (fitRequest > 0 && mapView != null) {
            // Give the surface a frame so bounds fitting uses the real viewport.
            kotlinx.coroutines.delay(280)
            controller.fitTo(vertices)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            mapView?.let { view ->
                view.onPause()
                view.onStop()
                view.onDestroy()
            }
            mapView = null
        }
    }
}

/**
 * Vertical zoom pair, styled like Google Maps' map controls.
 *
 * @param enabled while tracing (camera locked) the pair is disabled, so the on-screen buttons
 *   cannot defeat the lock that the gesture settings already enforce.
 */
@Composable
fun MapZoomControls(
    onZoomIn: () -> Unit,
    onZoomOut: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Column(
        modifier
            .clip(MaterialTheme.shapes.large)
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.94f)),
        verticalArrangement = Arrangement.spacedBy(1.dp),
    ) {
        ZoomButton(SubsurfIcons.Plus, stringResource(R.string.map_zoom_in), onZoomIn, enabled)
        Box(
            Modifier
                .padding(horizontal = 10.dp)
                .fillMaxWidth()
                .height(1.dp)
                .background(MaterialTheme.colorScheme.outlineVariant),
        )
        ZoomButton(SubsurfIcons.Minus, stringResource(R.string.map_zoom_out), onZoomOut, enabled)
    }
}

@Composable
private fun ZoomButton(icon: ImageVector, label: String, onClick: () -> Unit, enabled: Boolean = true) {
    Box(
        Modifier
            .size(46.dp)
            .alpha(if (enabled) 1f else 0.35f)
            .let { m -> if (enabled) m.clickable(onClick = onClick) else m },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = if (enabled) MaterialTheme.colorScheme.onSurface
            else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(20.dp),
        )
    }
}

/** Soft loading veil shown until the first style has rendered. */
@Composable
fun MapLoadingOverlay(visible: Boolean, modifier: Modifier = Modifier) {
    AnimatedVisibility(visible, modifier, enter = fadeIn(), exit = fadeOut()) {
        Box(
            Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface.copy(alpha = 0.6f)),
            contentAlignment = Alignment.Center,
        ) {
            Row(
                Modifier
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                Text(stringResource(R.string.map_loading), style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

/**
 * Google-Maps-style scale bar. Driven by [RegionMapController.metresPerPixel] on each camera idle
 * event; it snaps to a "nice" round distance so the label never reads like a spreadsheet.
 */
@Composable
fun MapScaleBar(
    metresPerPixel: Double?,
    modifier: Modifier = Modifier,
) {
    val mpp = metresPerPixel ?: return
    if (mpp <= 0.0) return

    // Target ~92dp wide bar, snapped to 1/2/5 x 10^n in metres or kilometres.
    val targetPx = with(androidx.compose.ui.platform.LocalDensity.current) { 92.dp.toPx() }
    val rawMetres = mpp * targetPx
    val niceMetres = niceDistance(rawMetres)
    val barWidthDp = with(androidx.compose.ui.platform.LocalDensity.current) {
        (niceMetres / mpp).toFloat().toDp()
    }

    Row(
        modifier
            .clip(androidx.compose.foundation.shape.RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.88f))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            Modifier
                .width(barWidthDp.coerceIn(28.dp, 140.dp))
                .height(3.dp)
                .background(MaterialTheme.colorScheme.onSurface),
        )
        Text(
            formatDistance(niceMetres),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

/** Smallest "nice" distance (1/2/5 x 10^n) that is >= the requested value. */
internal fun niceDistance(metres: Double): Double {
    if (metres <= 0.0 || !metres.isFinite()) return 1.0
    val magnitude = Math.pow(10.0, Math.floor(Math.log10(metres)))
    val mantissa = metres / magnitude
    val nice = when {
        mantissa <= 1.0 -> 1.0
        mantissa <= 2.0 -> 2.0
        mantissa <= 5.0 -> 5.0
        else -> 10.0
    }
    return nice * magnitude
}

internal fun formatDistance(metres: Double): String = when {
    metres >= 1000.0 -> String.format(java.util.Locale.US, "%.0f km", metres / 1000.0)
    metres >= 1.0 -> String.format(java.util.Locale.US, "%.0f m", metres)
    else -> String.format(java.util.Locale.US, "%.0f cm", metres * 100.0)
}
