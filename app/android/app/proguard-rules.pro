# Flutter-specific rules
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Keep Dio HTTP client
-keep class com.squareup.okhttp3.** { *; }
-dontwarn okhttp3.**
-dontwarn okio.**

# Keep model classes (if using JSON serialization)
-keepattributes *Annotation*
-keepattributes Signature

# Play Core library (deferred components)
-dontwarn com.google.android.play.core.splitcompat.SplitCompatApplication
-dontwarn com.google.android.play.core.splitinstall.**
-dontwarn com.google.android.play.core.tasks.**
