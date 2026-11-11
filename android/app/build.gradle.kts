import java.util.Base64

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// --------------------------------------------------------------------------- //
// CI release signing: the keystore is injected via environment variables
// (KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD). Without them the
// release APK is simply built unsigned — nothing is ever committed to git.
// --------------------------------------------------------------------------- //
val keystoreB64: String? = System.getenv("KEYSTORE_BASE64")?.takeIf { it.isNotBlank() }
val hasCiSigning = keystoreB64 != null
val ciKeystoreFile = File(layout.buildDirectory.get().asFile, "signing/release.keystore")
if (hasCiSigning) {
    ciKeystoreFile.parentFile.mkdirs()
    ciKeystoreFile.writeBytes(Base64.getDecoder().decode(keystoreB64!!.replace("\\s".toRegex(), "")))
}

// Optional API base URL override: gradle -PAPI_BASE_URL=https://host/ :app:assembleRelease
val apiBaseUrl: String = (project.findProperty("API_BASE_URL") as String?) ?: "http://10.0.2.2:8000/"

android {
    namespace = "com.salsalvia.subsurf"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.salsalvia.subsurf"
        minSdk = 26
        targetSdk = 36
        versionCode = 9
        versionName = "1.6.1"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
    }

    signingConfigs {
        if (hasCiSigning) {
            create("ci") {
                storeFile = ciKeystoreFile
                storePassword = System.getenv("KEYSTORE_PASSWORD") ?: ""
                keyAlias = System.getenv("KEY_ALIAS") ?: ""
                keyPassword = System.getenv("KEY_PASSWORD")
                    ?: System.getenv("KEYSTORE_PASSWORD") ?: ""
            }
        }
    }

    buildTypes {
        release {
            // Shrinking + resource stripping: the release APK is several MB smaller and starts
            // faster. Rules for MapLibre and kotlinx-serialization live in proguard-rules.pro.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (hasCiSigning) {
                signingConfig = signingConfigs.getByName("ci")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }

    // Lint is a hard gate on the debug variant (CI runs :app:lintDebug).
    // Release lint stays off to keep release packaging fast.
    lint {
        checkReleaseBuilds = false
        abortOnError = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons.core)

    implementation(libs.maplibre.android)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    debugImplementation(libs.compose.ui.tooling)
    testImplementation(libs.junit)
}
