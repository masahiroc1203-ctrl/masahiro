package com.example.btnotifyrelay

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var statusTextView: TextView

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        startRelayService()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        NotificationHelper.createChannels(this)

        statusTextView = TextView(this).apply {
            text = "状態: ${BtRelayService.currentStatus}"
            textSize = 18f
            setPadding(0, 0, 0, 32)
        }

        val btnStart = Button(this).apply {
            text = "サービス開始（権限許可して待機）"
            setOnClickListener { requestPermissionsAndStart() }
        }

        val btnStop = Button(this).apply {
            text = "サービス停止"
            setOnClickListener {
                stopService(Intent(this@MainActivity, BtRelayService::class.java))
            }
        }

        val btnTest = Button(this).apply {
            text = "テスト通知を発行（バンド設定確認用）"
            setOnClickListener {
                NotificationHelper.showRelayedNotification(
                    this@MainActivity,
                    "テスト送信",
                    "会議リマインド (5分前)",
                    "スマートバンドにこの通知が届けば連携完了です"
                )
            }
        }

        val btnBattery = Button(this).apply {
            text = "バッテリー最適化の除外設定を開く"
            setOnClickListener {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
                startActivity(intent)
            }
        }

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(48, 48, 48, 48)
            addView(statusTextView)
            addView(btnStart)
            addView(btnStop)
            addView(btnTest)
            addView(btnBattery)
        }

        setContentView(layout)

        BtRelayService.onStatusChanged = { status ->
            runOnUiThread {
                statusTextView.text = "状態: $status"
            }
        }
    }

    private fun requestPermissionsAndStart() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        if (permissions.isNotEmpty()) {
            permissionLauncher.launch(permissions.toTypedArray())
        } else {
            startRelayService()
        }
    }

    private fun startRelayService() {
        val intent = Intent(this, BtRelayService::class.java)
        ContextCompat.startForegroundService(this, intent)
    }

    override fun onDestroy() {
        BtRelayService.onStatusChanged = null
        super.onDestroy()
    }
}
