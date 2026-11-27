package com.example.btnotifyrelay

import android.Manifest
import android.bluetooth.BluetoothManager
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * 管理画面 (FR-AND-03): 状態表示、サービス開始/停止、テスト通知、バッテリー最適化の除外。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var statusTextView: TextView
    private lateinit var warningTextView: TextView
    private lateinit var btnToggle: Button
    private lateinit var btnBattery: Button

    private val startPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        if (BtRelayService.hasBluetoothPermission(this)) {
            startRelayService()
        } else {
            Toast.makeText(this, "「付近のデバイス」を許可しないと PC とつながりません", Toast.LENGTH_LONG).show()
        }
        refreshUi()
    }

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) postTestNotification() else openAppNotificationSettings()
        refreshUi()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        NotificationHelper.createChannels(this)

        statusTextView = TextView(this).apply {
            textSize = 18f
            setPadding(0, 0, 0, dp(8))
        }

        warningTextView = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(0xC6, 0x28, 0x28))
            setPadding(0, 0, 0, dp(16))
        }

        btnToggle = Button(this).apply {
            setOnClickListener {
                if (BtRelayService.isRunning) {
                    stopService(Intent(this@MainActivity, BtRelayService::class.java))
                } else {
                    requestPermissionsAndStart()
                }
                refreshUi()
            }
        }

        val btnTest = Button(this).apply {
            text = "テスト通知を発行（バンド設定確認用）"
            setOnClickListener { onTestNotificationClicked() }
        }

        btnBattery = Button(this).apply {
            setOnClickListener { openBatteryOptimizationSettings() }
        }

        val btnNotificationSettings = Button(this).apply {
            text = "このアプリの通知設定を開く"
            setOnClickListener { openAppNotificationSettings() }
        }

        val help = TextView(this).apply {
            textSize = 14f
            setPadding(0, dp(24), 0, 0)
            text = """
                使い方
                1. 「サービス開始」を押して、権限を許可します
                2. 「テスト通知を発行」を押します
                3. バンドの公式アプリ（Mi Fitness など）のアプリ通知設定で、「BT Notify Relay」をオンにします
                4. バンドにテスト通知が届いたら準備完了です。PC の BT Notify Relay を起動してください
            """.trimIndent()
        }

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24), dp(24), dp(24), dp(24))
            addView(TextView(this@MainActivity).apply {
                text = "BT Notify Relay"
                textSize = 24f
                setPadding(0, 0, 0, dp(16))
            })
            addView(statusTextView, matchWidth())
            addView(warningTextView, matchWidth())
            addView(btnToggle, matchWidth())
            addView(btnTest, matchWidth())
            addView(btnBattery, matchWidth())
            addView(btnNotificationSettings, matchWidth())
            addView(help, matchWidth())
        }

        val root = ScrollView(this).apply { addView(layout) }
        // Android 15 以降は画面の端まで描画されるので、ステータスバー等の分だけ余白を足す
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        setContentView(root)
    }

    override fun onStart() {
        super.onStart()
        BtRelayService.onStatusChanged = { runOnUiThread { refreshUi() } }
        refreshUi()
    }

    override fun onStop() {
        BtRelayService.onStatusChanged = null
        super.onStop()
    }

    private fun refreshUi() {
        statusTextView.text = "状態: ${BtRelayService.currentStatus}"
        btnToggle.text = if (BtRelayService.isRunning) "サービス停止" else "サービス開始（権限を許可して待機）"

        val ignoring = getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)
        btnBattery.text = if (ignoring) "バッテリー最適化: 除外済み" else "バッテリー最適化の除外設定を開く"

        val warnings = mutableListOf<String>()
        if (!BtRelayService.hasBluetoothPermission(this)) warnings += "・「付近のデバイス」の権限がありません"
        if (!NotificationHelper.canPostRelayNotifications(this)) warnings += "・通知がオフです（バンドに届きません）"
        if (!isBluetoothEnabled()) warnings += "・Bluetooth がオフです"
        if (!ignoring) warnings += "・バッテリー最適化の対象です（しばらくすると止まることがあります）"
        warningTextView.text = warnings.joinToString("\n")
    }

    private fun isBluetoothEnabled(): Boolean = try {
        getSystemService(BluetoothManager::class.java)?.adapter?.isEnabled == true
    } catch (_: SecurityException) {
        true // 判断できないときは警告を出さない
    }

    private fun requestPermissionsAndStart() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            !BtRelayService.hasBluetoothPermission(this)
        ) {
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        if (permissions.isNotEmpty()) {
            startPermissionLauncher.launch(permissions.toTypedArray())
        } else {
            startRelayService()
        }
    }

    private fun startRelayService() {
        // 権限が無いまま開始すると、Android 14 以降はサービスが起動できずにアプリが落ちる
        if (!BtRelayService.hasBluetoothPermission(this)) return
        ContextCompat.startForegroundService(this, Intent(this, BtRelayService::class.java))
    }

    private fun onTestNotificationClicked() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        postTestNotification()
    }

    private fun postTestNotification() {
        val shown = NotificationHelper.showRelayedNotification(
            this,
            "テスト送信",
            "会議リマインド (5分前)",
            "スマートバンドにこの通知が届けば連携完了です"
        )
        if (!shown) {
            Toast.makeText(this, "通知がオフになっています。通知設定を開きます", Toast.LENGTH_LONG).show()
            openAppNotificationSettings()
        }
    }

    private fun openBatteryOptimizationSettings() {
        val request = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:$packageName")
        }
        try {
            startActivity(request)
        } catch (_: ActivityNotFoundException) {
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        }
    }

    private fun openAppNotificationSettings() {
        val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
            putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        }
        try {
            startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
        }
    }

    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun matchWidth() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    )
}
