import java.util.Properties

val signingProperties = Properties()
val repositoryEnvFile = rootProject.projectDir.resolve("../../.env").canonicalFile
if (repositoryEnvFile.isFile) {
    repositoryEnvFile.inputStream().use(signingProperties::load)
}

fun signingValue(name: String): String =
    System.getenv(name)?.trim()?.takeIf { it.isNotEmpty() }
        ?: signingProperties.getProperty(name)?.trim().orEmpty()

val releaseKeystorePath = signingValue("ANDROID_RELEASE_KEYSTORE_PATH")
val releaseKeystorePassword = signingValue("ANDROID_RELEASE_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("ANDROID_RELEASE_KEY_ALIAS")
val releaseKeyPassword = signingValue("ANDROID_RELEASE_KEY_PASSWORD")
val releaseSigningReady = listOf(
    releaseKeystorePath,
    releaseKeystorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { it.isNotBlank() }

plugins {
    id("com.android.application")
    id("com.google.gms.google-services")
    // The Flutter Gradle Plugin must be applied after the Android plugin.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.rentalution.mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    flavorDimensions += "environment"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.rentalution.mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    productFlavors {
        create("dev") {
            dimension = "environment"
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
            manifestPlaceholders["appName"] = "Rentalution Dev"
        }
        create("prod") {
            dimension = "environment"
            manifestPlaceholders["appName"] = "rentalution"
        }
    }

    signingConfigs {
        if (releaseSigningReady) {
            create("release") {
                storeFile = file(releaseKeystorePath)
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            // Production artifacts must never be signed with the debug key.
            if (releaseSigningReady) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

tasks.configureEach {
    if (name.contains("prodrelease", ignoreCase = true)) {
        doFirst {
            check(releaseSigningReady) {
                "Production Android signing is not configured. Set all " +
                    "ANDROID_RELEASE_KEYSTORE_* values in the repository .env " +
                    "or the build environment."
            }
            check(file(releaseKeystorePath).isFile) {
                "Android release keystore was not found at $releaseKeystorePath."
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")
}

flutter {
    source = "../.."
}
