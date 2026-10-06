plugins {
    id("com.android.application")
}

android {
    namespace = "dev.masahiro.hiitweekly"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "dev.masahiro.hiitweekly"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    // アプリ内のファイルを https://appassets.androidplatform.net/ として配信する（file:// では ES Modules が読めない）
    implementation("androidx.webkit:webkit:1.14.0")
}

// Webアプリ本体（リポジトリ直下の index.html・css・js・icons）を assets にコピーして APK に同梱する。
// 元ファイルは1か所だけにしておき、Web版とアプリ版で中身がずれないようにする。
abstract class CopyWebApp : DefaultTask() {
    @get:Internal
    abstract val webRoot: DirectoryProperty

    @get:Input
    abstract val patterns: ListProperty<String>

    @get:InputFiles
    @get:PathSensitive(PathSensitivity.RELATIVE)
    val webFiles: FileTree
        get() = webRoot.get().asFileTree.matching { include(patterns.get()) }

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @get:Inject
    abstract val fs: FileSystemOperations

    @TaskAction
    fun copy() {
        fs.sync {
            from(webRoot) { include(patterns.get()) }
            into(outputDir)
        }
    }
}

val copyWebApp = tasks.register<CopyWebApp>("copyWebApp") {
    webRoot.set(rootDir.parentFile)
    // sw.js は入れない（ファイルはすべて APK の中にあり、オフライン用のキャッシュが要らないため）
    patterns.set(listOf("index.html", "manifest.webmanifest", "css/**", "js/**", "icons/**"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(copyWebApp, CopyWebApp::outputDir)
    }
}
