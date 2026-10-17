plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.hypertechwidget.cosmo"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.hypertechwidget.cosmo"
        minSdk = 26
        targetSdk = 34
        // CI passes the build number so each APK installs over the last one.
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0.${System.getenv("GITHUB_RUN_NUMBER") ?: "0"}"
    }

    signingConfigs {
        // A fixed key in the repo so every build can update the installed app.
        // Fine for sideloading your own app; use a private key for any store release.
        getByName("debug") {
            storeFile = file("cosmo-debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        getByName("debug") { signingConfig = signingConfigs.getByName("debug") }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
