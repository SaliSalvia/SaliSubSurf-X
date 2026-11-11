package com.salsalvia.subsurf

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import com.salsalvia.subsurf.ui.AppRoot
import com.salsalvia.subsurf.ui.theme.SubsurfTheme
import com.salsalvia.subsurf.ui.theme.isDarkTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Edge-to-edge with transparent system bars; the Compose theme flips the icon colours.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT),
        )

        setContent {
            val vm: AppViewModel = viewModel()
            val state by vm.state.collectAsState()
            // Resolve the user's stored preference against the current system setting (reactive,
            // so a system dark/light switch re-resolves immediately).
            val dark = state.themeMode.isDarkTheme()
            // Publish the resolved appearance so the map can choose its basemap, then render.
            LaunchedEffect(dark) { vm.applyResolvedTheme(dark) }
            // One startup probe, so the map can show a "backend not reachable" hint.
            LaunchedEffect(Unit) { vm.probeBackend() }
            SubsurfTheme(darkTheme = dark) {
                AppRoot(vm)
            }
        }
    }
}
