package com.salsalvia.subsurf.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.salsalvia.subsurf.AppViewModel
import com.salsalvia.subsurf.R
import com.salsalvia.subsurf.UiState
import com.salsalvia.subsurf.data.ProductSummary
import com.salsalvia.subsurf.ui.components.BulletLine
import com.salsalvia.subsurf.ui.components.CardHeader
import com.salsalvia.subsurf.ui.components.EmptyState
import com.salsalvia.subsurf.ui.components.Hairline
import com.salsalvia.subsurf.ui.components.InfoBanner
import com.salsalvia.subsurf.ui.components.InfoRow
import com.salsalvia.subsurf.ui.components.MeterRow
import com.salsalvia.subsurf.ui.components.MetricCell
import com.salsalvia.subsurf.ui.components.MetricRow
import com.salsalvia.subsurf.ui.components.MicroLabel
import com.salsalvia.subsurf.ui.components.Pill
import com.salsalvia.subsurf.ui.components.SubsurfCard
import com.salsalvia.subsurf.ui.icons.SubsurfIcons
import com.salsalvia.subsurf.ui.theme.Dims
import java.util.Locale
import kotlin.math.roundToInt

@Composable
fun ResultsScreen(
    vm: AppViewModel,
    state: UiState,
    onGoToMap: () -> Unit = {},
    contentPadding: PaddingValues = PaddingValues(),
    onReportCopied: () -> Unit = {},
) {
    val empty = state.validation == null && state.catalog == null && state.terrain == null
    val context = androidx.compose.ui.platform.LocalContext.current
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current

    Column(
        Modifier
            .fillMaxSize()
            .padding(top = contentPadding.calculateTopPadding()),
    ) {
        ScreenTitle(
            title = stringResource(R.string.results_title),
            subtitle = if (empty) null else stringResource(R.string.results_subtitle),
            trailing = if (empty) {
                null
            } else {
                {
                    Row(horizontalArrangement = Arrangement.spacedBy(Dims.xs)) {
                        RoundIconAction(
                            icon = SubsurfIcons.Share,
                            label = stringResource(R.string.action_share_report),
                            onClick = { ReportExporter.share(context, state) },
                        )
                        RoundIconAction(
                            icon = SubsurfIcons.Copy,
                            label = stringResource(R.string.action_copy_report),
                            onClick = {
                                clipboard.setText(androidx.compose.ui.text.AnnotatedString(
                                    ReportExporter.toPlainText(context, state),
                                ))
                                onReportCopied()
                            },
                        )
                    }
                }
            },
        )

        if (empty) {
            EmptyState(
                icon = SubsurfIcons.Analytics,
                title = stringResource(R.string.results_empty_title),
                message = stringResource(R.string.results_empty),
                modifier = Modifier.weight(1f),
                action = {
                    Button(
                        onClick = onGoToMap,
                        shape = RoundedCornerShape(14.dp),
                    ) {
                        Icon(SubsurfIcons.Region, contentDescription = null, modifier = Modifier.size(17.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.results_empty_action))
                    }
                },
            )
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = Dims.l, vertical = Dims.l)
                    .padding(bottom = contentPadding.calculateBottomPadding()),
            ) {
                DisclaimerNote()
            }
            return
        }

        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                start = Dims.l,
                end = Dims.l,
                top = Dims.xs,
                bottom = contentPadding.calculateBottomPadding() + Dims.xl,
            ),
            verticalArrangement = Arrangement.spacedBy(Dims.m),
        ) {
            item { StatusHero(state) }
            state.validation?.let { v ->
                item { ValidationCard(v.valid, v.issues, v.warnings, v.vertexCount, v.areaHectares, v.perimeterM) }
            }
            state.catalog?.let { catalog ->
                item { CatalogCard(catalog.totalMatched, catalog.products) }
                if (catalog.warnings.isNotEmpty()) {
                    item {
                        NotesCard(
                            title = stringResource(R.string.warnings_title),
                            icon = SubsurfIcons.Caveat,
                            accent = MaterialTheme.colorScheme.tertiary,
                            notes = catalog.warnings,
                        )
                    }
                }
                if (catalog.provenance.isNotEmpty()) {
                    item { ProvenanceCard(catalog.provenance.map { it.provider }) }
                }
            }
            item { TerrainCard(vm, state) }
            state.terrain?.let { terrain ->
                if (terrain.provenance.isNotEmpty()) {
                    item { ProvenanceCard(terrain.provenance.map { it.provider }) }
                }
                if (terrain.caveats.isNotEmpty()) {
                    item {
                        NotesCard(
                            title = stringResource(R.string.caveats_title),
                            icon = SubsurfIcons.Caveat,
                            accent = MaterialTheme.colorScheme.onSurfaceVariant,
                            notes = terrain.caveats,
                        )
                    }
                }
            }
            item { DisclaimerNote() }
        }
    }
}

/** Compact round icon button used in screen titles. */
@Composable
private fun RoundIconAction(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    onClick: () -> Unit,
) {
    Box(
        Modifier
            .size(40.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.size(19.dp),
        )
    }
}

// --------------------------------------------------------------------------- //
// Hero: one glance summary of the whole report
// --------------------------------------------------------------------------- //

@Composable
private fun StatusHero(state: UiState) {
    val valid = state.validation?.valid
    val ok = valid != false
    val accent = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
    Row(
        Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.large)
            .background(
                Brush.horizontalGradient(
                    listOf(
                        accent.copy(alpha = 0.14f),
                        accent.copy(alpha = 0.05f),
                    ),
                ),
            )
            .border(1.dp, accent.copy(alpha = 0.22f), MaterialTheme.shapes.large)
            .padding(Dims.l),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Dims.m),
    ) {
        Box(
            Modifier
                .size(44.dp)
                .clip(CircleShape)
                .background(accent.copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (ok) SubsurfIcons.Provenance else SubsurfIcons.Caveat,
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(23.dp),
            )
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                stringResource(
                    if (valid == false) R.string.invalid_region else R.string.valid_region,
                ),
                style = MaterialTheme.typography.titleMedium,
                color = accent,
            )
            Text(
                stringResource(
                    if (state.catalog != null) R.string.hero_summary_full
                    else R.string.hero_summary_partial,
                ),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        state.catalog?.let {
            Pill(text = "${it.products.size}", color = accent)
        }
    }
}

// --------------------------------------------------------------------------- //
// Region validation
// --------------------------------------------------------------------------- //

@Composable
private fun ValidationCard(
    valid: Boolean,
    issues: List<String>,
    warnings: List<String>,
    vertexCount: Int,
    areaHectares: Double,
    perimeterM: Double,
) {
    SubsurfCard {
        CardHeader(
            title = stringResource(R.string.validation_card),
            icon = SubsurfIcons.Ruler,
        )
        MetricRow {
            MetricCell(
                value = fmt(areaHectares, if (areaHectares >= 100) 0 else 2),
                label = stringResource(R.string.metric_area),
                unit = stringResource(R.string.unit_hectare),
                emphasis = true,
            )
            MetricCell(
                value = fmt(perimeterM, 0),
                label = stringResource(R.string.metric_perimeter),
                unit = stringResource(R.string.unit_metre),
            )
            MetricCell(
                value = vertexCount.toString(),
                label = stringResource(R.string.metric_vertices),
            )
        }
        if (issues.isNotEmpty()) {
            Hairline()
            MicroLabel(stringResource(R.string.issues_title))
            issues.forEach { BulletLine(it, MaterialTheme.colorScheme.error) }
        }
        if (warnings.isNotEmpty()) {
            InfoBanner(
                text = warnings.joinToString("\n"),
                icon = SubsurfIcons.Caveat,
                accent = MaterialTheme.colorScheme.tertiary,
                title = stringResource(R.string.warnings_title),
            )
        }
    }
}

// --------------------------------------------------------------------------- //
// Sentinel-2 catalog
// --------------------------------------------------------------------------- //

@Composable
private fun CatalogCard(totalMatched: Int, products: List<ProductSummary>) {
    SubsurfCard {
        CardHeader(
            title = stringResource(R.string.catalog_card),
            icon = SubsurfIcons.Satellite,
            trailing = {
                Pill(
                    text = products.size.toString(),
                    color = MaterialTheme.colorScheme.primary,
                )
            },
        )
        Text(
            stringResource(R.string.total_matched_format, totalMatched),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (products.isEmpty()) {
            Hairline()
            Text(
                stringResource(R.string.no_products),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        products.forEachIndexed { index, p ->
            if (index > 0) Hairline()
            Spacer(Modifier.height(if (index == 0) Dims.xs else 0.dp))
            ProductRow(p)
        }
    }
}

@Composable
private fun ProductRow(p: ProductSummary) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                p.datetime?.take(10) ?: "—",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            p.cloudCoverPercent?.let { cloud ->
                val tint = when {
                    cloud <= 10 -> MaterialTheme.colorScheme.primary
                    cloud <= 30 -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.error
                }
                Pill(
                    text = stringResource(R.string.cloud_cover_short, fmt(cloud, 0)),
                    color = tint,
                    icon = SubsurfIcons.Cloud,
                )
            }
        }
        Text(
            p.name,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
        )
        if (p.sizeMb != null) {
            Text(
                stringResource(R.string.size_format, fmt(p.sizeMb, 0)),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// --------------------------------------------------------------------------- //
// Terrain indicators + score
// --------------------------------------------------------------------------- //

@Composable
private fun TerrainCard(vm: AppViewModel, state: UiState) {
    val t = state.terrain
    SubsurfCard {
        CardHeader(
            title = stringResource(R.string.terrain_card),
            icon = SubsurfIcons.Terrain,
            trailing = {
                if (t != null) {
                    Pill(
                        text = stringResource(R.string.dem_tag),
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            },
        )
        if (t == null) {
            Text(
                stringResource(R.string.terrain_intro),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            // Terrain is the step most likely to fail (large polygons can exceed the DEM
            // window). Say why, and make the button below an explicit retry.
            if (state.runError != null && !state.terrainBusy) {
                Text(
                    text = state.runError,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = Dims.xs),
                )
            }
            Button(
                onClick = { vm.retryTerrain() },
                enabled = !state.terrainBusy,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = Dims.xs)
                    .height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                ),
            ) {
                if (state.terrainBusy) {
                    CircularProgressIndicator(
                        Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.width(8.dp))
                } else {
                    Icon(SubsurfIcons.Terrain, contentDescription = null, modifier = Modifier.size(17.dp))
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    stringResource(
                        when {
                            state.terrainBusy -> R.string.computing
                            state.runError != null -> R.string.action_retry
                            else -> R.string.compute_terrain
                        },
                    ),
                )
            }
            return@SubsurfCard
        }

        MetricRow {
            MetricCell(
                value = fmt(t.elevation.meanM, 0),
                label = stringResource(R.string.metric_mean_elevation),
                unit = stringResource(R.string.unit_metre),
                emphasis = true,
            )
            MetricCell(
                value = fmt(t.slope.meanDeg, 1),
                label = stringResource(R.string.metric_mean_slope),
                unit = stringResource(R.string.unit_degree),
            )
            MetricCell(
                value = fmt(t.roughnessTriMean, 1),
                label = stringResource(R.string.metric_roughness),
            )
        }

        Hairline()
        InfoRow(
            stringResource(R.string.elevation_range_label),
            stringResource(
                R.string.elevation_format,
                fmt(t.elevation.minM, 0),
                fmt(t.elevation.maxM, 0),
            ),
        )
        InfoRow(
            stringResource(R.string.slope_max_label),
            fmt(t.slope.maxDeg, 1) + "°",
        )
        InfoRow(
            stringResource(R.string.dem_resolution_label),
            stringResource(R.string.resolution_format, fmt(t.resolutionMPerPx, 1)),
        )
        InfoRow(
            stringResource(R.string.tiles_label),
            t.tilesFetched.toString(),
        )
        t.dominantGradientAzimuthDeg?.let { az ->
            InfoRow(
                stringResource(R.string.gradient_label),
                fmt(t.gradientConsistency ?: 0.0, 2) + " · " +
                    com.salsalvia.subsurf.geo.GeoMath.compassLabel(az),
            )
        }

        t.surfaceAnomalyScore?.let { score ->
            Hairline()
            ScoreBlock(score = score, components = t.scoreComponents)
        }
    }
}

/**
 * The headline number of the analysis: a 0..1 surface anomaly score with an animated gauge and
 * a transparent breakdown of the documented components (weights come from the backend).
 */
@Composable
private fun ScoreBlock(score: Double, components: Map<String, Double>) {
    val fraction = score.toFloat().coerceIn(0f, 1f)
    val animated by animateFloatAsState(
        targetValue = fraction,
        animationSpec = tween(750),
        label = "score",
    )
    val accent = when {
        fraction < 0.34f -> MaterialTheme.colorScheme.primary
        fraction < 0.67f -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.error
    }
    Column(verticalArrangement = Arrangement.spacedBy(Dims.s)) {
        Row(verticalAlignment = Alignment.Bottom) {
            Column(Modifier.weight(1f)) {
                MicroLabel(stringResource(R.string.score_title))
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        fmt(score, 2),
                        style = MaterialTheme.typography.displaySmall,
                        fontWeight = FontWeight.Bold,
                        color = accent,
                    )
                    Text(
                        stringResource(R.string.score_out_of),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(bottom = 7.dp, start = 3.dp),
                    )
                }
            }
            Pill(
                text = stringResource(
                    when {
                        fraction < 0.34f -> R.string.score_level_low
                        fraction < 0.67f -> R.string.score_level_moderate
                        else -> R.string.score_level_high
                    },
                ),
                color = accent,
            )
        }
        MeterRow(
            label = stringResource(R.string.score_title),
            fraction = animated,
            valueText = "${(animated * 100).roundToInt()}%",
            color = accent,
        )
        if (components.isNotEmpty()) {
            Spacer(Modifier.height(2.dp))
            MicroLabel(stringResource(R.string.score_components))
            components.forEach { (name, value) ->
                MeterRow(
                    label = componentLabel(name),
                    fraction = value.toFloat(),
                    valueText = fmt(value, 2),
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
        }
        InfoBanner(
            text = stringResource(R.string.score_explainer),
            icon = SubsurfIcons.Caveat,
            accent = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun componentLabel(key: String): String = when (key) {
    "slope_variability" -> stringResource(R.string.component_slope_variability)
    "roughness" -> stringResource(R.string.component_roughness)
    "gradient_consistency" -> stringResource(R.string.component_gradient_consistency)
    "relief" -> stringResource(R.string.component_relief)
    else -> key.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

// --------------------------------------------------------------------------- //
// Provenance / notes / disclaimer
// --------------------------------------------------------------------------- //

@Composable
private fun ProvenanceCard(providers: List<String>) {
    SubsurfCard {
        CardHeader(
            title = stringResource(R.string.provenance_title),
            icon = SubsurfIcons.Provenance,
            tint = MaterialTheme.colorScheme.secondary,
        )
        providers.forEach { BulletLine(it, MaterialTheme.colorScheme.secondary) }
    }
}

@Composable
private fun NotesCard(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    accent: Color,
    notes: List<String>,
) {
    SubsurfCard {
        CardHeader(title = title, icon = icon, tint = accent)
        notes.forEach { BulletLine(it, accent) }
    }
}

@Composable
private fun DisclaimerNote() {
    InfoBanner(
        text = stringResource(R.string.disclaimer),
        icon = SubsurfIcons.Caveat,
        accent = MaterialTheme.colorScheme.tertiary,
        title = stringResource(R.string.disclaimer_title),
    )
}

private fun fmt(v: Double, digits: Int): String =
    String.format(Locale.US, "%.${digits}f", v)
