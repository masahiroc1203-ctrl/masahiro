package dev.masahiro.hiitweekly

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.util.Log
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import android.window.OnBackInvokedDispatcher
import androidx.webkit.WebViewAssetLoader
import org.json.JSONObject
import java.util.Locale

// Web版（リポジトリ直下）を APK に同梱して WebView で表示するだけの入れ物。
// WebView に無い機能（読み上げ・スリープ防止・ファイル保存・心拍計）は Bridge で Web 側に渡す。
class MainActivity : Activity() {
    private lateinit var web: WebView
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var pendingSpeech: Pair<String, Float>? = null
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var pendingExport: String? = null
    private var pendingHeart: (() -> Unit)? = null // Bluetooth の許可が出たら実行すること
    private val heart by lazy { HeartRate(this, ::heartEvent) }

    // 心拍計からの知らせを Web 側（js/hr.js）へ渡す。Bluetooth のスレッドからも呼ばれる
    private fun heartEvent(type: String, data: JSONObject) = runOnUiThread {
        if (!isDestroyed) web.evaluateJavascript("window.__hiitHr&&window.__hiitHr('$type',$data)", null)
    }

    // 心拍計を使う前に、Bluetooth の許可と電源を確かめる。Android 11 以前は機器をさがすのに位置情報の許可が要る
    private fun withBluetooth(action: () -> Unit) {
        val wanted = if (Build.VERSION.SDK_INT >= 31) {
            listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        val missing = wanted.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            pendingHeart = action
            requestPermissions(missing.toTypedArray(), REQ_BLUETOOTH)
        } else if (!heart.ready) {
            heartEvent("error", JSONObject().put("message", "Bluetooth をオンにしてください"))
        } else {
            action()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, grantResults: IntArray) {
        if (requestCode != REQ_BLUETOOTH) return super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val action = pendingHeart ?: return
        pendingHeart = null
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) withBluetooth(action)
        else heartEvent("error", JSONObject().put("message", "心拍計を使うには Bluetooth の許可が必要です"))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 端末の音量ボタンが、いつでもこのアプリの音（メディア音量）に効くようにする
        volumeControlStream = AudioManager.STREAM_MUSIC
        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            WebView.setWebContentsDebuggingEnabled(true) // デバッグ版だけ PC の Chrome から中を調べられる
        }
        web = WebView(this)
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true // 記録・設定は localStorage に保存している
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            allowContentAccess = false
        }
        web.addJavascriptInterface(Bridge(), "HiitNative")
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest) =
                loader.shouldInterceptRequest(request.url)

            // アプリ外のページ（YouTube検索など）は普段のブラウザで開く。動画の埋め込み（iframe）はそのまま
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame || request.url.host == WebViewAssetLoader.DEFAULT_DOMAIN) return false
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, request.url))
                } catch (_: ActivityNotFoundException) {
                    Toast.makeText(this@MainActivity, "開けるアプリがありません", Toast.LENGTH_SHORT).show()
                }
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            // バックアップの「読み込む」（<input type="file">）
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                // .json が application/octet-stream 扱いの端末もあるので種類で絞らない（中身は Web 側で検査する）
                val intent = Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
                return try {
                    startActivityForResult(intent, REQ_OPEN)
                    true
                } catch (_: ActivityNotFoundException) {
                    fileCallback = null
                    false
                }
            }
        }

        val root = FrameLayout(this)
        root.addView(web)
        // Android 15 以降は画面の端まで描画されるので、ステータスバーとナビゲーションバーの分だけ内側に寄せる。
        // 寄せた分は WebView に渡さない（渡すと CSS の env(safe-area-inset-*) でもう一度空いて二重になる）
        root.setOnApplyWindowInsetsListener { v, insets ->
            if (Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars())
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
                WindowInsets.CONSUMED
            } else {
                @Suppress("DEPRECATION")
                v.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop, insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
                @Suppress("DEPRECATION")
                insets.consumeSystemWindowInsets()
            }
        }
        setContentView(root)

        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            Log.i(TAG, "TTS init: ${if (ttsReady) "ok" else "failed ($status)"}")
            if (ttsReady) {
                val lang = tts?.setLanguage(Locale.JAPAN)
                Log.i(TAG, "TTS ja-JP: $lang")
                tts?.setSpeechRate(1.05f)
                pendingSpeech?.let { say(it.first, it.second) }
            }
        }

        if (Build.VERSION.SDK_INT >= 33) {
            onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT) { back() }
        }
        // テーマ色の変更などで作り直されたときは前の画面に戻す。まだ何も読み込んでいなかった場合は復元できないので最初から
        if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) web.loadUrl(START_URL)
    }

    // 端末の戻る：ページの履歴（下の階層・ワークアウト画面）を先に戻す。ワークアウト中は Web 側が終了確認を出す。
    // 一番上では終了せず裏に回す（Android 12 以降の標準と同じ）。終了させると、その後に届くメモリ解放の通知で
    // WebView 内部が異常終了するため（Android 17 エミュレータ・WebView 145 で毎回再現。裏に回すだけなら起きない）
    private fun back() {
        if (web.canGoBack()) web.goBack() else moveTaskToBack(true)
    }

    @Deprecated("Android 12 以前だけで使う")
    override fun onBackPressed() = back()

    // volume は 0〜1（端末のメディア音量に対する割合）
    private fun say(text: String, volume: Float) {
        if (!ttsReady) {
            pendingSpeech = text to volume
            return
        }
        pendingSpeech = null
        Log.d(TAG, "speak: $text (volume $volume)")
        val params = Bundle().apply { putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, volume.coerceIn(0f, 1f)) }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, params, "hiit")
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        when (requestCode) {
            REQ_OPEN -> {
                fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
                fileCallback = null
            }
            REQ_SAVE -> {
                val uri = data?.data
                val text = pendingExport
                pendingExport = null
                if (resultCode != RESULT_OK || uri == null || text == null) return
                val ok = runCatching {
                    contentResolver.openOutputStream(uri, "wt")!!.use { it.write(text.toByteArray()) }
                }.isSuccess
                Toast.makeText(this, if (ok) "バックアップを保存しました" else "保存できませんでした", Toast.LENGTH_SHORT).show()
            }
            else -> super.onActivityResult(requestCode, resultCode, data)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onPause() {
        super.onPause()
        web.onPause()
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
    }

    override fun onDestroy() {
        heart.release()
        tts?.shutdown()
        (web.parent as? ViewGroup)?.removeView(web)
        web.destroy()
        super.onDestroy()
    }

    // Web 側からは window.HiitNative として呼ぶ（js/audio.js・js/views/history.js）。呼ばれるのは WebView の別スレッド
    inner class Bridge {
        @JavascriptInterface
        fun speak(text: String, volume: Float) = runOnUiThread { say(text, volume) }

        @JavascriptInterface
        fun stopSpeaking() {
            tts?.stop()
        }

        @JavascriptInterface
        fun keepScreenOn(on: Boolean) = runOnUiThread {
            if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }

        // navigator.vibrate と同じ形（"200" や "[100,80,100]" = 振動, 休み, 振動…）
        @JavascriptInterface
        fun vibrate(pattern: String) {
            val ms = pattern.trim('[', ']', ' ').split(',').mapNotNull { it.trim().toLongOrNull() }
            if (ms.isEmpty()) return
            val vibrator = if (Build.VERSION.SDK_INT >= 31) {
                getSystemService(VibratorManager::class.java).defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Vibrator::class.java)
            }
            // Android の波形は「休み, 振動, 休み…」の順なので先頭に 0 を足す
            vibrator.vibrate(VibrationEffect.createWaveform((listOf(0L) + ms).toLongArray(), -1))
        }

        @JavascriptInterface
        fun saveFile(name: String, text: String) = runOnUiThread {
            pendingExport = text
            val intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/json")
                .putExtra(Intent.EXTRA_TITLE, name)
            try {
                startActivityForResult(intent, REQ_SAVE)
            } catch (_: ActivityNotFoundException) {
                pendingExport = null
                Toast.makeText(this@MainActivity, "保存先を選ぶ画面を開けません", Toast.LENGTH_SHORT).show()
            }
        }

        // 心拍計（js/hr.js）。結果は window.__hiitHr に届く
        @JavascriptInterface
        fun hrScan() = runOnUiThread { withBluetooth { heart.scan() } }

        @JavascriptInterface
        fun hrStopScan() = runOnUiThread { heart.stopScan() }

        @JavascriptInterface
        fun hrConnect(address: String) = runOnUiThread { withBluetooth { heart.connect(address) } }

        @JavascriptInterface
        fun hrDisconnect() = runOnUiThread { heart.disconnect() }
    }

    private companion object {
        const val TAG = "HiitWeekly"
        const val START_URL = "https://${WebViewAssetLoader.DEFAULT_DOMAIN}/assets/index.html"
        const val REQ_OPEN = 1
        const val REQ_SAVE = 2
        const val REQ_BLUETOOTH = 3
    }
}
