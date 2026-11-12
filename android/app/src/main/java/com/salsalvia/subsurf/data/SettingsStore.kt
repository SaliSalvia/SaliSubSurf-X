package com.salsalvia.subsurf.data

import android.content.Context
import android.content.SharedPreferences
import com.salsalvia.subsurf.BuildConfig

/** How the app chooses between the light and the dark palette. */
enum class ThemeMode { SYSTEM, LIGHT, DARK }

/**
 * Tiny persistence layer for presentation preferences plus the backend base URL.
 * Only the backend base URL affects behaviour; the rest is purely cosmetic.
 */
class SettingsStore(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var apiBaseUrl: String
        get() = prefs.getString(KEY_URL, null)?.takeIf { it.isNotBlank() }
            ?: BuildConfig.API_BASE_URL
        set(value) {
            prefs.edit().putString(KEY_URL, value).apply()
        }

    /**
     * Defaults to [ThemeMode.DARK]: the brand logo is luminous artwork on black, so the app opens
     * in the identity it was designed in. Users can switch to Light or follow the device.
     */
    var themeMode: ThemeMode
        get() {
            val raw = prefs.getString(KEY_THEME, null) ?: return ThemeMode.DARK
            return ThemeMode.entries.firstOrNull { it.name == raw } ?: ThemeMode.DARK
        }
        set(value) {
            prefs.edit().putString(KEY_THEME, value.name).apply()
        }

    companion object {
        private const val PREFS_NAME = "subsurf_settings"
        private const val KEY_URL = "api_base_url"
        private const val KEY_THEME = "theme_mode"
    }
}
