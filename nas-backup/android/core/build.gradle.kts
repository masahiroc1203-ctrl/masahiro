import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("org.jetbrains.kotlin.jvm")
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    // SMB2/3 クライアント (LS720D などの NAS の共有フォルダに接続する)
    api("com.hierynomus:smbj:0.15.0")

    testImplementation("junit:junit:4.13.2")
    testRuntimeOnly("org.slf4j:slf4j-nop:2.0.17")
}

tasks.test {
    // 実際の SMB サーバーを使うテストは SMB_TEST_HOST などの環境変数があるときだけ動く
    listOf("SMB_TEST_HOST", "SMB_TEST_PORT", "SMB_TEST_SHARE", "SMB_TEST_USER", "SMB_TEST_PASSWORD").forEach { key ->
        System.getenv(key)?.let { environment(key, it) }
    }
    testLogging {
        events("passed", "skipped", "failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
