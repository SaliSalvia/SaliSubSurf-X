package com.salsalvia.subsurf.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.salsalvia.subsurf.AppViewModel
import com.salsalvia.subsurf.R
import com.salsalvia.subsurf.UiState
import com.salsalvia.subsurf.geo.GeoMath
import com.salsalvia.subsurf.map.MapLoadingOverlay
import com.salsalvia.subsurf.map.MapScaleBar
import com.salsalvia.subsurf.map.MapZoomControls
import com.salsalvia.subsurf.map.RegionMapController
import com.salsalvia.subsurf.map.RegionMapView
import com.salsalvia.subsurf.ui.components.Pill
import com.salsalvia.subsurf.ui.icons.SubsurfIcons
import com.salsalvia.subsurf.ui.theme.Dims
import com.salsalvia.subsurf.ui.theme.isDarkTheme

/**
 * Exploration mode of the home screen.
 *
 * [EXPLORE] — free pan/zoom over the globe, exactly like Google Earth: nothing is being traced,
 * the map owns all gestures. [TRACE] — the camera is locked and each tap drops a vertex of the
 * dashed exploration boundary.
 */
private enum class MapMode { EXPLORE, TRACE }

/**
 * Home screen. The map *is* the app: it opens on the globe, the user flies to a location, locks
 * it, traces the exact boundary with a red/black dashed line, and then starts the data
 * collection run (validation → satellite catalog → terrain indicators).
 */
@Composable
fun MapScreen(
    vm: AppViewModel,
    state: UiState,
    contentPadding: PaddingValues = PaddingValues(),
    onOpenSettings: () -> Unit = {},
    exitTraceSignal: Int = 0,
    onTracingChanged: (Boolean) -> Unit = {},
) {
    val haptics = LocalHapticFeedback.current
    // Follow the user theme choice (resolved by the activity and published into the state),
    // not just the system setting — the basemap swap survives style reloads via syncTheme().
    val dark = state.isDark
    val statusBars = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()

    var mapReady by remember { mutableStateOf(false) }
    var mapFailed by remember { mutableStateOf(false) }
    var fitRequest by remember { mutableIntStateOf(0) }
    var controller by remember { mutableStateOf<RegionMapController?>(null) }
    var mode by remember { mutableStateOf(MapMode.EXPLORE) }
    var cameraMoved by remember { mutableStateOf(false) }
    var pinned by remember { mutableStateOf(false) }
    var metresPerPixel by remember { mutableStateOf<Double?>(null) }
    var offlineDismissed by remember { mutableStateOf(false) }

    // A failed or finished run must never leave the full-screen collection overlay covering
    // the map: it is only meant to bridge the in-flight request.
    LaunchedEffect(state.busy) {
        if (!state.busy) pinned = false
    }

    val tracing = mode == MapMode.TRACE
    val vertexCount = state.vertices.size
    val canAnalyze = vertexCount >= GeoMath.MIN_VERTICES && !state.busy
    val areaText = remember(state.vertices) { vm.formatArea(state.vertices) }

    val latestTap = rememberUpdatedState(newValue = { lat: Double, lon: Double ->
        // In explore mode the map is for navigation only; the boundary is drawn after lock.
        // Ignore taps while a request is in flight so a report can never describe a different
        // ring than the one currently drawn.
        if (mode == MapMode.TRACE && !state.busy) {
            if (vertexCount < GeoMath.MAX_VERTICES) {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
            }
            vm.addVertex(lat, lon)
        }
    })

    // The host can ask the map to leave trace mode (system back) without losing the sketch.
    LaunchedEffect(exitTraceSignal) {
        if (exitTraceSignal > 0 && mode == MapMode.TRACE) mode = MapMode.EXPLORE
    }
    LaunchedEffect(tracing) { onTracingChanged(tracing) }

    // A locked area freezes the camera: gestures off, taps become boundary vertices.
    LaunchedEffect(controller, tracing) {
        controller?.setLocked(tracing)
        metresPerPixel = controller?.metresPerPixel()
    }

    // Keep the traced ring inside the visible band between the header and the action sheet.
    val density = androidx.compose.ui.platform.LocalDensity.current
    LaunchedEffect(controller, density, tracing) {
        val top = with(density) { (statusBars + 132.dp).toPx() }.toInt()
        val bottom = with(density) {
            (contentPadding.calculateBottomPadding() + if (tracing) 210.dp else 150.dp).toPx()
        }.toInt()
        controller?.setViewInset(top = top, bottom = bottom)
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        RegionMapView(
            vertices = state.vertices,
            onMapTap = { lat, lon -> latestTap.value(lat, lon) },
            modifier = Modifier.fillMaxSize(),
            dark = dark,
            fitRequest = fitRequest,
            onController = { c ->
                controller = c
                c.onCameraMoved = { moving ->
                    if (moving) {
                        cameraMoved = true
                    } else {
                        // Camera idle: refresh the scale bar and re-sync the lock state.
                        metresPerPixel = c.metresPerPixel()
                    }
                }
            },
            onLoadState = {
                mapReady = true
                mapFailed = false
            },
            onLoadError = {
                mapReady = true
                mapFailed = true
            },
        )

        // --- Top bar: brand, mode chip, globe/fit actions ------------------- //
        Column(
            Modifier
                .fillMaxWidth()
                .padding(top = statusBars + Dims.s, start = Dims.m, end = Dims.m),
            verticalArrangement = Arrangement.spacedBy(Dims.s),
        ) {
            TopMapBar(
                tracing = tracing,
                vertexCount = vertexCount,
                onGlobe = { controller?.showGlobe() },
                onFit = { fitRequest++ },
                hasSketch = vertexCount > 0,
            )
            AnimatedVisibility(
                visible = mapFailed,
                enter = fadeIn(tween(200)),
                exit = fadeOut(tween(140)),
            ) {
                MapErrorBanner(
                    onRetry = {
                        mapFailed = false
                        controller?.retry()
                    },
                )
            }
            AnimatedVisibility(
                visible = polygonReady(vertexCount),
                enter = fadeIn(tween(200)),
                exit = fadeOut(tween(140)),
            ) {
                SketchReadout(areaText, GeoMath.perimeterM(state.vertices))
            }
            // Nothing works without a reachable backend: say so once, with a shortcut to fix it.
            AnimatedVisibility(
                visible = state.backendOnline == false && !offlineDismissed,
                enter = fadeIn(tween(220)),
                exit = fadeOut(tween(140)),
            ) {
                OfflineNotice(
                    onOpenSettings = onOpenSettings,
                    onDismiss = { offlineDismissed = true },
                )
            }
        }

        // --- Right-hand map controls --------------------------------------- //
        Column(
            Modifier
                .align(Alignment.CenterEnd)
                .padding(end = Dims.m),
            verticalArrangement = Arrangement.spacedBy(Dims.s),
            horizontalAlignment = Alignment.End,
        ) {
            MapZoomControls(
                onZoomIn = { controller?.zoomBy(1.0) },
                onZoomOut = { controller?.zoomBy(-1.0) },
                enabled = !tracing,
            )
            // Recenter affordance, mirroring Google Maps' "my location" button position.
            MapCircleButton(
                icon = SubsurfIcons.Compass,
                label = stringResource(R.string.map_recenter),
                onClick = { fitRequest++ },
                enabled = !tracing,
            )
        }

        // --- Tracing crosshair hint ---------------------------------------- //
        AnimatedVisibility(
            visible = tracing && vertexCount == 0,
            modifier = Modifier.align(Alignment.Center),
            enter = fadeIn(tween(220)),
            exit = fadeOut(tween(140)),
        ) {
            TracingReticle()
        }

        MapScaleBar(
            metresPerPixel = metresPerPixel,
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(
                    start = Dims.l,
                    bottom = contentPadding.calculateBottomPadding() +
                        if (tracing) 232.dp else 172.dp,
                ),
        )

        MapLoadingOverlay(visible = !mapReady)

        // --- Bottom control dock ------------------------------------------- //
        BottomDock(
            modifier = Modifier.align(Alignment.BottomCenter),
            tracing = tracing,
            vertexCount = vertexCount,
            busy = state.busy,
            canAnalyze = canAnalyze,
            runError = state.runError,
            bottomInset = contentPadding.calculateBottomPadding(),
            cameraMoved = cameraMoved,
            onLock = {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                mode = if (tracing) MapMode.EXPLORE else MapMode.TRACE
            },
            onUndo = { if (vertexCount > 0) vm.undo() },
            onClear = {
                vm.clear()
                mode = MapMode.EXPLORE
            },
            onAnalyze = {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                pinned = true
                vm.dismissError()
                vm.analyze()
            },
            onDismissError = { vm.dismissError() },
        )

        // --- Full-screen collection overlay while the run is in flight ------ //
        CollectionOverlay(
            // Only the blocking validate+catalog stage gets the full-screen treatment; the terrain
            // step keeps running in the background on the Results screen.
            visible = state.busy || (pinned && state.catalog == null && state.runError == null),
            vertices = vertexCount,
        )
    }
}

private fun polygonReady(vertexCount: Int) = vertexCount >= GeoMath.MIN_VERTICES

// --------------------------------------------------------------------------- //
// Top bar
// --------------------------------------------------------------------------- //

@Composable
private fun TopMapBar(
    tracing: Boolean,
    vertexCount: Int,
    onGlobe: () -> Unit,
    onFit: () -> Unit,
    hasSketch: Boolean,
) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Dims.s),
    ) {
        // Brand plate — the app logo, as required by the design brief.
        Row(
            Modifier
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.95f))
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, CircleShape)
                .padding(start = 4.dp, end = 12.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(Dims.s),
        ) {
            Image(
                painter = painterResource(R.drawable.logo_brand),
                contentDescription = null,
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape),
            )
            Column {
                Text(
                    stringResource(R.string.app_name),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    stringResource(R.string.map_title),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.weight(1f))
        // Camera actions are inert while tracing: the lock is only meaningful if the chrome
        // cannot move the camera either (the gesture settings already block drag/pinch).
        MapCircleButton(
            icon = SubsurfIcons.Globe,
            label = stringResource(R.string.map_globe),
            onClick = onGlobe,
            enabled = !tracing,
        )
        if (hasSketch) {
            MapCircleButton(
                icon = SubsurfIcons.Fit,
                label = stringResource(R.string.map_fit),
                onClick = onFit,
                enabled = !tracing,
            )
        }
    }
}

@Composable
private fun SketchReadout(areaText: String, perimeterM: Double) {
    Row(
        Modifier
            .clip(RoundedCornerShape(18.dp))
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.95f))
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(18.dp))
            .padding(horizontal = Dims.l, vertical = Dims.m),
        horizontalArrangement = Arrangement.spacedBy(Dims.l),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column {
            Text(
                stringResource(R.string.metric_area),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                areaText,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        Box(
            Modifier
                .width(1.dp)
                .height(28.dp)
                .background(MaterialTheme.colorScheme.outlineVariant),
        )
        Column {
            Text(
                stringResource(R.string.metric_perimeter),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                stringResource(R.string.perimeter_format, formatNumber(perimeterM, 0)),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun MapCircleButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
) {
    // Press feedback: a quick scale dip replaces the default ripple, matching the
    // physical "key press" feel of the rest of the dock.
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.92f else 1f,
        animationSpec = tween(130),
        label = "mapButtonScale",
    )
    Box(
        Modifier
            .size(46.dp)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.95f))
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, CircleShape)
            .alpha(if (enabled) 1f else 0.35f)
            .let { m ->
                if (enabled) {
                    m.clickable(
                        interactionSource = interaction,
                        indication = null,
                        onClick = onClick,
                    )
                } else {
                    m
                }
            },
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

/**
 * Shown only when the startup probe could not reach the backend. Dismissible so it never becomes
 * a permanent nag while the user is still setting things up.
 */
@Composable
private fun OfflineNotice(onOpenSettings: () -> Unit, onDismiss: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.94f))
            .padding(start = Dims.m, end = Dims.xs, top = Dims.s, bottom = Dims.s),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Dims.s),
    ) {
        Icon(
            SubsurfIcons.Offline,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onErrorContainer,
            modifier = Modifier.size(18.dp),
        )
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(R.string.offline_banner_title),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                stringResource(R.string.offline_banner_body),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
                maxLines = 3,
            )
        }
        TextButton(onClick = onOpenSettings) {
            Text(stringResource(R.string.action_open_settings))
        }
        Icon(
            SubsurfIcons.Minus,
            contentDescription = stringResource(R.string.action_dismiss),
            tint = MaterialTheme.colorScheme.onErrorContainer,
            modifier = Modifier
                .size(30.dp)
                .clip(CircleShape)
                .clickable(onClick = onDismiss)
                .padding(6.dp),
        )
    }
}

// --------------------------------------------------------------------------- //
// Tracing reticle: a pulsing crosshair that tells the user taps now drop points
// --------------------------------------------------------------------------- //

@Composable
private fun TracingReticle() {
    val pulse = rememberInfiniteTransition(label = "reticle")
    val ring by pulse.animateFloat(
        initialValue = 0.72f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "ring",
    )
    Box(
        Modifier
            .size(120.dp)
            .alpha(ring),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .size(96.dp)
                .clip(CircleShape)
                .border(1.5.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = 0.85f), CircleShape),
        )
        Box(
            Modifier
                .width(46.dp)
                .height(1.5.dp)
                .background(MaterialTheme.colorScheme.tertiary),
        )
        Box(
            Modifier
                .width(1.5.dp)
                .height(46.dp)
                .background(MaterialTheme.colorScheme.tertiary),
        )
        Box(
            Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.tertiary),
        )
    }
}

// --------------------------------------------------------------------------- //
// Bottom dock: mode switching and the primary action
// --------------------------------------------------------------------------- //

@Composable
private fun BottomDock(
    modifier: Modifier = Modifier,
    tracing: Boolean,
    vertexCount: Int,
    busy: Boolean,
    canAnalyze: Boolean,
    runError: String?,
    bottomInset: androidx.compose.ui.unit.Dp,
    cameraMoved: Boolean,
    onLock: () -> Unit,
    onUndo: () -> Unit,
    onClear: () -> Unit,
    onAnalyze: () -> Unit,
    onDismissError: () -> Unit,
) {
    // Primary CTA press feedback: a barely perceptible scale dip (the ripple stays on).
    val analyzeInteraction = remember { MutableInteractionSource() }
    val analyzePressed by analyzeInteraction.collectIsPressedAsState()
    val analyzeScale by animateFloatAsState(
        targetValue = if (analyzePressed) 0.985f else 1f,
        animationSpec = tween(130),
        label = "analyzeScale",
    )
    Column(
        modifier
            .fillMaxWidth()
            .padding(horizontal = Dims.m)
            .padding(bottom = bottomInset + Dims.m)
            .animateContentSize(tween(240)),
        verticalArrangement = Arrangement.spacedBy(Dims.s),
    ) {
        // A failed collection is shown in place, with a one-tap retry, so the user never has to
        // hunt for what happened.
        AnimatedVisibility(
            visible = runError != null,
            enter = fadeIn(tween(180)),
            exit = fadeOut(tween(140)),
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clip(MaterialTheme.shapes.medium)
                    .background(MaterialTheme.colorScheme.errorContainer)
                    .padding(horizontal = Dims.m, vertical = Dims.s),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Dims.s),
            ) {
                Icon(
                    SubsurfIcons.Caveat,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.size(18.dp),
                )
                Column(Modifier.weight(1f)) {
                    Text(
                        stringResource(R.string.run_failed_title),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                    Text(
                        runError ?: "",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        maxLines = 3,
                    )
                }
                TextButton(onClick = onDismissError) {
                    Text(stringResource(R.string.action_dismiss))
                }
            }
        }

        // Hint line changes with the mode so the next gesture is always obvious.
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            Pill(
                text = stringResource(
                    when {
                        tracing && vertexCount == 0 -> R.string.hint_trace_first
                        tracing -> R.string.hint_trace_more
                        vertexCount > 0 -> R.string.hint_locked_ready
                        else -> R.string.hint_explore
                    },
                ),
                color = if (tracing) MaterialTheme.colorScheme.tertiary
                else MaterialTheme.colorScheme.primary,
                icon = if (tracing) SubsurfIcons.Region else SubsurfIcons.Globe,
            )
        }

        Column(
            Modifier
                .fillMaxWidth()
                .clip(MaterialTheme.shapes.extraLarge)
                .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.97f))
                .border(
                    1.dp,
                    MaterialTheme.colorScheme.outlineVariant,
                    MaterialTheme.shapes.extraLarge,
                )
                .padding(Dims.l),
            verticalArrangement = Arrangement.spacedBy(Dims.m),
        ) {
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Dims.s),
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        stringResource(
                            when {
                                tracing -> R.string.sheet_title_tracing
                                vertexCount > 0 -> R.string.sheet_title_locked
                                else -> R.string.sheet_title_empty
                            },
                        ),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        stringResource(
                            if (tracing) R.string.sheet_sub_tracing
                            else R.string.sheet_sub_explore,
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                SheetStepDots(vertexCount)
            }

            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(Dims.s),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // Lock / unlock — the mode switch that starts the tracing.
                LockButton(
                    tracing = tracing,
                    enabled = !busy,
                    onClick = onLock,
                    modifier = Modifier.weight(1f),
                )
                DockAction(
                    icon = SubsurfIcons.Undo,
                    label = stringResource(R.string.action_undo),
                    enabled = vertexCount > 0 && !busy,
                    onClick = onUndo,
                    modifier = Modifier.weight(1f),
                )
                DockAction(
                    icon = SubsurfIcons.Minus,
                    label = stringResource(R.string.action_clear),
                    enabled = vertexCount > 0 && !busy,
                    onClick = onClear,
                    modifier = Modifier.weight(1f),
                )
            }

            Button(
                onClick = onAnalyze,
                enabled = canAnalyze,
                interactionSource = analyzeInteraction,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
                    .graphicsLayer {
                        scaleX = analyzeScale
                        scaleY = analyzeScale
                    },
                shape = RoundedCornerShape(18.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            ) {
                if (busy) {
                    CircularProgressIndicator(
                        Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.width(8.dp))
                } else {
                    Icon(
                        SubsurfIcons.Sparkle,
                        contentDescription = null,
                        modifier = Modifier.size(17.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    stringResource(
                        when {
                            busy -> R.string.analyzing_short
                            runError != null -> R.string.action_retry
                            else -> R.string.action_start_run
                        },
                    ),
                    style = MaterialTheme.typography.labelLarge,
                    maxLines = 1,
                )
            }

            if (tracing && vertexCount in 1 until GeoMath.MIN_VERTICES) {
                Text(
                    stringResource(R.string.need_three_vertices),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            if (!tracing && vertexCount == 0 && !cameraMoved) {
                Text(
                    stringResource(R.string.hint_pan_zoom),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

/** Lock/unlock control — the "start tracing this area" affordance. */
@Composable
private fun LockButton(
    tracing: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val container by animateColorAsState(
        targetValue = if (tracing) MaterialTheme.colorScheme.tertiary
        else MaterialTheme.colorScheme.surfaceContainerHigh,
        animationSpec = tween(220),
        label = "lockBg",
    )
    val content = if (tracing) MaterialTheme.colorScheme.onTertiary
    else MaterialTheme.colorScheme.onSurface
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.96f else 1f,
        animationSpec = tween(130),
        label = "lockScale",
    )
    Column(
        modifier
            .height(56.dp)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .clip(RoundedCornerShape(16.dp))
            .background(container)
            .clickable(
                enabled = enabled,
                interactionSource = interaction,
                indication = null,
                onClick = onClick,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            if (tracing) SubsurfIcons.Unlock else SubsurfIcons.Lock,
            contentDescription = null,
            tint = content,
            modifier = Modifier.size(18.dp),
        )
        Spacer(Modifier.height(2.dp))
        Text(
            stringResource(if (tracing) R.string.action_unlock else R.string.action_lock),
            style = MaterialTheme.typography.labelSmall,
            color = content,
            maxLines = 1,
        )
    }
}

@Composable
private fun DockAction(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val tint = if (enabled) MaterialTheme.colorScheme.onSurface
    else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.45f)
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.96f else 1f,
        animationSpec = tween(130),
        label = "dockActionScale",
    )
    Column(
        modifier
            .height(56.dp)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .clip(RoundedCornerShape(16.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.7f))
            .clickable(
                enabled = enabled,
                interactionSource = interaction,
                indication = null,
                onClick = onClick,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(17.dp))
        Spacer(Modifier.height(2.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = tint, maxLines = 1)
    }
}

@Composable
private fun SheetStepDots(vertexCount: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
        repeat(GeoMath.MAX_VERTICES) { index ->
            val filled = index < vertexCount
            Box(
                Modifier
                    .size(width = if (filled) 12.dp else 5.dp, height = 5.dp)
                    .clip(CircleShape)
                    .background(
                        if (filled) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.outlineVariant,
                    ),
            )
        }
    }
}

// --------------------------------------------------------------------------- //
// Collection overlay — the "data gathering" state
// --------------------------------------------------------------------------- //

@Composable
private fun CollectionOverlay(visible: Boolean, vertices: Int) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(tween(220)) + slideInVertically(tween(240)) { it / 6 },
        exit = fadeOut(tween(160)) + slideOutVertically(tween(160)) { it / 6 },
    ) {
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        listOf(
                            MaterialTheme.colorScheme.background.copy(alpha = 0.86f),
                            MaterialTheme.colorScheme.background.copy(alpha = 0.96f),
                        ),
                    ),
                ),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                Modifier
                    .padding(horizontal = Dims.xxl)
                    .clip(MaterialTheme.shapes.extraLarge)
                    .background(MaterialTheme.colorScheme.surface)
                    .border(
                        1.dp,
                        MaterialTheme.colorScheme.outlineVariant,
                        MaterialTheme.shapes.extraLarge,
                    )
                    .padding(Dims.xl),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(Dims.m),
            ) {
                Box(Modifier.size(74.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(
                        modifier = Modifier.fillMaxSize(),
                        strokeWidth = 3.dp,
                        trackColor = MaterialTheme.colorScheme.surfaceContainerHighest,
                    )
                    Icon(
                        SubsurfIcons.Satellite,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(28.dp),
                    )
                }
                Text(
                    stringResource(R.string.collect_title),
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )
                Text(
                    stringResource(R.string.collect_sub, vertices),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Column(
                    Modifier.fillMaxWidth().padding(top = Dims.xs),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    CollectStep(stringResource(R.string.collect_step_validate), done = true)
                    CollectStep(stringResource(R.string.collect_step_catalog), done = false)
                    CollectStep(stringResource(R.string.collect_step_terrain), done = false)
                }
            }
        }
    }
}

@Composable
private fun CollectStep(label: String, done: Boolean) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Dims.s),
    ) {
        Box(
            Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(
                    if (done) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.outlineVariant,
                ),
        )
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = if (done) MaterialTheme.colorScheme.onSurface
            else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

internal fun formatNumber(value: Double, digits: Int): String =
    String.format(java.util.Locale.US, "%.${digits}f", value)

@Composable
private fun MapErrorBanner(onRetry: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(MaterialTheme.colorScheme.errorContainer)
            .padding(start = Dims.l, end = Dims.s, top = Dims.xs, bottom = Dims.xs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Dims.s),
    ) {
        Text(
            stringResource(R.string.map_load_failed),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onErrorContainer,
            modifier = Modifier.weight(1f),
        )
        TextButton(onClick = onRetry) {
            Text(stringResource(R.string.action_retry))
        }
    }
}
