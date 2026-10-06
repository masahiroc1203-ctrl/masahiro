// トップレベルのビルド設定。実際の設定は app/build.gradle.kts 側。
// AGP 9 は Kotlin を内蔵しているので Kotlin プラグインは不要。
plugins {
    id("com.android.application") version "9.1.0" apply false
}
