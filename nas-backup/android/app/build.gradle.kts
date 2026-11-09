import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "io.github.masahiroc1203.nasbackup"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.masahiroc1203.nasbackup"
        minSdk = 29 // Android 10 以降
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    // 署名鍵はリポジトリに入れない。環境変数 (GitHub Actions では Secrets) で渡されたときだけ使う。
    // 毎回同じ鍵で署名すると、新しい版を上書きインストール (アップデート) できる。
    // 渡されなければ Android 標準のデバッグ用の鍵で署名する (インストールはできる)。
    val keystorePath = System.getenv("NASBACKUP_KEYSTORE")
    signingConfigs {
        if (!keystorePath.isNullOrBlank()) {
            create("sideload") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("NASBACKUP_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("NASBACKUP_KEY_ALIAS") ?: "nasbackup"
                keyPassword = System.getenv("NASBACKUP_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("sideload") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources {
            excludes += setOf(
                "META-INF/versions/9/OSGI-INF/MANIFEST.MF",
                "META-INF/DEPENDENCIES",
                "META-INF/INDEX.LIST",
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(project(":core"))

    implementation(platform("androidx.compose:compose-bom:2025.06.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    // smbj のログ出力先 (何も出さない)
    implementation("org.slf4j:slf4j-nop:2.0.17")
}
