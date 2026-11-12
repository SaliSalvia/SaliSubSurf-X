package com.salsalvia.subsurf.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.salsalvia.subsurf.AppViewModel
import com.salsalvia.subsurf.BuildConfig
import com.salsalvia.subsurf.R
import com.salsalvia.subsurf.UiState
import com.salsalvia.subsurf.data.ThemeMode
import com.salsalvia.subsurf.ui.components.CardHeader
import com.salsalvia.subsurf.ui.components.Hairline
import com.salsalvia.subsurf.ui.components.InfoBanner
import com.salsalvia.subsurf.ui.components.Pill
import com.salsalvia.subsurf.ui.components.SegmentedPicker
import com.salsalvia.subsurf.ui.components.SettingsTile
import com.salsalvia.subsurf.ui.components.SubsurfCard
import com.salsalvia.subsurf.ui.icons.SubsurfIcons
import com.salsalvia.subsurf.ui.theme.Dims

@Composable
fun SettingsScreen(
    vm: AppViewModel,
    state: UiState,
    contentPadding: PaddingValues = PaddingValues(),
) {
    var url by remember(state.apiBaseUrl) { mutableStateOf(state.apiBaseUrl) }
    var testing by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<TestResult?>(null) }

    val trimmed = url.trim()
    val urlValid = trimmed.length > 8 &&
        (trimmed.startsWith("http://") || trimmed.startsWith("https://"))
    val dirty = trimmed.trimEnd('/') != state.apiBaseUrl.trimEnd('/')

    Column(
        Modifier
            .fillMaxSize()
            .padding(top = contentPadding.calculateTopPadding()),
    ) {
        ScreenTitle(
            title = stringResource(R.string.settings_title),
            subtitle = stringResource(R.string.settings_subtitle),
        )

        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Dims.l)
                .padding(bottom = contentPadding.calculateBottomPadding() + Dims.xl),
            verticalArrangement = Arrangement.spacedBy(Dims.m),
        ) {
            // ---------------------------------------------------------------- //
            // Backend connection
            // ---------------------------------------------------------------- //
            SubsurfCard {
                CardHeader(
                    title = stringResource(R.string.settings_api_url),
                    icon = SubsurfIcons.Signal,
                    trailing = {
                        // Live status: an explicit test result wins, otherwise the startup probe.
                        val online = when (testResult) {
                            is TestResult.Ok -> true
                            is TestResult.Fail -> false
                            null -> state.backendOnline
                        }
                        Pill(
                            text = stringResource(
                                when (online) {
                                    true -> R.string.status_online
                                    false -> R.string.status_offline
                                    null -> R.string.status_checking
                                },
                            ),
                            color = when (online) {
                                true -> MaterialTheme.colorScheme.primary
                                false -> MaterialTheme.colorScheme.error
                                null -> MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                    },
                )
                Text(
                    stringResource(R.string.settings_api_url_help),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it; testResult = null },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(R.string.settings_api_url_hint)) },
                    singleLine = true,
                    shape = RoundedCornerShape(14.dp),
                    isError = url.isNotBlank() && !urlValid,
                    supportingText = if (url.isNotBlank() && !urlValid) {
                        { Text(stringResource(R.string.url_invalid)) }
                    } else null,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Uri,
                        imeAction = ImeAction.Done,
                    ),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = MaterialTheme.colorScheme.primary,
                        unfocusedBorderColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.6f),
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                    ),
                )
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Dims.s),
                ) {
                    Button(
                        onClick = {
                            testResult = null
                            vm.saveBaseUrl(trimmed)
                        },
                        enabled = urlValid && dirty,
                        modifier = Modifier
                            .weight(1f)
                            .height(46.dp),
                        shape = RoundedCornerShape(13.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary,
                        ),
                    ) { Text(stringResource(R.string.settings_save)) }

                    OutlinedButton(
                        onClick = {
                            testResult = null
                            testing = true
                            vm.saveBaseUrl(trimmed)
                            vm.testConnection { ok, info ->
                                testing = false
                                testResult = if (ok) TestResult.Ok(info) else TestResult.Fail(info)
                            }
                        },
                        enabled = urlValid && !testing,
                        modifier = Modifier
                            .weight(1.3f)
                            .height(46.dp),
                        shape = RoundedCornerShape(13.dp),
                    ) {
                        if (testing) {
                            CircularProgressIndicator(Modifier.size(15.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(
                            stringResource(
                                if (testing) R.string.settings_testing else R.string.settings_test,
                            ),
                        )
                    }
                }

                AnimatedVisibility(
                    visible = testResult != null,
                    enter = fadeIn(),
                    exit = fadeOut(),
                ) {
                    when (val result = testResult) {
                        is TestResult.Ok -> InfoBanner(
                            text = stringResource(R.string.settings_test_ok, result.version),
                            icon = SubsurfIcons.Provenance,
                            accent = MaterialTheme.colorScheme.primary,
                        )
                        is TestResult.Fail -> InfoBanner(
                            text = stringResource(R.string.settings_test_fail_detail, result.reason),
                            icon = SubsurfIcons.Caveat,
                            accent = MaterialTheme.colorScheme.error,
                        )
                        null -> Unit
                    }
                }
            }

            // ---------------------------------------------------------------- //
            // Appearance
            // ---------------------------------------------------------------- //
            SubsurfCard {
                CardHeader(
                    title = stringResource(R.string.settings_appearance),
                    icon = SubsurfIcons.Palette,
                    trailing = {
                        Pill(
                            text = stringResource(
                                when (state.themeMode) {
                                    ThemeMode.SYSTEM -> R.string.settings_theme_system
                                    ThemeMode.LIGHT -> R.string.settings_theme_light
                                    ThemeMode.DARK -> R.string.settings_theme_dark
                                },
                            ),
                            color = MaterialTheme.colorScheme.secondary,
                        )
                    },
                )
                SettingsTile(
                    icon = SubsurfIcons.Theme,
                    title = stringResource(R.string.settings_theme_title),
                    subtitle = stringResource(R.string.settings_theme_desc),
                )
                SegmentedPicker(
                    options = listOf(
                        ThemeMode.SYSTEM to stringResource(R.string.settings_theme_system),
                        ThemeMode.LIGHT to stringResource(R.string.settings_theme_light),
                        ThemeMode.DARK to stringResource(R.string.settings_theme_dark),
                    ),
                    selected = state.themeMode,
                    onSelect = { vm.setThemeMode(it) },
                    modifier = Modifier.padding(bottom = Dims.xs),
                )
                Hairline()
                SettingsTile(
                    icon = SubsurfIcons.Globe,
                    title = stringResource(R.string.settings_language_title),
                    subtitle = stringResource(R.string.settings_language_desc),
                )
            }

            // ---------------------------------------------------------------- //
            // Data & method
            // ---------------------------------------------------------------- //
            SubsurfCard {
                CardHeader(
                    title = stringResource(R.string.settings_data_title),
                    icon = SubsurfIcons.Provenance,
                    tint = MaterialTheme.colorScheme.secondary,
                )
                Text(
                    stringResource(R.string.settings_about),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Hairline()
                SettingsTile(
                    icon = SubsurfIcons.Satellite,
                    title = stringResource(R.string.settings_source_s2),
                    subtitle = stringResource(R.string.settings_source_s2_desc),
                    tint = MaterialTheme.colorScheme.secondary,
                )
                SettingsTile(
                    icon = SubsurfIcons.Terrain,
                    title = stringResource(R.string.settings_source_dem),
                    subtitle = stringResource(R.string.settings_source_dem_desc),
                    tint = MaterialTheme.colorScheme.secondary,
                )
            }

            // ---------------------------------------------------------------- //
            // About — brand hero panel
            // ---------------------------------------------------------------- //
            SubsurfCard {
                // Hero: the SaliSurf-X wordmark banner on a molten gold→electric blue
                // gradient strip. This is the brand identity moment of the screen.
                Box(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(18.dp))
                        .background(
                            Brush.verticalGradient(
                                0f to Color(0xFF1A1206),
                                0.55f to Color(0xFF0A0F15),
                                1f to Color(0xFF04101C),
                            ),
                        )
                        .border(
                            1.dp,
                            MaterialTheme.colorScheme.outlineVariant,
                            RoundedCornerShape(18.dp),
                        )
                        .padding(vertical = Dims.l, horizontal = Dims.m),
                    contentAlignment = Alignment.Center,
                ) {
                    Image(
                        painter = painterResource(R.drawable.brand_wordmark),
                        contentDescription = stringResource(R.string.brand_wordmark_alt),
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(2.4f),
                        contentScale = ContentScale.Fit,
                    )
                }

                Spacer(Modifier.height(Dims.m))

                // Mother logo — the full brand artwork (silicon meets earth).
                // Square, fills the card width, rounded.
                Image(
                    painter = painterResource(R.drawable.brand_mother_logo),
                    contentDescription = stringResource(R.string.brand_mother_logo_alt),
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(1f)
                        .clip(RoundedCornerShape(18.dp))
                        .border(
                            1.dp,
                            MaterialTheme.colorScheme.outlineVariant,
                            RoundedCornerShape(18.dp),
                        ),
                    contentScale = ContentScale.Crop,
                )

                Spacer(Modifier.height(Dims.m))

                // App identity + tagline
                Text(
                    stringResource(R.string.app_name),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    stringResource(R.string.brand_tagline),
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    stringResource(R.string.settings_version, BuildConfig.VERSION_NAME),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(Dims.s))

                // Brand studies — the two alternate chip variants (neural-network core
                // and magma-terrain) shown side-by-side as small thumbnails, so the
                // full set of brand artwork is visible without dominating the panel.
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Dims.s),
                ) {
                    Image(
                        painter = painterResource(R.drawable.brand_chip_blue),
                        contentDescription = stringResource(R.string.brand_chip_alt),
                        modifier = Modifier
                            .weight(1f)
                            .aspectRatio(1f)
                            .clip(RoundedCornerShape(14.dp))
                            .border(
                                1.dp,
                                MaterialTheme.colorScheme.outlineVariant,
                                RoundedCornerShape(14.dp),
                            ),
                        contentScale = ContentScale.Crop,
                    )
                    Image(
                        painter = painterResource(R.drawable.brand_chip_terrain),
                        contentDescription = stringResource(R.string.brand_chip_alt),
                        modifier = Modifier
                            .weight(1f)
                            .aspectRatio(1f)
                            .clip(RoundedCornerShape(14.dp))
                            .border(
                                1.dp,
                                MaterialTheme.colorScheme.outlineVariant,
                                RoundedCornerShape(14.dp),
                            ),
                        contentScale = ContentScale.Crop,
                    )
                }

                Spacer(Modifier.height(Dims.s))

                // Designer credit — the signature that lives inside the mother logo
                Text(
                    stringResource(R.string.brand_designer_credit),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.primary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(Dims.m))
                Hairline()
                Spacer(Modifier.height(Dims.s))

                InfoBanner(
                    text = stringResource(R.string.disclaimer),
                    icon = SubsurfIcons.Caveat,
                    accent = MaterialTheme.colorScheme.tertiary,
                )
                Text(
                    stringResource(R.string.settings_licence),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Typed connection-test outcome, so no string prefix sniffing is needed. */
private sealed interface TestResult {
    data class Ok(val version: String) : TestResult
    data class Fail(val reason: String) : TestResult
}
