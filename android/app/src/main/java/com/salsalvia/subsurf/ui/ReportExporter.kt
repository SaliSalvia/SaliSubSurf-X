package com.salsalvia.subsurf.ui

import android.content.Context
import android.content.Intent
import com.salsalvia.subsurf.R
import com.salsalvia.subsurf.UiState
import java.util.Locale

/**
 * Turns the current [UiState] into a plain-text run summary that can be copied or shared.
 *
 * This is a pure formatting helper: it contains no analysis of its own and every number comes
 * straight from the backend responses. The scientific caveat is always appended, so a shared
 * report can never be read as a "find" on its own.
 */
object ReportExporter {

    fun toPlainText(context: Context, state: UiState): String {
        val sb = StringBuilder()
        sb.appendLine(context.getString(R.string.report_share_title))
        sb.appendLine("—".repeat(28))

        state.runAreaLabel?.let {
            sb.appendLine("${context.getString(R.string.run_area_label)}: $it")
        }

        state.validation?.let { v ->
            sb.appendLine()
            sb.appendLine("[ ${context.getString(R.string.validation_card)} ]")
            sb.appendLine(
                context.getString(if (v.valid) R.string.valid_region else R.string.invalid_region),
            )
            sb.appendLine(
                "${context.getString(R.string.metric_area)}: " +
                    fmt(v.areaHectares, 2) + " " + context.getString(R.string.unit_hectare) +
                    " · ${context.getString(R.string.metric_perimeter)}: " +
                    fmt(v.perimeterM, 0) + " " + context.getString(R.string.unit_metre) +
                    " · ${context.getString(R.string.metric_vertices)}: ${v.vertexCount}",
            )
            v.issues.forEach { sb.appendLine("  ! $it") }
        }

        state.catalog?.let { c ->
            sb.appendLine()
            sb.appendLine("[ ${context.getString(R.string.catalog_card)} ]")
            sb.appendLine(
                context.getString(R.string.total_matched_format, c.totalMatched),
            )
            if (c.products.isEmpty()) {
                sb.appendLine("  ${context.getString(R.string.report_no_products)}")
            }
            c.products.forEach { p ->
                val cloud = p.cloudCoverPercent?.let { " · ${fmt(it, 0)}% cloud" } ?: ""
                sb.appendLine("  - ${p.datetime?.take(10) ?: "—"}$cloud")
            }
        }

        state.terrain?.let { t ->
            sb.appendLine()
            sb.appendLine("[ ${context.getString(R.string.terrain_card)} ]")
            sb.appendLine(
                "  ${context.getString(R.string.metric_mean_elevation)}: " +
                    fmt(t.elevation.meanM, 0) + " m (" +
                    fmt(t.elevation.minM, 0) + "–" + fmt(t.elevation.maxM, 0) + " m)",
            )
            sb.appendLine(
                "  ${context.getString(R.string.metric_mean_slope)}: " + fmt(t.slope.meanDeg, 1) +
                    "° · ${context.getString(R.string.slope_max_label)}: " + fmt(t.slope.maxDeg, 1) + "°",
            )
            sb.appendLine(
                "  ${context.getString(R.string.metric_roughness)}: " + fmt(t.roughnessTriMean, 2),
            )
            t.surfaceAnomalyScore?.let { score ->
                sb.appendLine(
                    "  ${context.getString(R.string.score_title)}: ${fmt(score, 2)} / 1.00",
                )
                t.scoreComponents.forEach { (k, v) ->
                    sb.appendLine("    · ${k.replace('_', ' ')} = ${fmt(v, 2)}")
                }
            }
        }

        sb.appendLine()
        sb.appendLine(context.getString(R.string.disclaimer))
        return sb.toString().trim()
    }

    fun share(context: Context, state: UiState) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, context.getString(R.string.report_share_title))
            putExtra(Intent.EXTRA_TEXT, toPlainText(context, state))
        }
        context.startActivity(
            Intent.createChooser(intent, context.getString(R.string.action_share_report)),
        )
    }

    private fun fmt(v: Double, digits: Int): String =
        String.format(Locale.US, "%.${digits}f", v)
}
