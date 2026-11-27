package com.example.btnotifyrelay

import android.Manifest
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothServerSocket
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ActivityCompat
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.io.PrintWriter
import java.util.UUID

class BtRelayService : Service() {

    companion object {
        val SERVICE_UUID: UUID = UUID.fromString("8ce255c0-200a-11e0-ac64-0800200c9a66")
        const val SERVICE_NAME = "BtNotifyRelay"
        const val FOREGROUND_ID = 1

        @Volatile
        var currentStatus: String = "停止中"
        var onStatusChanged: ((String) -> Unit)? = null
    }

    @Volatile
    private var isRunning = false
    private var serverSocket: BluetoothServerSocket? = null
    private var clientSocket: BluetoothSocket? = null
    private var workerThread: Thread? = null

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.createChannels(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!isRunning) {
            isRunning = true
            startForegroundWithStatus("PCからの接続を待機中...")
            workerThread = Thread { acceptLoop() }.apply { start() }
        }
        return START_STICKY
    }

    private fun startForegroundWithStatus(status: String) {
        updateStatus(status)
        val notification = NotificationHelper.buildServiceNotification(this, status)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                FOREGROUND_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            )
        } else {
            startForeground(FOREGROUND_ID, notification)
        }
    }

    private fun updateStatus(status: String) {
        currentStatus = status
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(FOREGROUND_ID, NotificationHelper.buildServiceNotification(this, status))
        onStatusChanged?.invoke(status)
    }

    private fun acceptLoop() {
        val btManager = getSystemService(BluetoothManager::class.java)
        val adapter = btManager?.adapter ?: run {
            updateStatus("エラー: Bluetooth非対応端末")
            stopSelf()
            return
        }

        while (isRunning) {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
                    ActivityCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED
                ) {
                    updateStatus("エラー: Bluetooth接続権限がありません")
                    break
                }

                serverSocket = adapter.listenUsingRfcommWithServiceRecord(SERVICE_NAME, SERVICE_UUID)
                updateStatus("PCからの接続を待機中...")

                val socket = serverSocket?.accept() ?: continue
                clientSocket = socket
                serverSocket?.close()

                val deviceName = try { socket.remoteDevice?.name ?: "PC" } catch (_: SecurityException) { "PC" }
                updateStatus("接続中: $deviceName")

                handleClient(socket)
            } catch (e: Exception) {
                if (isRunning) {
                    updateStatus("再待機中 (${e.message})")
                    try { Thread.sleep(2000) } catch (_: InterruptedException) {}
                }
            } finally {
                try { clientSocket?.close() } catch (_: Exception) {}
                try { serverSocket?.close() } catch (_: Exception) {}
            }
        }
    }

    private fun handleClient(socket: BluetoothSocket) {
        val reader = BufferedReader(InputStreamReader(socket.inputStream, Charsets.UTF_8))
        val writer = PrintWriter(OutputStreamWriter(socket.outputStream, Charsets.UTF_8), true)

        while (isRunning && socket.isConnected) {
            val line = reader.readLine() ?: break
            if (line.isBlank()) continue

            try {
                val json = JSONObject(line)
                when (json.optString("type")) {
                    "notification" -> {
                        val appName = json.optString("app_name", "PC")
                        val title = json.optString("title", "通知")
                        val body = json.optString("body", "")
                        NotificationHelper.showRelayedNotification(this, appName, title, body)
                    }
                    "ping" -> {
                        val pong = JSONObject().apply {
                            put("type", "pong")
                            put("timestamp", System.currentTimeMillis() / 1000)
                        }
                        writer.println(pong.toString())
                    }
                }
            } catch (_: Exception) {
                // 不正なJSON行はスキップ
            }
        }
    }

    override fun onDestroy() {
        isRunning = false
        try { clientSocket?.close() } catch (_: Exception) {}
        try { serverSocket?.close() } catch (_: Exception) {}
        workerThread?.interrupt()
        updateStatus("停止中")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
