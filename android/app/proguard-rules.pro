# --------------------------------------------------------------------------- //
# R8 rules for the release build (isMinifyEnabled = true).
# Every entry here is required by a library that relies on reflection.
# --------------------------------------------------------------------------- //

# MapLibre Native loads its classes reflectively and ships its own consumer rules; keep the
# platform surface plus the JNI entry points that R8 cannot see.
-keep class org.maplibre.** { *; }
-dontwarn org.maplibre.**
-keep class com.mapbox.** { *; }
-dontwarn com.mapbox.**

# Retrofit / OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# ViewModels are instantiated reflectively by viewModel(); AndroidX ships a rule for this, but an
# explicit one keeps the app's own ViewModel alive across R8/AGP upgrades.
-keep class * extends androidx.lifecycle.ViewModel {
    <init>(...);
}

# kotlinx-serialization: generated serializers are resolved by reflection on the companion.
-keepclassmembers class com.salsalvia.subsurf.data.** {
    *** Companion;
}
-keepclasseswithmembers class com.salsalvia.subsurf.data.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keepattributes *Annotation*, InnerClasses, Signature
